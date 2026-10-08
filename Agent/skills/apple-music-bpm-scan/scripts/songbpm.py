#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""songbpm.com 抓取内核：查询 + 解析 + 匹配，供上层脚本复用。

**这是一个库，不是入口。** 没有 `main()`，直接运行本文件不做任何事。
要抓 BPM 请用唯一入口 `fetch_bpm.py`。

对外接口：
    fetch(query)                 → HTML（带磁盘缓存）
    parse(body)                  → [{slug, artist, title, bpm, dur, is_ver}, ...]
    matches(title, artist, res)  → [(相似度, 结果), ...] 按相似度降序
    process(task)                → CSV 行列表，task = (序号, 总数, 歌名, 艺人)
    artist_match(q_artist, f)    → 命中的是不是原唱（别名表判定）
    WORKERS                      → 建议并发数（6）

调用方：fetch_bpm.py（增量抓取）、lib_report.py（缺项补抓）、probe.py（人工核查）。
"""
import difflib
import hashlib
import html
import os
import re
import threading
import time
import urllib.parse
import urllib.request

import _common as C
from _aliases import ALIAS, QUERY_ALIAS

CACHE = C.CACHE_DIR
os.makedirs(CACHE, exist_ok=True)

#: 6 线程最稳；8 线程会被限流，约 15% 请求超时
WORKERS = 6

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_lock = threading.Lock()

_ALIAS_NORM = {k: [C.norm(v) for v in vs] for k, vs in ALIAS.items()}


def artist_match(q_artist, f_artist):
    """命中的艺人是不是原唱。

    先子串双向包含，再查别名表。⚠️ 只查 `q_artist` 这一项：
    若改成遍历整个别名表，会把 郁可唯→Hebe Tien 这类跨歌手误配判为原唱。
    """
    q, f = C.norm(q_artist), C.norm(f_artist)
    if not q or not f:
        return False
    if q in f or f in q:
        return True
    for a in _ALIAS_NORM.get(q_artist, []):
        if a and (a == f or a in f or f in a):
            return True
    return False


def fetch(query):
    """查 songbpm，命中缓存则不发请求。失败返回空串（最多重试 4 次）。"""
    key = hashlib.md5(query.encode("utf-8")).hexdigest()[:16] + ".html"
    path = os.path.join(CACHE, key)
    if os.path.exists(path) and os.path.getsize(path) > C.CACHE_MIN_BYTES:
        return open(path, encoding="utf-8", errors="replace").read()
    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(
        "https://songbpm.com/searches", data=data,
        headers={"User-Agent": UA, "Origin": "https://songbpm.com",
                 "Referer": "https://songbpm.com/",
                 "Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "text/html,application/xhtml+xml",
                 "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=35) as r:
                body = r.read().decode("utf-8", "replace")
            if "BPM results for" in body:
                open(path, "w", encoding="utf-8").write(body)
                return body
        except Exception as e:
            with _lock:
                C.eprint("! %s: %s" % (query, e))
        time.sleep(1.5 + attempt * 1.5)
    return ""


BLOCK = re.compile(r'<a class="hover:bg-foreground/5[^"]*"\s+href="(/@[^"]+)"(.*?)</a>', re.S)
P = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
BPM = re.compile(r">BPM</span>\s*<span[^>]*>\s*(\d+)\s*</span>", re.S)
DUR = re.compile(r">Duration</span>\s*<span[^>]*>\s*([\d:]+)\s*</span>", re.S)

#: 命中即视为「非录音室版本」，BPM 不能代表用户库里的原曲
VERSION = re.compile(
    r"-\s*(Live|Remastered?|Acoustic|Demo|Remix|Instrumental|Karaoke"
    r"|伴奏|現場|现场|版)\b", re.I)


def parse(body):
    """解析搜索结果页 → 结果列表（每次搜索 songbpm 最多返回 5 条）。"""
    out = []
    for m in BLOCK.finditer(body or ""):
        slug, inner = m.group(1), m.group(2)
        ps = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in P.findall(inner)]
        b = BPM.search(inner)
        d = DUR.search(inner)
        if len(ps) >= 2 and b:
            out.append({"slug": slug, "artist": ps[0], "title": ps[1],
                        "bpm": int(b.group(1)), "dur": d.group(1) if d else "",
                        "is_ver": bool(VERSION.search(ps[1]))})
    return out


def matches(title, artist, res):
    """按「原唱 + 歌名相似度 ≥ 0.5」筛出候选，非录音室版本排在后面。"""
    nt = C.norm(title)
    out = []
    for r in res:
        if not artist_match(artist, r["artist"]):
            continue
        s1 = difflib.SequenceMatcher(None, nt, C.norm(r["title"])).ratio()
        if s1 >= 0.5:
            out.append((s1, r))
    out.sort(key=lambda x: (-x[0], x[1]["is_ver"]))
    return out


def _lookup(title, artist):
    """一次曲目查询：中文名 → 繁体名 → QUERY_ALIAS 重查词，命中即止。"""
    for qt in (title, C.to_traditional(title)):
        ms = matches(title, artist, parse(fetch("%s %s" % (artist, qt))))
        if ms:
            return ms
    for qa in QUERY_ALIAS.get(artist, []):
        for qt in (title, C.to_traditional(title)):
            ms = matches(title, artist, parse(fetch("%s %s" % (qa, qt))))
            if ms:
                return ms
    return []


def process(item):
    """抓一首候选，返回 CSV 行列表（每行一个匹配版本）。"""
    i, total, title, artist = item
    ms = _lookup(title, artist)
    rows, seen = [], set()
    for s1, r in ms:
        if r["slug"] in seen:      # 同一录音可能有重复条目，按 slug 去重
            continue
        seen.add(r["slug"])
        rows.append([title, artist, r["title"], r["artist"], r["bpm"], r["dur"],
                     round(s1, 3), "Live/版" if r["is_ver"] else "", r["slug"]])
    with _lock:
        C.eprint("[%d/%d] %s / %s -> %d ver %s" % (
            i, total, title, artist, len(rows),
            ",".join("%d%s" % (r[4], "(L)" if r[7] else "") for r in rows) or "no match"))
    return rows


if __name__ == "__main__":
    raise SystemExit(
        "songbpm.py 是抓取内核库，不能直接运行（没有全量抓取的入口）。\n"
        "请用：\n"
        "    python3 %s            # 增量抓取 work/cand_lib.txt\n"
        "    python3 %s 候选.txt   # 或指定候选文件"
        % (os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_bpm.py"),
           os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_bpm.py")))
