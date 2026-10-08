#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Apple Music 导出的资料库清单里，挑出还没抓过 BPM 的曲目，生成待抓候选。

    python3 lib_fetch.py [导出文件]

产出 work/cand_lib.txt（`歌名|歌手`），交给 fetch_bpm.py 抓取。
"""
import sys

import _common as C


def pending(lib, rows):
    """挑出库里「还没查过」的曲目，返回清理过的 (歌名, 艺人) 列表。

    三种已覆盖情形：整对精确命中、清理后命中、仅歌名命中。
    """
    done = {(C.norm(r["query_title"]), C.norm(r["query_artist"])) for r in rows}
    bytitle = {C.norm(r["query_title"]) for r in rows if r["bpm"]}

    pend, seen = [], set()
    for t in lib:
        title, artist = t["title"], t["artist"]
        ct, ca = C.clean_title(title), C.primary_artist(artist)
        if (C.norm(title), C.norm(artist)) in done or (C.norm(ct), C.norm(ca)) in done:
            continue
        if C.norm(title) in bytitle:
            continue
        key = (C.norm(ct), C.norm(ca))
        if not ct or key in seen:
            continue
        seen.add(key)
        pend.append((ct, ca))
    return pend


def main():
    C.ensure_dirs()
    src = C.find_export(sys.argv[1] if len(sys.argv) > 1 else None)
    lib = C.load_lib(src)
    rows = C.read_bpm_rows()
    pend = pending(lib, rows)
    C.write_candidates(C.CAND_LIB, pend, note="来自 Apple Music 资料库导出：%s" % src)
    print("资料库 %d 首 | 已查过 %d 首 -> 待抓 %d 首\n已写 %s"
          % (len(lib), len(lib) - len(pend), len(pend), C.CAND_LIB))


if __name__ == "__main__":
    main()
