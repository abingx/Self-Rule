#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""依赖自举：让脚本无需外部环境配置即可找到 opencc。

技能自带 `_pylibs/`（opencc-python-reimplemented）。任何脚本在
`from opencc import OpenCC` 之前先 `import _boot`，即可在系统解释器、
DSH runtime、homebrew python3 之间通用，无需 PYTHONPATH。

查找顺序：
  1. 本目录 _pylibs/（技能自带，最稳）
  2. 已装好的 opencc（交给正常 import）
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.join(_HERE, '_pylibs')


def ensure():
    """确保 import opencc 可用；不可用则报出可操作的提示。"""
    try:
        import opencc  # noqa: F401
        return
    except ImportError:
        pass
    if os.path.isdir(_BUNDLED) and _BUNDLED not in sys.path:
        sys.path.insert(0, _BUNDLED)
    try:
        import opencc  # noqa: F401
    except ImportError:
        raise SystemExit(
            '缺少 opencc。技能自带依赖应在 %s，但导入失败。\n'
            '可重新安装：\n'
            '  <python> -m pip install --target %s opencc-python-reimplemented\n'
            % (_BUNDLED, _BUNDLED))


ensure()
