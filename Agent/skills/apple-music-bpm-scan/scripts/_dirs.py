#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apple-music-bpm-scan / _dirs.py —— 统一的目录解析（分发版：全程不出现个人路径）。

两种目录，各司其职：

    work/   中间数据：候选清单 cand_lib.txt、BPM 库 bpm_all.csv、
            请求缓存 bpm_cache/、中间结果 lib_result.json
    out/    交付物：最终 180-184bpm-scan.html / .txt 报告

锚点：始终跟着「当前工作目录 / 当前项目」走 —— 数据随项目，不污染技能的安装目录，
也绝不写进别的项目、别的 agent 的目录。

解析顺序（work / out 各自独立，未显式指定时共用同一个「数据根」）：

    ① $AMBS_WORK_DIR / $AMBS_OUT_DIR        显式指定（命令行内联即可临时覆盖）
    ② <技能目录>/config.env 里的同名键        永久配置（推荐）
    ③ <当前项目根>/.apple-music-bpm-scan/     ← 常规路径
    ④ <当前目录>/.apple-music-bpm-scan/       ← 无项目标记，但当前目录安全
    ⑤ <技能目录>/                            ← 当前目录不安全时的兜底

「项目根」= 从 $PWD 逐级向上第一个含 .git / AGENTS.md / package.json / pyproject.toml 的目录。

「不安全」= `/`、`$HOME` 根、临时目录（/tmp、$TMPDIR）、其他 agent 的家目录
（~/.dsh、~/.claude、~/.codex、~/.cursor、~/.gemini…），以及技能自身目录。
命中兜底时只会落在本技能自己的 work/ 与 out/，不会外溢。

⚠️ 不要写 ~/.zshrc：脚本是非交互调用，读不到它的导出；要固定路径请用 config.env。

排查当前解析到哪：  python3 scripts/_dirs.py
"""
import os
import re
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

PROJECT_MARKERS = (".git", "AGENTS.md", "package.json", "pyproject.toml")
PROJECT_DIRNAME = ".apple-music-bpm-scan"

#: 其他 agent / 工具自己的家目录：绝不往里写数据
FOREIGN_AGENT_DIRS = (
    "~/.dsh", "~/.claude", "~/.codex", "~/.cursor", "~/.gemini",
    "~/.aider", "~/.continue", "~/.config/dsh", "~/.config/claude",
)

# KEY=VALUE / KEY="VALUE" / KEY='VALUE'，可带行尾注释；不解析 $VAR 展开
_KV = re.compile(r"""^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$""")


# ── 配置文件 ──────────────────────────────────────────────────────────────

def config_path():
    """本次生效的配置文件路径。

    ① $AMBS_CONFIG 指定的路径
    ② <技能目录>/config.env      ← 默认位置，与技能放一起
    """
    env = os.environ.get("AMBS_CONFIG")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(SKILL_DIR, "config.env")


def _strip_value(raw):
    """解析 VALUE：先去引号（引号内可含 # 与空格），无引号才按 " #" 截注释。"""
    raw = raw.strip()
    if raw[:1] in ("\"", "'"):
        q = raw[0]
        end = raw.find(q, 1)
        if end != -1:                       # 取成对引号内部，忽略其后内容
            return raw[1:end]
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip()


def load_config(path=None):
    """读取配置文件的 KEY=VALUE（不执行 shell、不展开变量）。缺文件返回 {}。"""
    path = path or config_path()
    out = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = _KV.match(line)
                if m:
                    out[m.group(1)] = _strip_value(m.group(2))
    except (OSError, UnicodeDecodeError):
        return {}
    return out


def cfg(key):
    """配置文件里的单项；没有则 None。"""
    val = load_config().get(key)
    return val or None


def _normalize(val):
    """把配置/环境变量值规范化成绝对路径。

    只支持 `~` 与 `$HOME` / `${HOME}` 两种写法，其它 `$VAR` 一律不展开
    （不执行 shell），保持字面量，避免与 shell 侧结果分叉。
    """
    home = os.path.expanduser("~")
    val = val.replace("${HOME}", home).replace("$HOME", home)
    return os.path.abspath(os.path.expanduser(val))


# ── 安全护栏 ─────────────────────────────────────────────────────────────

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
    """work/ 与 out/ 的公共锚点目录（见模块开头 ③④⑤）。"""
    cwd = os.path.abspath(os.getcwd())
    if not is_unsafe(cwd):
        root = project_root(cwd)
        if root and not is_unsafe(root):
            return os.path.join(root, PROJECT_DIRNAME)
        return os.path.join(cwd, PROJECT_DIRNAME)
    return SKILL_DIR


# ── 两种目录 ─────────────────────────────────────────────────────────────

def work_dir():
    """中间数据目录（候选清单 / BPM 库 / 缓存 / 中间 JSON）。"""
    val = os.environ.get("AMBS_WORK_DIR") or cfg("AMBS_WORK_DIR")
    if val:
        return _normalize(val)
    return os.path.join(data_root(), "work")


def out_dir():
    """交付物目录（最终 HTML / TXT 报告）。"""
    val = os.environ.get("AMBS_OUT_DIR") or cfg("AMBS_OUT_DIR")
    if val:
        return _normalize(val)
    return os.path.join(data_root(), "out")


def export_dir():
    """Apple Music 导出文件的默认搜索位置（工作目录优先）。"""
    return work_dir()


def ensure_dirs():
    """建好 work/ 与 out/，返回 (work, out)。"""
    w, o = work_dir(), out_dir()
    os.makedirs(w, exist_ok=True)
    os.makedirs(o, exist_ok=True)
    return w, o


def show_dirs():
    """排查用：打印本次实际解析结果。"""
    cp = config_path()
    loaded = "已加载" if os.path.isfile(cp) else "未创建，用默认值"
    print("skill  : %s" % SKILL_DIR)
    print("script : %s" % SCRIPT_DIR)
    print("config : %s (%s)" % (cp, loaded))
    print("cwd    : %s" % os.getcwd())
    print("root   : %s%s" % (project_root() or "(无项目标记)", "" if is_unsafe(os.getcwd()) else ""))
    print("work   : %s" % work_dir())
    print("out    : %s" % out_dir())


if __name__ == "__main__":
    show_dirs()
