#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清掉指定艺人的 NO_MATCH 占位行，让别名表更新后能重新抓取。

    python3 refetch.py                     # 只列出当前有占位行的艺人，不改文件
    python3 refetch.py 艺人甲 艺人乙 …      # 删掉这些艺人的占位行
    python3 refetch.py --all               # 删掉全部占位行（下次全量重查）

占位行（slug=NO_MATCH）表示「这首查过、没结果」。它会被增量抓取永久跳过，
所以修好 _aliases.py 之后必须先删掉对应占位行，否则修正永远不生效。
"""
import sys

import _common as C


def main():
    C.ensure_dirs()
    rows = C.read_bpm_rows()
    if not rows:
        raise SystemExit("还没有 %s" % C.BPM_CSV)

    placeholders = [r for r in rows if r["slug"] == "NO_MATCH"]
    if not placeholders:
        print("没有 NO_MATCH 占位行，无需处理。")
        return

    args = sys.argv[1:]
    if not args:
        artists = sorted({r["query_artist"] for r in placeholders if r["query_artist"]})
        print("共 %d 条占位行，涉及 %d 位艺人：" % (len(placeholders), len(artists)))
        for a in artists:
            n = sum(1 for r in placeholders if r["query_artist"] == a)
            print("  %-24s %d" % (a, n))
        print("\n指定要重查的艺人再跑一次：python3 refetch.py 艺人甲 艺人乙 …")
        return

    targets = None if args == ["--all"] else set(args)
    keep, drop = [], []
    for r in rows:
        if r["slug"] == "NO_MATCH" and (targets is None or r["query_artist"] in targets):
            drop.append((r["query_title"], r["query_artist"]))
            continue
        keep.append(r)

    if not drop:
        print("给定艺人没有占位行，文件未改动。")
        return
    C.write_bpm_rows(keep)
    print("剔除 %d 行，剩余 %d 行" % (len(drop), len(keep)))
    print("现在可以重跑：python3 fetch_bpm.py <含这些艺人的候选文件>")


if __name__ == "__main__":
    main()
