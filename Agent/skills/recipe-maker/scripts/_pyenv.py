"""recipe-maker / _pyenv.py —— Python 解释器自检与自动切换。

背景（WorkBuddy 隔离 runtime 实测）:
    `python3` 在 PATH 里可能解析到隔离 runtime（如
    `~/.workbuddy/binaries/python/versions/3.13.12/bin/python3`），
    它**没装** faster-whisper / rapidocr 等依赖；依赖实际装在
    `~/.workbuddy/binaries/python/envs/default/`。

用法（在 import 重依赖之前）:
    import _pyenv
    _pyenv.ensure(("faster_whisper", "imageio_ffmpeg"), "faster-whisper imageio-ffmpeg")

ensure() 会：
    1. 当前解释器能 import 全部模块 → 直接返回，什么都不做；
    2. 否则按候选顺序找一个能 import 的解释器 → **exec 自己换过去**（透明重启）；
    3. 都找不到 → 打印当前解释器路径 + 尝试过的候选 + 可复制的安装命令后退出。

候选顺序：
    ① $RECIPE_PYTHON（显式指定，最高优先级）
    ② <技能目录>/config.env 里的 RECIPE_PYTHON
    ③ ~/.workbuddy/binaries/python/envs/default/bin/python
    ④ PATH 上的 python3 / python
"""
import os
import shutil
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
WORKBUDDY_PY = os.path.expanduser(
    "~/.workbuddy/binaries/python/envs/default/bin/python"
)
# 已经换过一次就别再换，避免候选互相 exec 死循环
_GUARD = "RECIPE_PYENV_SWITCHED"


# 子进程探测用：真实 import 比 find_spec 可靠（find_spec 在沙箱/冷启动下偶发误判）
_PROBE = (
    "import importlib, sys\n"
    "bad=[]\n"
    "for m in sys.argv[1:]:\n"
    "    try:\n"
    "        importlib.import_module(m)\n"
    "    except BaseException:\n"
    "        bad.append(m)\n"
    "print(' '.join(bad))\n"
)


def _run_probe(python, modules, attempts=6):
    """跑探测子进程；返回 CompletedProcess 或 None（全部尝试失败）。

    失败分两类，都返回 None（由调用方保守处理）：
      ① 沙箱 / 隐私保护让某些路径下的可执行文件无法 spawn（实测 VS Code 沙箱下
         `~/.workbuddy/.../python` 直接 OSError，外层终端却可以）；
      ② 首次 fork 偶发失败。
    多试几次 + 退避能消掉 ②，消不掉 ① —— 所以候选探测失败**不等于**它没装依赖。
    """
    last_err = None
    for i in range(attempts):
        try:
            out = subprocess.run(
                [python, "-c", _PROBE, *modules],
                capture_output=True, text=True, timeout=120,
            )
            if out.returncode == 0:
                return out
            last_err = out.stderr.strip()[-200:] or f"rc={out.returncode}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if i:
            time.sleep(0.15)
    if os.environ.get("RECIPE_PYENV_DEBUG"):
        print(f"[pyenv] 探测失败 {python}: {last_err}", file=sys.stderr)
    return None


def _missing(modules):
    """返回当前解释器缺失的模块名列表（用子进程探测，避免污染本进程）。"""
    out = _run_probe(sys.executable, modules)
    if out is None:
        return list(modules)   # 探测彻底失败：保守判定为缺失
    return out.stdout.split()


def _same_interpreter(p):
    """p 是否就是「当前这个解释器环境」（排除它做候选没意义）。

    ⚠️ 不能只用 realpath 比较：venv 的 `bin/python` 通常是指向同一份
    CPython 二进制的软链（`bin/python -> bin/python3 -> .../python3.13`），
    realpath 与隔离 runtime 的 `sys.executable` **完全相同**，但 venv 有
    自己的 site-packages —— 依赖就装在那儿。实测这正是「候选为空、
    明明装了依赖却报缺少依赖」的根因（2026-10-19）。

    判据（纯字符串，不读文件系统元数据，沙箱下也稳）：
      1. abspath 相同            → 是同一个
      2. realpath 不同           → 不是同一个
      3. realpath 相同           → 再看推导出的 venv prefix 是否等于 sys.prefix
    """
    ap = os.path.abspath(p)
    if ap == os.path.abspath(sys.executable):
        return True
    if os.path.realpath(p) != os.path.realpath(sys.executable):
        return False
    cand_prefix = os.path.dirname(os.path.dirname(ap))
    return os.path.realpath(cand_prefix) == os.path.realpath(sys.prefix)


def _candidates():
    """候选解释器（已去重、排除当前解释器环境）。

    ⚠️ 不在这里用 os.path.isfile / os.access 过滤：沙箱或隐私保护下
    `~/.workbuddy` 这类目录的元数据可能读不到（isfile 返回 False），
    但**直接执行仍然成功**。所以只做路径去重，能不能用交给 _missing_on 实跑验证。
    """
    seen, out = set(), []

    def add(p):
        if not p:
            return
        p = os.path.abspath(os.path.expanduser(p))
        if p in seen:
            return
        if _same_interpreter(p):
            return
        seen.add(p)
        out.append(p)

    add(os.environ.get("RECIPE_PYTHON"))
    try:
        import _dirs  # 同目录；读 config.env 里的 RECIPE_PYTHON

        add(_dirs.load_config().get("RECIPE_PYTHON"))
    except Exception:
        pass
    add(WORKBUDDY_PY)
    add(shutil.which("python3"))
    add(shutil.which("python"))
    return out


def ensure(modules, pip_names):
    """确保当前解释器能 import `modules`；不能就 exec 换到能用的那个。

    modules   : 必须可用的模块名元组
    pip_names : 缺依赖时提示的 pip 包名（空格分隔）
    """
    bad = _missing(modules)
    if not bad:
        return

    if not os.environ.get(_GUARD):
        cands = _candidates()
        # 第一轮：探测通过的直接换过去（最可靠）
        for cand in cands:
            if _missing_on(cand, bad) == []:
                os.environ[_GUARD] = "1"
                os.execv(cand, [cand, *sys.argv])
        # 第二轮：探测全部失败（多为沙箱拦 spawn，而不是真缺依赖）→ 盲试一次。
        # 换过去后如果还是缺依赖，新进程里 _GUARD 已置位，会直接报错，不会死循环。
        for cand in cands:
            os.environ[_GUARD] = "1"
            try:
                os.execv(cand, [cand, *sys.argv])
            except OSError:
                continue          # 这个候选根本起不来，试下一个
        os.environ.pop(_GUARD, None)
        # 全部候选都起不来 —— 落到下面报错

    lines = [
        f"缺少依赖 {', '.join(bad)}",
        f"  当前解释器 : {sys.executable}",
        "  尝试过的解释器（都不满足）:",
    ]
    lines += [f"    - {c}" for c in _candidates()] or ["    （无可用候选）"]
    lines += [
        f"  装到当前解释器: {sys.executable} -m pip install {pip_names}",
        f"  或指定一个已装好的: RECIPE_PYTHON=/path/to/python python3 {sys.argv[0]} ...",
        "  也可写进 <技能目录>/config.env: RECIPE_PYTHON=\"/path/to/python\"",
    ]
    sys.exit("\n".join(lines))


def _missing_on(python, modules):
    """探测指定解释器缺哪些模块；返回缺失列表（空 = 全都有）。"""
    out = _run_probe(python, modules)
    if out is None:
        return list(modules)   # 探测彻底失败：保守判定为缺失
    return out.stdout.split()
