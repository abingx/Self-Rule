#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 BPM 的唯一入口：增量处理 bpm_all.csv 里还没有的候选并合并回去。

    python3 fetch_bpm.py                 # 默认读 work/cand_lib.txt
    python3 fetch_bpm.py a.txt b.txt     # 可传多个候选文件
    python3 fetch_bpm.py --force         # 忽略「已抓过」记录，候选全部重跑
                                         # （仍命中磁盘缓存，不产生新请求）
    python3 fetch_bpm.py --all           # 连库内已有曲目一起整体重抓
                                         # （别名表大改后用，最慢）

⚠️ 不传候选文件时按 DEFAULT_FILES 顺序找；若都不存在会直接报错退出，
   绝不会回头重抓整个 bpm_all.csv。

抓取内核在 songbpm.py（库，无入口）；本文件只负责候选筛选与结果合并。
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import _common as C
import songbpm as F

#: 不显式传参时按顺序读这些候选文件（cand_lib.txt 由 lib_fetch.py 生成）
DEFAULT_FILES = ("cand_lib.txt", "candidates.txt", "candidates2.txt", "candidates3.txt")


def main():
    C.ensure_dirs()
    argv = sys.argv[1:]
    args = [a for a in argv if not a.startswith("--")]
    force = "--force" in argv
    allrows = "--all" in argv

    rows = C.read_bpm_rows()
    if allrows:
        old_rows, done = [], set()
    elif force:
        old_rows, done = [], set()
        print("force 模式：重跑全部候选（命中缓存，不产生新请求）")
    else:
        old_rows = [[r[h] for h in C.HEADER] for r in rows]
        done = {(r["query_title"], r["query_artist"]) for r in rows}

    if allrows:
        # 把库内已有的曲目整体重抓一遍（保持原有出现顺序），
        # 用于别名表大改后刷新全部结果。全部命中缓存时几乎不产生新请求。
        cands_all, seen = [], set()
        for r in rows:
            k = (r["query_title"], r["query_artist"])
            if k not in seen:
                seen.add(k)
                cands_all.append(k)
        if not cands_all:
            raise SystemExit("%s 里没有可重抓的曲目。" % C.BPM_CSV)
        print("--all 模式：重抓库内全部 %d 首（命中缓存则不产生新请求）" % len(cands_all))
    elif args:
        cands_all = C.read_candidates(*args, strict=True)
    else:
        cands_all = C.read_candidates(*[os.path.join(C.WORK, f) for f in DEFAULT_FILES])
        if not cands_all:
            raise SystemExit(
                "没有候选文件。请先跑 lib_fetch.py 生成 %s，\n"
                "或显式指定： python3 fetch_bpm.py /path/to/候选.txt"
                % os.path.join(C.WORK, "cand_lib.txt"))

    cands = [(t, a) for t, a in cands_all if (t, a) not in done]
    print("新增待抓 %d 首（库内已有 %d 首）" % (len(cands), len(done)))
    if not cands:
        return

    total = len(cands)
    tasks = [(i, total, t, a) for i, (t, a) in enumerate(cands, 1)]
    new_rows = []
    with ThreadPoolExecutor(max_workers=F.WORKERS) as ex:
        for task, out in zip(tasks, ex.map(F.process, tasks)):
            if not out:
                # 记一条占位行表示「已查无匹配」，否则后续每轮都会无休止重抓；
                # 别名表修正后需用 refetch.py 删掉它才会重抓。
                new_rows.append([task[2], task[3], "", "", "", "", 0, "", "NO_MATCH"])
            new_rows.extend(out)

    C.write_bpm_rows(old_rows + new_rows)
    print("wrote %s  %d rows (+%d)" % (C.BPM_CSV, len(old_rows) + len(new_rows), len(new_rows)))


if __name__ == "__main__":
    main()
