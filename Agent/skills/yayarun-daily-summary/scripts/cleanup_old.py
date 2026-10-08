#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理 ~/Documents/YaYaRun 下超过 N 天的卡片文件。

用法：
    python3 cleanup_old.py --days 7                  # 默认 dry-run，只列出
    python3 cleanup_old.py --days 7 --apply          # 真删
    python3 cleanup_old.py --days 7 --trash          # 移到废纸篓而不是永久删除（macOS）
    python3 cleanup_old.py --days 7 --all            # 明确要清理目录里所有顶层文件时才用

判断依据是**修改时间(mtime)**，不是文件名里的日期 —— 文件可能被重新生成过。

设计取向：宁可少删不可错删。
  - 默认 dry-run，必须显式 --apply 才动手
  - 默认只处理文件名以 run-summary- 开头的文件（本链路产物）；要清全部顶层文件须显式 --all
  - 只清理目标目录**顶层**，不递归、不碰子目录、隐藏文件与符号链接
  - --days 不得小于 1；拒绝对 / 与家目录本身下手（防止 --dir 误传）
  - 没有任何文件超期时**明确报告「无文件超期」**，且不算失败（退出码 0）

退出码：0=正常（含无文件可删） / 1=出错
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

DEFAULT_PREFIX = "run-summary-"


def human_age(seconds: float) -> str:
    days = seconds / 86400
    if days < 1:
        return f"{seconds / 3600:.1f} 小时"
    return f"{days:.1f} 天"


def main():
    ap = argparse.ArgumentParser(description="清理超期卡片文件")
    ap.add_argument("--days", type=float, default=7, help="保留天数阈值，默认 7")
    ap.add_argument("--dir", default="~/Documents/YaYaRun", help="目标目录")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX,
                    help=f"只清理此文件名前缀，默认 {DEFAULT_PREFIX}")
    ap.add_argument("--all", action="store_true", help="不限前缀，清理顶层所有普通文件")
    ap.add_argument("--trash", action="store_true", help="移到 ~/.Trash 而非永久删除")
    ap.add_argument("--apply", action="store_true", help="真正删除（默认仅预览）")
    ap.add_argument("--quiet", action="store_true", help="精简输出")
    args = ap.parse_args()

    if args.days < 1:
        print("[失败] --days 不得小于 1（0 或负数会把刚生成的卡片也判为超期）", file=sys.stderr)
        return 1
    target = Path(os.path.expanduser(args.dir)).resolve()
    if not target.is_dir():
        print(f"[失败] 目录不存在：{target}", file=sys.stderr)
        return 1
    if target in (Path("/"), Path.home().resolve()):
        print(f"[失败] 拒绝清理 {target}：目录参数看起来不对", file=sys.stderr)
        return 1
    prefix = "" if args.all else args.prefix

    cutoff = time.time() - args.days * 86400
    expired, kept = [], []

    # 只扫顶层文件；不递归，天然避开子目录
    for item in sorted(target.iterdir()):
        if item.is_symlink() or not item.is_file() or item.name.startswith("."):
            continue                                   # 符号链接 / 子目录 / 隐藏文件一律不碰
        if prefix and not item.name.startswith(prefix):
            continue
        try:
            mtime = item.stat().st_mtime
        except OSError as exc:
            print(f"[跳过] {item.name}: {exc}", file=sys.stderr)
            continue
        (expired if mtime < cutoff else kept).append((item, mtime))

    print(f"目录 {target}")
    scope = "全部顶层文件" if args.all else f"前缀 {prefix}"
    print(f"阈值 {args.days:g} 天（以修改时间为准）| 范围 {scope} | 命中 {len(expired) + len(kept)} 个文件")

    if not expired:
        print(f"\n无文件超期 —— 最旧的仍在 {args.days:g} 天窗口内，本次不删除任何文件。")
        if not args.quiet and kept:
            oldest = min(kept, key=lambda x: x[1])
            print(f"  最旧：{oldest[0].name}（{human_age(time.time() - oldest[1])}前）")
        return 0

    print(f"\n超期 {len(expired)} 个：")
    for path, mtime in expired:
        print(f"  {'删除' if args.apply else '待删'}  {path.name}  "
              f"(修改于 {human_age(time.time() - mtime)}前)")

    if not args.apply:
        print("\n[dry-run] 未删除任何文件。确认无误后加 --apply 执行。")
        return 0

    removed = 0
    trash = Path.home() / ".Trash"
    for path, _ in expired:
        try:
            if args.trash and trash.is_dir():
                dest = trash / path.name
                if dest.exists():                      # 废纸篓里重名则加时间戳，绝不覆盖
                    dest = trash / f"{path.stem}-{int(time.time())}{path.suffix}"
                shutil.move(str(path), str(dest))
            else:
                path.unlink(missing_ok=True)           # 扫描后文件被别处删掉不算失败
            removed += 1
        except OSError as exc:
            print(f"[失败] 无法删除 {path.name}: {exc}", file=sys.stderr)

    print(f"\n已{'移入废纸篓' if args.trash else '删除'} {removed}/{len(expired)} 个文件。")
    if kept and not args.quiet:
        print(f"保留 {len(kept)} 个仍在窗口内的文件。")
    return 0 if removed == len(expired) else 1


if __name__ == "__main__":
    sys.exit(main())