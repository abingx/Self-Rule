"""recipe-maker / _dirs.py —— 与 _dirs.sh 同一套目录约定（Python 侧）。

脚本：随技能自身目录（SCRIPT_DIR），不硬编码。
数据：跟着「当前项目」走 —— 优先复用 shell 侧已解析好的环境变量
（RECIPE_WORK_DIR / OUT），没有时按同一规则自行推导，保证两侧指向同一目录。

── 永久配置：把路径写进配置文件 ────────────────────────────────────────
    位置（依次尝试，命中即止）：
      ① $RECIPE_MAKER_CONFIG     显式指定别处的配置文件
      ② <技能目录>/config.env    默认位置，与技能放一起
    内容示例（shell 语法，zsh 侧也读同一个文件）：
        RECIPE_NOTE_DIR="/path/to/your/vault/your-recipes"
        RECIPE_WORK_DIR="/path/to/work"

    优先级：环境变量 > 配置文件 > 自动解析（与 _dirs.sh 完全一致）。

    配置文件只用简单的 KEY="VALUE" / KEY=VALUE 解析，**不执行任何 shell**，
    也不做变量展开 —— 它只是数据。

解析顺序：
    work_dir()  ① $RECIPE_WORK_DIR  ② $OUT  ③ 配置文件  ④ 项目根/.recipe-maker/work
                ⑤ cwd 不安全（/ 、$HOME 、临时目录）→ 技能内 work/
                ⑥ 其余 → $PWD/.recipe-maker/work
    note_dir()  ① $RECIPE_NOTE_DIR  ② 配置文件  ③ ~/Documents/RecipeNotes

「项目根」= 从 cwd 逐级向上第一个含 .git / AGENTS.md / package.json /
pyproject.toml 的目录。

⚠️ 不要写 ~/.zshrc：python 脚本由 bash 直接启动，读不到 .zshrc 的导出。
"""
import os
import re
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

_MARKERS = (".git", "AGENTS.md", "package.json", "pyproject.toml")

# KEY=VALUE / KEY="VALUE" / KEY='VALUE'，可带行尾注释；不解析 $VAR 展开
_KV = re.compile(r"""^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$""")


def config_path():
    """本次生效的配置文件路径（与 _dirs.sh 同一顺序）。

    ① $RECIPE_MAKER_CONFIG 指定的路径
    ② <技能目录>/config.env      ← 默认位置
    """
    env = os.environ.get("RECIPE_MAKER_CONFIG")
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
    """读取配置文件的 KEY=VALUE（不执行 shell，不展开变量）。缺文件返回 {}。"""
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


def _cfg(key):
    val = load_config().get(key)
    return val or None


def _normalize(val):
    """把配置值规范化成绝对路径。

    只支持 `~` 与 `$HOME` / `${HOME}` 两种写法（_dirs.sh 侧同口径）。
    其它 `$VAR` 一律**不展开**（不执行 shell），保持为字面量，避免两侧结果分叉。
    """
    val = val.replace("${HOME}", os.path.expanduser("~")).replace("$HOME", os.path.expanduser("~"))
    return os.path.abspath(os.path.expanduser(val))


def project_root(start=None):
    """从 start 逐级向上找项目根；找不到返回 None。"""
    d = os.path.abspath(start or os.getcwd())
    while True:
        if any(os.path.exists(os.path.join(d, m)) for m in _MARKERS):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _unsafe(path):
    d = os.path.abspath(path)
    if d == os.path.abspath(os.sep) or d == os.path.expanduser("~"):
        return True
    for t in ("/tmp", "/private/tmp", tempfile.gettempdir()):
        t = os.path.abspath(t)
        if d == t or d.startswith(t + os.sep):
            return True
    return False


def work_dir():
    """中间数据目录（mp4 / 直链 / 元信息 / 字幕 / 抽帧）。"""
    env = os.environ.get("RECIPE_WORK_DIR") or os.environ.get("OUT") or _cfg("RECIPE_WORK_DIR")
    if env:
        return _normalize(env)
    root = project_root()
    if root:
        return os.path.join(root, ".recipe-maker", "work")
    cwd = os.getcwd()
    if _unsafe(cwd):
        return os.path.join(SKILL_DIR, "work")
    return os.path.join(os.path.abspath(cwd), ".recipe-maker", "work")


def note_dir():
    """菜谱 md 落盘目录。"""
    env = os.environ.get("RECIPE_NOTE_DIR") or _cfg("RECIPE_NOTE_DIR")
    if env:
        return _normalize(env)
    return os.path.join(os.path.expanduser("~"), "Documents", "RecipeNotes")


if __name__ == "__main__":
    cfg = config_path()
    exists = os.path.isfile(cfg)
    for k, v in (("skill", SKILL_DIR), ("script", SCRIPT_DIR),
                 ("config", f"{cfg} ({'已加载' if exists else '未创建，用默认值'})"),
                 ("work", work_dir()), ("note", note_dir())):
        print(f"{k:<7}: {v}")
