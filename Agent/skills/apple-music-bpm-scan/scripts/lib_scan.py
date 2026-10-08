#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资料库 vs BPM 库：逐首判定是否满足目标区间，并分桶打印。

    python3 lib_scan.py [导出文件]

分桶（目标区间默认 180-184，半速 90-92）：
    A  只有单拍目标区间、且同曲无半速条目 → 真快拍，直接跟跑
    B  目标区间 **且** 同曲另有半速条目   → 半速底，双踩更稳
    C  只有半速条目                       → 双踩（实战大多数）
    X  有数据但不满足                     → 出界备查

中间结果写 work/lib_recs.json，供后续分析复用。
"""
import json
import sys

import _common as C


def index_bpm(rows):
    """把 BPM 库建成两张索引：整对精确 / 仅歌名。"""
    exact, bytitle = {}, {}
    for r in rows:
        if not r["bpm"]:
            continue
        exact.setdefault((C.norm(r["query_title"]), C.norm(r["query_artist"])), []).append(r)
        bytitle.setdefault(C.norm(r["query_title"]), []).append(r)
    return exact, bytitle


def lookup(track, exact, bytitle):
    """三级回退匹配：整对精确 → 清理后整对 → 仅歌名。"""
    title, artist = track["title"], track["artist"]
    ct, ca = C.clean_title(title), C.primary_artist(artist)
    return (exact.get((C.norm(title), C.norm(artist)))
            or exact.get((C.norm(ct), C.norm(ca)))
            or bytitle.get(C.norm(title))
            or bytitle.get(C.norm(ct))
            or [])


def classify(rec):
    """按 BPM 集合分桶；非录音室版本单独标记。"""
    lo, hi = C.bpm_range()
    hlo, hhi = C.half_range()
    singles = [b for b in rec["bpm"] if lo <= b <= hi]
    halves = [b for b in rec["bpm"] if hlo <= b <= hhi]
    if singles and halves:
        return "B"
    if singles:
        return "A"
    if halves:
        return "C"
    return "X"


def main():
    C.ensure_dirs()
    lib = C.load_lib(sys.argv[1] if len(sys.argv) > 1 else None)
    rows = C.read_bpm_rows()
    exact, bytitle = index_bpm(rows)

    recs = []
    for track in lib:
        cand = lookup(track, exact, bytitle)
        studio = [r for r in cand if not r["version"]]
        live = [r for r in cand if r["version"]]
        pool = studio or live          # 有录音室版就只认录音室版
        t = dict(track)
        t["bpm"] = sorted({int(r["bpm"]) for r in pool})
        t["allbpm"] = sorted({int(r["bpm"]) for r in cand})
        t["only_live"] = bool(cand) and not studio
        t["src"] = pool[0]["found_artist"] if pool else ""
        t["n"] = len(cand)
        recs.append(t)

    lo, hi = C.bpm_range()
    buckets = {"A": [], "B": [], "C": [], "X": []}
    for r in recs:
        buckets[classify(r)].append(r)

    print("资料库 %d 首 | 有 BPM 数据 %d 首 | 目标区间 %d-%d BPM"
          % (len(recs), sum(1 for r in recs if r["bpm"]), lo, hi))
    for tag, name in [("A", "A 真快拍：命中 %d-%d，库内无半速条目" % (lo, hi)),
                      ("B", "B 半速底：命中 %d-%d 且同曲有半速条目（双踩更稳）" % (lo, hi)),
                      ("C", "C 双踩：仅半速条目（跑时按 %d-%d 双踩）" % (lo, hi))]:
        print("\n===== %s（%d 首）=====" % (name, len(buckets[tag])))
        for r in sorted(buckets[tag], key=lambda x: (x["artist"], x["title"])):
            mark = "  [仅 Live/版命中]" if r["only_live"] else ""
            print("%s\t%s\t%s\t%s\t%s\t%s%s"
                  % ("/".join(map(str, r["bpm"])) or "-", r["title"], r["artist"],
                     r["genre"], r["year"], r["dur"], mark))
    print("\n===== X 出界备查（有数据但不满足）=====")
    for r in sorted(buckets["X"], key=lambda x: (x["artist"], x["title"])):
        if r["bpm"]:
            print("%s\t%s\t%s\t%s" % ("/".join(map(str, r["bpm"])), r["title"],
                                      r["artist"], r["dur"]))

    json.dump(recs, open(C.LIB_RECS_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    C.eprint("已写 %s" % C.LIB_RECS_JSON)


if __name__ == "__main__":
    main()
