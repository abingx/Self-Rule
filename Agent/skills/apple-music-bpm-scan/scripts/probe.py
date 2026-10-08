#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人工核查：把若干查询的全部 songbpm 结果打印出来，眼检命中情况。

    python3 probe.py "艺人 歌名" ["艺人 歌名" ...]
    python3 probe.py - < queries.txt        # 每行一条查询

用途：判断某首/某艺人到底是「库里真没有」还是「别名写错导致 0 命中」。
songbpm 每次搜索只返回 5 条，所以要把 5 条全看一遍再下结论，
并确认命中的是原唱而不是翻唱。
"""
import sys

import _common as C
import songbpm as F


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        raise SystemExit(
            "用法：python3 probe.py \"艺人 歌名\" [\"艺人 歌名\" ...]\n"
            "      python3 probe.py - < queries.txt      # 每行一条查询")
    if args == ["-"]:
        queries = [l.strip() for l in sys.stdin if l.strip()]
    else:
        queries = args

    lo, hi = C.bpm_range()
    hlo, hhi = C.half_range()
    for q in queries:
        res = F.parse(F.fetch(q))
        print("=== %s  -> %d 条" % (q, len(res)))
        for r in res:
            hit = lo <= r["bpm"] <= hi or hlo <= r["bpm"] <= hhi
            if not F.artist_match(q.split(" ", 1)[0], r["artist"]):
                hit = False
            print("    %-42s %-28s %3d  %s%s" % (r["title"][:42], r["artist"][:28],
                                                 r["bpm"], r["dur"],
                                                 "  ★" if hit else ""))
        if not res:
            print("    （0 结果：可能是别名问题，也可能是库里真的没有）")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
