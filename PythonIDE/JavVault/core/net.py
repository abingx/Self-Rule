# -*- coding: utf-8 -*-
"""通用 HTTP 网络层。"""
import network

from core.config import BASE, HEADERS
from core.log import log


def get(url, cookie_all=False):
    """GET 请求返回文本；失败返回空串。cookie_all 时带上 existmag=all 显示全量。"""
    headers = dict(HEADERS)
    if cookie_all:
        headers["Cookie"] = "existmag=all"
    try:
        resp = network.get(url, headers=headers, timeout=15)
        if resp and resp.ok:
            return resp.text
    except Exception as e:
        log("get err " + url[:80] + " : " + str(e))
    return ""


def fill_base(src):
    """相对路径补全为完整 URL（已是 http 开头则原样返回）。"""
    if src.startswith("http"):
        return src
    return BASE + src


def is_video_url(url):
    """探测 URL 是否指向可直接播放的视频（用于 Missav 预览校验）。"""
    try:
        with network.stream("GET", url, headers=dict(HEADERS), timeout=12) as resp:
            if not resp.ok:
                return False
            h = resp.headers or {}
            ct = (h.get("content-type") or h.get("Content-Type") or "").lower()
            return "video/mp4" in ct or "application/octet-stream" in ct
    except Exception as e:
        log("is_video err: " + str(e))
        return False