# -*- coding: utf-8 -*-
"""应用内日志（便于 iOS 上无控制台时排错）。"""

# 环形缓冲：最多保留 300 条，超出后丢弃最早 100 条
LOG = []


def log(msg):
    try:
        LOG.append(str(msg))
        if len(LOG) > 300:
            del LOG[:100]
    except Exception:
        pass