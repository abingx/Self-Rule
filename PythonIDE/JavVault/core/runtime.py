# -*- coding: utf-8 -*-
"""后台任务调度：图片缓存刷新、详情抓取、播放请求，全部在主线程 Timer 中安全提交。"""

import threading
import time

import appui

from core import cache
from core import state as st
from core.log import log
from parser.detail import fetch_detail

# 详情抓取请求/结果（由后台线程写入，主线程 _sync_dirty 提交）
_DETAIL_REQUEST = None     # 待抓取详情链接
_DETAIL_READY = None       # 已抓取的详情 dict
_DETAIL_ERROR = False
_DETAIL_SEQ = 0            # 使旧详情线程的结果失效

# 播放请求（后台抓取成功后由主线程提交给播放器）
_PLAY_REQUEST = None       # (url, title, source)
_PLAY_ERROR = ""           # 后台抓取失败时的提示

# 图片刷新：下载完成后需静默多久才整树重建（去抖，防止闪烁）
_LAST_IMG_RELOAD = 0.0
IMG_SILENCE_INTERVAL = 0.5
IMG_MAX_RELOAD_INTERVAL = 2.0

_started = False


def request_detail(link):
    """登记详情抓取请求并启动后台线程。"""
    global _DETAIL_REQUEST, _DETAIL_READY, _DETAIL_ERROR, _DETAIL_SEQ
    _DETAIL_SEQ += 1
    seq = _DETAIL_SEQ
    _DETAIL_REQUEST = link
    _DETAIL_READY = None
    _DETAIL_ERROR = False
    threading.Thread(target=_detail_worker, args=(link, seq), daemon=True).start()


def _detail_worker(link, seq):
    """后台详情抓取线程（不会阻塞主循环）。"""
    global _DETAIL_READY, _DETAIL_ERROR
    if not link:
        return
    try:
        result = fetch_detail(link)
        if seq == _DETAIL_SEQ:
            _DETAIL_READY = result
    except Exception:
        if seq == _DETAIL_SEQ:
            _DETAIL_ERROR = True


def set_play_request(url, title, source):
    """后台线程登记一条待播放链接（成功路径）。"""
    global _PLAY_REQUEST, _PLAY_ERROR
    _PLAY_REQUEST = (url, title, source)
    _PLAY_ERROR = ""


def set_play_error(message):
    """后台线程登记一条播放失败提示。"""
    global _PLAY_REQUEST, _PLAY_ERROR
    _PLAY_REQUEST = None
    _PLAY_ERROR = message


def play_url(url, title="", referer=None, source=""):
    """直接播放 URL（与原始 JS play(url) 一致）。source 标记当前来源用于按键高亮。"""
    log("play: " + str(title) + " -> " + str(url)[:120])
    st.state.panel = url
    st.state.panel_title = title
    st.state.play = source
    st.state.status = ""
    st.state.reload += 1


def _sync_dirty():
    """主线程周期任务：图片刷新 + 播放请求 + 详情提交。"""
    global _PLAY_REQUEST, _PLAY_ERROR, _LAST_IMG_RELOAD
    # 图片刷新用"去抖"：下载高峰期间不刷新，等这一批全部下载完、静默一段
    # 时间后再整树重建一次，避免多张封面连续完成导致列表不停闪烁。
    if cache.is_dirty():
        now = time.time()
        quiet = now - cache.last_activity() >= IMG_SILENCE_INTERVAL
        overdue = now - _LAST_IMG_RELOAD >= IMG_MAX_RELOAD_INTERVAL
        if quiet or overdue:
            cache.clear_dirty()
            _LAST_IMG_RELOAD = now
            st.state.reload += 1
    # 提交后台线程抓到的待播放链接
    if _PLAY_REQUEST:
        url, title, source = _PLAY_REQUEST
        _PLAY_REQUEST = None
        st.state.status = ""
        play_url(url, title, source=source)
    elif _PLAY_ERROR:
        st.state.status = _PLAY_ERROR
        _PLAY_ERROR = ""
        st.state.reload += 1
    _commit_detail()


def _commit_detail():
    """主线程 Timer：若后台详情已就绪则提交到 state。"""
    global _DETAIL_READY, _DETAIL_ERROR, _DETAIL_REQUEST
    if _DETAIL_READY is not None:
        d = _DETAIL_READY
        _DETAIL_READY = None
        log("detail ready code=" + str(d.get("code")))
        # 若用户已切换/关闭，则不强制覆盖当前占位
        cur = st.state.detail
        req_link = _DETAIL_REQUEST
        _DETAIL_REQUEST = None
        if cur and cur.get("link") != d.get("link"):
            return
        if d.get("error"):
            if cur and cur.get("_loading"):
                cur["_loading"] = False
                cur["error"] = True
            st.state.reload += 1
            return
        # 详情页解析不出番号时，用占位的番号兜底（保证收藏/按钮状态一致）
        if not d.get("code") and cur and cur.get("code"):
            d["code"] = cur["code"]
        if not d.get("cover") and cur and cur.get("cover"):
            d["cover"] = cur["cover"]
        st.state.detail = d
        # 详情图用 priority：插入队首，保证立刻下载，不被首页封面队列挤掉
        for a in d["actresses"]:
            cache.request_img(a["img"], priority=True)
        for s in d["samples"]:
            cache.request_img(s["img"], priority=True)
            cache.request_img(s["link"], priority=True)   # 大图也缓存，供查看大图用
        cache.request_img(d["cover"], priority=True)
        st.state.reload += 1
    elif _DETAIL_ERROR:
        _DETAIL_ERROR = False
        _DETAIL_REQUEST = None
        log("detail fetch error")
        cur = st.state.detail
        if cur and cur.get("_loading"):
            cur["_loading"] = False
            cur["error"] = True
        st.state.reload += 1


def reset_pending():
    """冷启动清空所有后台待办。"""
    global _DETAIL_REQUEST, _DETAIL_READY, _DETAIL_ERROR, _DETAIL_SEQ, _PLAY_REQUEST, _PLAY_ERROR
    _DETAIL_SEQ += 1
    _DETAIL_REQUEST = None
    _DETAIL_READY = None
    _DETAIL_ERROR = False
    _PLAY_REQUEST = None
    _PLAY_ERROR = ""


def init_background():
    """启动图片下载线程与主线程刷新 Timer（只执行一次）。"""
    global _started
    if _started:
        return
    _started = True
    # 多线程并发下载 + 主线程周期刷新
    cache.start_workers()
    appui.Timer(interval=0.4, action=_sync_dirty).start()
