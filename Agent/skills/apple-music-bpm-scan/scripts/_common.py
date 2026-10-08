#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apple-music-bpm-scan / _common.py —— 各脚本共用的路径、解析与归一化工具。

零个人信息：本文件不含任何真实曲库、艺人清单或本机路径，全部由运行时解析。
"""
import csv
import os
import re
import sys
import unicodedata

import _boot  # noqa: F401  (自举 opencc，见 _boot.py)
import _dirs
from opencc import OpenCC

# ── 目录 ────────────────────────────────────────────────────────────────
WORK = _dirs.work_dir()
OUT = _dirs.out_dir()

BPM_CSV = os.path.join(WORK, "bpm_all.csv")
CACHE_DIR = os.path.join(WORK, "bpm_cache")
LIB_RECS_JSON = os.path.join(WORK, "lib_recs.json")
RESULT_JSON = os.path.join(WORK, "lib_result.json")
CAND_LIB = os.path.join(WORK, "cand_lib.txt")

HEADER = ["query_title", "query_artist", "found_title", "found_artist",
          "bpm", "duration", "title_sim", "version", "slug"]

#: BPM 缓存文件名里不带任何原始查询串，只留 md5 前 16 位，避免外泄检索词
CACHE_MIN_BYTES = 1000

_cc = OpenCC("t2s")
_s2t = OpenCC("s2t")


def ensure_dirs():
    """建好 work/ 与 out/。所有脚本开头调用一次。"""
    return _dirs.ensure_dirs()


# ── 目标 BPM 区间 ────────────────────────────────────────────────────────
def bpm_range():
    """目标单拍区间 (lo, hi)，默认 180-184。

    可用 `AMBS_BPM_RANGE=170-174`（环境变量或 config.env）整体改口径。
    """
    raw = os.environ.get("AMBS_BPM_RANGE") or _dirs.cfg("AMBS_BPM_RANGE")
    if raw:
        m = re.match(r"^\s*(\d{2,3})\s*[-~,]\s*(\d{2,3})\s*$", raw)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if 0 < lo <= hi <= 300:
                return lo, hi
    return 180, 184


def half_range():
    """由单拍区间推出的半速区间，用于双踩判定。

    双踩是「每拍踩两步」，所以半速值 b 必须满足 lo <= 2b <= hi，
    即 b ∈ [ceil(lo/2), floor(hi/2)]。180-184 → 90-92（与实际完全吻合）；
    175-179 → 88-89（×2 = 176/178，仍落在区间内）。
    """
    lo, hi = bpm_range()
    return (lo + 1) // 2, hi // 2


# ── Apple Music 导出文件 ─────────────────────────────────────────────────
def find_export(arg=None):
    """定位 Apple Music 导出文件。

    顺序：函数参数 > $AMBS_EXPORT（环境变量或 config.env）> 当前目录 >
          工作目录 > ~/Downloads 常见文件名。
    """
    cands = []
    if arg:
        cands.append(arg)
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        cands.append(sys.argv[1])
    env = os.environ.get("AMBS_EXPORT") or _dirs.cfg("AMBS_EXPORT")
    if env:
        cands.append(env)
    home = os.path.expanduser("~")
    for d in (os.getcwd(), WORK, os.path.join(home, "Downloads")):
        for name in ("音乐.txt", "Music Library.txt", "音乐 .txt",
                     "Music Library.xml", "音乐.xml"):
            cands.append(os.path.join(d, name))
    for p in cands:
        if p and os.path.exists(p):
            return os.path.abspath(os.path.expanduser(p))
    raise SystemExit(
        "找不到 Apple Music 导出文件。请先在 Music 里「文件 → 资料库 → 导出…」导出为\n"
        "    ~/Downloads/音乐.txt\n"
        "或显式指定： python3 %s /path/to/音乐.txt\n"
        "（已尝试：%s）" % (os.path.basename(sys.argv[0] or "lib_fetch.py"), ", ".join(cands)))


def _decode(raw):
    """导出文件是 UTF-16LE + BOM、CR 行尾；也容忍 UTF-8 版本。"""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        txt = raw.decode("utf-16")
    else:
        try:
            txt = raw.decode("utf-16")
        except UnicodeError:
            txt = raw.decode("utf-8-sig", "replace")
    return txt.replace("\r\n", "\n").replace("\r", "\n")


def load_lib(path=None):
    """解析导出文件 → [{title, artist, album, genre, kind, dur, year}, ...]。

    导出为 TSV、31 列，首行为表头；用到的列位（对真实导出实测确认）：
    0 名称 / 1 艺人 / 3 专辑 / 6 流派 / 9 类型 / 11 时长(秒) / 16 年份。
    不同 macOS 版本的列位可能微调，取不到就是空串，不会报错。
    """
    src = find_export(path)
    print("读取资料库导出：%s" % src)
    text = _decode(open(src, "rb").read())

    def col(f, i):
        return f[i].strip() if len(f) > i else ""

    out = []
    for line in [x for x in text.split("\n") if x.strip()][1:]:
        f = line.split("\t")
        if len(f) < 2 or not f[0].strip():
            continue
        out.append({
            "title": col(f, 0),
            "artist": col(f, 1),
            "album": col(f, 3),
            "genre": col(f, 6),
            "kind": col(f, 9),
            "dur": col(f, 11),
            "year": col(f, 16),
        })
    return out


# ── 文本归一化 ───────────────────────────────────────────────────────────
_PUNCT = re.compile(r"[\s\-_’'\".,!?()（）\[\]*·]+")


def norm(s):
    """繁→简 + NFKC + 去空白标点。不转换时「綠光」与「绿光」相似度只有 0.5。"""
    s = _cc.convert(s or "")
    s = unicodedata.normalize("NFKC", s).lower()
    return _PUNCT.sub("", s)


def to_traditional(s):
    """简体 → 繁体，用于向只收录繁体曲名的库补一次查询。"""
    return _s2t.convert(s or "")


_SUFFIX = re.compile(r"[（(\[][^）)\]]*[）)\]]")


def clean_title(t):
    """去掉 (Live) / (电影…插曲) / [第5期 ver.] 这类后缀，提高命中率。"""
    t = _SUFFIX.sub(" ", t or "")
    return re.sub(r"\s+", " ", t).strip() or (t or "").strip()


_SPLIT_ARTIST = re.compile(r"\s*(?:&|＆|feat\.?|ft\.?|、|,|，|/)\s*", re.I)


def primary_artist(a):
    """`A & B` / `A feat. B` / `A、B` → 取第一顺位。"""
    return _SPLIT_ARTIST.split(a or "")[0].strip() or (a or "").strip()


def all_artists(a):
    """拆出全部参与艺人，按出现顺序去重。"""
    out = []
    for x in _SPLIT_ARTIST.split(a or ""):
        x = x.strip()
        if x and x not in out:
            out.append(x)
    return out


# ── BPM 库读写 ───────────────────────────────────────────────────────────
def read_bpm_rows(path=None):
    """读 bpm_all.csv；文件不存在时返回 []（首次运行即从零建库）。"""
    path = path or BPM_CSV
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh)]


def write_bpm_rows(rows, path=None):
    """写 bpm_all.csv（统一表头）。"""
    path = path or BPM_CSV
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        for r in rows:
            w.writerow([r[h] if isinstance(r, dict) else r[i]
                        for i, h in enumerate(HEADER)])


def read_candidates(*paths, strict=False):
    """读 `歌名|歌手` 候选文件，返回去重后的 (title, artist) 列表。

    strict=True（用户显式指定的文件）时，路径不存在直接报错，
    避免「文件写错位置 → 静默 0 候选 → 白跑一轮」。
    """
    out, seen = [], set()
    for p in paths:
        p = p if os.path.isabs(p) else os.path.join(WORK, p)
        if not os.path.exists(p):
            if strict:
                raise SystemExit("候选文件不存在：%s" % p)
            continue
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            t, a = line.split("|", 1)
            t, a = t.strip(), a.strip()
            if not t or (t, a) in seen:
                continue
            seen.add((t, a))
            out.append((t, a))
    return out


def write_candidates(path, pairs, note=None):
    """写 `歌名|歌手` 候选文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if note:
            fh.write("# %s\n" % note)
        for t, a in pairs:
            fh.write("%s|%s\n" % (t, a))
    return path


def eprint(*a):
    """进度一律走 stderr，stdout 留给结果，便于重定向。"""
    sys.stderr.write(" ".join(str(x) for x in a) + "\n")
    sys.stderr.flush()
