#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hongqi-car-apk / _dirs.py —— 统一的目录解析（分发版：全程不出现个人路径）。

两种目录，各司其职：

    work/   中间产物：验证解包目录、未签名的 patch 中间件、临时下载的工具
    out/    交付物：各变体 APK、原版/ 源样本备份、安装与测试说明

锚点：始终跟着「当前工作目录 / 当前项目」走 —— 数据随项目，
不污染技能安装目录，也绝不写进别的项目、别的 agent 的工作目录。

解析顺序（work / out 各自独立，未显式指定时共用同一个「数据根」）：

    ① $HQCAR_WORK_DIR / $HQCAR_OUT_DIR   显式指定（命令行内联即可临时覆盖）
    ② <当前项目根>/.hongqi-car-apk/       ← 常规路径
    ③ <当前目录>/.hongqi-car-apk/         ← 无项目标记，但当前目录安全
    ④ <技能目录>/                         ← 当前目录不安全时的兜底

「项目根」= 从 $PWD 逐级向上第一个含 .git / AGENTS.md / package.json / pyproject.toml 的目录。

「不安全」= `/`、$HOME 根、临时目录（/tmp、$TMPDIR）、其他 agent 的家目录
（~/.dsh、~/.claude、~/.codex、~/.cursor、~/.gemini…），以及技能自身目录。
命中兜底时只会落在本技能自己的 work/ 与 out/，不会外溢。

排查当前解析到哪：  python3 scripts/_dirs.py
取单个目录：        python3 scripts/_dirs.py work | out
"""
import os
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

PROJECT_MARKERS = (".git", "AGENTS.md", "package.json", "pyproject.toml")
DATA_DIRNAME = ".hongqi-car-apk"

#: 其他 agent / 工具自己的家目录：绝不往里写数据
FOREIGN_AGENT_DIRS = (
    "~/.dsh", "~/.claude", "~/.codex", "~/.cursor", "~/.gemini",
    "~/.aider", "~/.continue", "~/.workbuddy",
    "~/.config/dsh", "~/.config/claude",
)


def _is_inside(path, parent):
    """子路径判断。两侧都取 realpath：macOS 上 /tmp 与 $TMPDIR 是符号链接
    （/var → /private/var），只比 abspath 会让临时目录护栏静默失效。"""
    path, parent = os.path.realpath(path), os.path.realpath(parent)
    return path == parent or path.startswith(parent + os.sep)


def is_unsafe(path):
    """该目录是否属于「不该落数据」的位置。"""
    d = os.path.realpath(path)
    if d == os.path.realpath(os.sep) or d == os.path.realpath(os.path.expanduser("~")):
        return True
    for t in ("/tmp", "/private/tmp", tempfile.gettempdir()):
        if _is_inside(d, t):
            return True
    for t in FOREIGN_AGENT_DIRS:
        if _is_inside(d, os.path.expanduser(t)):
            return True
    # 从技能目录内部运行：数据回技能自身，不落进 scripts/
    if _is_inside(d, SKILL_DIR):
        return True
    return False


def project_root(start=None):
    """从 start 逐级向上找项目根；找不到返回 None。"""
    d = os.path.abspath(start or os.getcwd())
    while True:
        if any(os.path.exists(os.path.join(d, m)) for m in PROJECT_MARKERS):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def data_root():
    """work/ 与 out/ 的公共锚点目录（见模块开头 ②③④）。"""
    cwd = os.path.abspath(os.getcwd())
    if not is_unsafe(cwd):
        root = project_root(cwd)
        if root and not is_unsafe(root):
            return os.path.join(root, DATA_DIRNAME)
        return os.path.join(cwd, DATA_DIRNAME)
    return SKILL_DIR


def _normalize(val):
    """把环境变量值规范化成绝对路径；只识别 `~` 与 `$HOME`，不执行 shell。"""
    home = os.path.expanduser("~")
    val = val.replace("${HOME}", home).replace("$HOME", home)
    return os.path.abspath(os.path.expanduser(val))


# ── 两种目录 ─────────────────────────────────────────────────────────────

def work_dir():
    """中间产物目录（解包验证 / 未签名中间件 / 工具缓存）。"""
    val = os.environ.get("HQCAR_WORK_DIR")
    if val:
        return _normalize(val)
    return os.path.join(data_root(), "work")


def out_dir():
    """交付物目录（各变体 APK、原版备份、安装说明）。"""
    val = os.environ.get("HQCAR_OUT_DIR")
    if val:
        return _normalize(val)
    return os.path.join(data_root(), "out")


def tools_dir():
    """工具缓存目录（缺 jar 时自动下载到这里，不写技能安装目录）。"""
    return os.path.join(work_dir(), "tools")


def ensure_dirs():
    """建好 work/ 与 out/（工具缓存按需另建），返回 (work, out)。"""
    w, o = work_dir(), out_dir()
    os.makedirs(w, exist_ok=True)
    os.makedirs(o, exist_ok=True)
    return w, o


def show_dirs():
    """排查用：打印本次实际解析结果。"""
    print("skill  : %s" % SKILL_DIR)
    print("script : %s" % SCRIPT_DIR)
    print("cwd    : %s" % os.getcwd())
    print("root   : %s" % (project_root() or "(无项目标记)"))
    print("work   : %s" % work_dir())
    print("out    : %s" % out_dir())


def main(argv):
    mode = argv[0] if argv else ""
    if mode == "work":
        print(work_dir())
    elif mode == "out":
        print(out_dir())
    elif mode == "tools":
        print(tools_dir())
    elif mode in ("", "-h", "--help", "show"):
        show_dirs()
    else:
        raise SystemExit("用法: _dirs.py [work|out|tools]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
