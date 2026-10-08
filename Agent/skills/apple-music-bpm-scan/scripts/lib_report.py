#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资料库 → 目标 BPM 区间 的完整报告（含在线补抓）。

    python3 lib_report.py [导出文件]

流程：
  1) 解析导出文件（UTF-16 / TSV）
  2) 先与已有 bpm_all.csv 交叉比对（整对精确 → 清理后整对 → 仅歌名）
  3) 仍缺的用 songbpm 补抓（复用 songbpm，共享 work/bpm_cache/，不写 bpm_all.csv）
  4) 分桶落 work/lib_result.json，交给 render_lib.py 出 HTML / TXT

「此前已交付」的曲目来自 work/delivered.txt（可选，`歌名|歌手` 每行一条），
本脚本不内置任何历史清单。
"""
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import _common as C
import songbpm as F
from lib_scan import index_bpm, lookup

#: 可选：此前已经给过用户的曲目，报告里会标注而不是当作新发现
DELIVERED_FILE = os.path.join(C.WORK, "delivered.txt")

#: 补抓时的额外歌名写法（去掉空格等），提高命中率
WORKERS = 5


def load_delivered():
    """读 work/delivered.txt（不存在则为空）。"""
    if not os.path.exists(DELIVERED_FILE):
        return set()
    out = set()
    for line in open(DELIVERED_FILE, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            t, a = line.split("|", 1)
            out.add((C.norm(t), C.norm(a)))
        else:
            out.add((C.norm(line), ""))
    return out


def delivered_set():
    return load_delivered()


def is_delivered(track, delivered):
    """同歌名 + 同歌手（歌手子串双向匹配，兼容「痛仰」vs「痛仰乐队」）。"""
    nt, na = C.norm(track["title"]), C.norm(track["artist"])
    for dt, da in delivered:
        if da and not (da == na or da in na or na in da):
            continue
        if dt == nt or dt in nt or nt in dt:
            return True
    return False


def hunt(track):
    """在线补抓一首：歌名多写法 × 参与艺人 × 别名，返回 [(bpm, 版本标记), ...]。"""
    titles = []
    for t in (C.clean_title(track["title"]), track["title"],
              C.clean_title(track["title"]).replace(" ", ""),
              track["title"].replace(" ", "")):
        if t and t not in titles:
            titles.append(t)
    artists = []
    for a in C.all_artists(track["artist"]):
        for cand in [a] + F.QUERY_ALIAS.get(a, []):
            if cand and cand not in artists:
                artists.append(cand)
    for title in titles:
        for artist in artists:
            for qtitle in (title, C.to_traditional(title)):
                ms = F.matches(title, artist, F.parse(F.fetch("%s %s" % (artist, qtitle))))
                if ms:
                    return [(r["bpm"], "Live/版" if r["is_ver"] else "") for _, r in ms]
    return []


def main():
    C.ensure_dirs()
    lib = C.load_lib(sys.argv[1] if len(sys.argv) > 1 else None)
    rows = C.read_bpm_rows()
    exact, bytitle = index_bpm(rows)

    lo, hi = C.bpm_range()
    hlo, hhi = C.half_range()
    delivered = delivered_set()

    # ── 1) 先用本地 BPM 库比对 ──
    results, todo = [], []
    for track in lib:
        cand = lookup(track, exact, bytitle)
        if cand:
            results.append((track, [(int(r["bpm"]), r["version"]) for r in cand]))
        else:
            todo.append(track)
    C.eprint("资料库 %d 首 | 本地已覆盖 %d 首 | 待补抓 %d 首" % (len(lib), len(results), len(todo)))

    # ── 2) 缺的在线补抓 ──
    lock = threading.Lock()

    def worker(track):
        got = hunt(track)
        if not got:
            got = [(0, "NO_MATCH")]
        with lock:
            results.append((track, got))
            C.eprint("  补抓 %s / %s -> %s" % (track["title"], track["artist"],
                                              ",".join(str(b) for b, _ in got)))

    if todo:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            list(ex.map(worker, todo))

    # ── 3) 分桶 ──
    A, B, Cb, D, NM, EDGE = [], [], [], [], [], []
    for track, bs in results:
        vals = sorted({b for b, _ in bs if b})
        if not vals:
            NM.append({"track": track})
            continue
        solo = [b for b in vals if lo <= b <= hi]
        halves = [b for b in vals if hlo <= b <= hhi]
        liveonly = bool(solo) and all(v for b, v in bs if b in solo)
        entry = {"track": track, "bpm": vals, "src": "",
                 "live": liveonly, "delivered": is_delivered(track, delivered)}
        if solo and halves:
            entry["solo"], entry["halves"] = solo, halves
            B.append(entry)
        elif solo:
            entry["solo"] = solo
            A.append(entry)
        elif halves:
            Cb.append(entry)
        else:
            D.append(entry)
        edge = [b for b in vals
                if lo - 10 <= b < lo or hi < b <= hi + 5 or hlo + 1 <= b <= hhi + 3]
        if edge:
            EDGE.append({"track": track, "edge": edge, "allbpm": vals})

    payload = {"A": A, "B": B, "C": Cb, "D": D, "NM": NM, "EDGE": EDGE,
               "NTOTAL": len(lib), "SRC": os.path.basename(C.find_export(
                   sys.argv[1] if len(sys.argv) > 1 else None)),
               "LO": lo, "HI": hi, "HLO": hlo, "HHI": hhi}
    with open(C.RESULT_JSON, "w", encoding="utf-8") as fh:
        import json
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    def line(t):
        tail = " ".join(x for x in (t["year"], t["genre"]) if x)
        return "%s - %s（%s）" % (t["title"], t["artist"], tail) if tail \
            else "%s - %s" % (t["title"], t["artist"])

    print("资料库共 %d 首 | A 真快拍 %d | B 半速底 %d | C 仅双踩 %d | 出界 %d | 库内无数据 %d"
          % (len(lib), len(A), len(B), len(Cb), len(D), len(NM)))

    def dump(title, items, fmt):
        print("\n===== %s（%d 首）=====" % (title, len(items)))
        for e in items:
            print(fmt(e) + ("  ★此前已交付" if e["delivered"] else ""))

    dump("A 真快拍 %d-%d（库内无半速条目）" % (lo, hi), A,
         lambda e: "%s\t%s%s" % ("/".join(map(str, e["solo"])), line(e["track"]),
                                 "  ⚠仅 Live/版命中，不可用" if e["live"] else ""))
    dump("B 半速底 %d-%d（同曲另有半速）" % (lo, hi), B,
         lambda e: "%s（同曲 %s）\t%s%s" % ("/".join(map(str, e["solo"])),
                                            "/".join(map(str, e["halves"])),
                                            line(e["track"]),
                                            "  ⚠仅 Live/版" if e["live"] else ""))
    dump("C 仅双踩 %d-%d" % (hlo, hhi), Cb,
         lambda e: "%s→%d\t%s" % ("/".join(map(str, e["bpm"])), e["bpm"][0] * 2,
                                  line(e["track"])))
    print("\n===== E 擦边备查 =====")
    for e in sorted(EDGE, key=lambda x: x["edge"][0]):
        print("%s\t（全库值 %s）\t%s" % ("/".join(map(str, e["edge"])),
                                        ",".join(map(str, e["allbpm"])), line(e["track"])))
    print("\n===== D 出界备查（有数据但不满足）=====")
    for e in sorted(D, key=lambda x: x["track"]["artist"]):
        print("%s\t%s" % (",".join(map(str, e["bpm"])), line(e["track"])))
    print("\n===== N 库内无此条目（查不到 BPM）=====")
    for e in NM:
        print("%s - %s" % (e["track"]["title"], e["track"]["artist"]))

    C.eprint("已写 %s" % C.RESULT_JSON)


if __name__ == "__main__":
    main()
