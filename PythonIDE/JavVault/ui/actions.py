# -*- coding: utf-8 -*-
"""业务动作层：打开详情、播放、复制、收藏等（与视图解耦，可被任意页面复用）。"""

import clipboard
import shortcuts
import threading
import time
from urllib.parse import quote

from core import runtime
from core import state as st
from core.log import log
from core.net import is_video_url
from data import shelf
from parser.sources import fetch_avgle, fetch_jable


def record_nav_action():
    """任何点击引起的导航/面板转场前调用：开启转场静默窗，
    期间所有后台定时刷新（图片去抖、详情提交、列表提交）暂缓，
    使快速点击 / 跨 tab 点击也不会有 reload 打断转场动画。"""
    runtime.note_nav_action()


def open_detail(movie, path=None):
    """打开影片详情：登记后台抓取并在给定导航栈内 push 详情页。

    movie: 必含 code / img / link；path 缺省用影片 tab 的导航栈。
    上次已抓过同一番号、或后台已抓完但用户已返回的，直接复用数据秒开，
    不再发请求。
    """
    log("open_detail: " + movie["link"])
    st.state.detail_thumb = movie.get("img") or ""
    st.state.detail_error = False
    st.state.panel = ""
    st.state.panel_title = ""
    st.state.play = ""
    st.state.status = ""

    link = movie["link"]
    ready = runtime.take_ready(link)
    cur = st.state.detail
    if ready:
        st.state.detail = ready
    elif (cur and cur.get("link") == link
          and not cur.get("_loading") and not cur.get("error")):
        st.state.detail = cur
    else:
        st.state.detail = {
            "_loading": True,
            "code": movie["code"],
            "cover": movie["img"],
            "name": movie.get("title", ""),
            "link": link,
        }
        runtime.request_detail(link)
    # 详情页在栈中，后台提交可以放心触发刷新；返回后 on_disappear 会复位。
    st.state.detail_open = True
    st.DETAIL_OPEN_AT = time.time()
    if path is None:
        path = st.PATH_BROWSE
    # 记住详情属于哪个栈：之后详情内的筛选/大图 push/pop 都只操作这个栈，
    # 与全局 ACTIVE_PATH、当前 tab 完全解耦，避免跨 tab 乱跳
    st.DETAIL_PATH = path
    st.set_active_path(path)
    record_nav_action()
    path.append({"tag": "detail"})


def on_detail_closed():
    """详情页被返回/关闭：复位标志 + 开启转场静默窗，后台提交转为静默。"""
    st.state.detail_open = False
    runtime.note_nav_action()


def close_detail():
    """保留占位（详情返回由系统导航处理）。"""
    pass


def clear_panel():
    """关闭当前播放器。"""
    st.state.panel = ""
    st.state.panel_title = ""
    st.state.play = ""


def open_senplayer():
    """完整视频链接交给 SenPlayer 播放。"""
    url = st.state.panel or ""
    if not url:
        st.state.status = "请先播放完整视频"
        st.state.reload += 1
        return
    code = (st.state.detail or {}).get("code", "")
    target = ("SenPlayer://x-callback-url/play?url=" + quote(url, safe="") +
              "&name=" + quote(code, safe="") + "&User-Agent=SenPlayer")
    ok = shortcuts.open_url(target)
    if ok:
        # 已交给外部 SenPlayer 播放，关闭本地播放面板以停止本地播放
        st.state.panel = ""
        st.state.panel_title = ""
        st.state.play = ""
        st.state.status = "已跳转 SenPlayer"
    else:
        st.state.status = "打开失败"
    st.state.reload += 1


def copy_video_link():
    """复制当前（完整视频）链接。"""
    if st.state.panel:
        clipboard.set(st.state.panel)
        st.state.status = "链接已复制"
        st.state.reload += 1
    else:
        st.state.status = "请先播放完整视频"
        st.state.reload += 1


def play_trailer():
    """播放 Fanza 预告。"""
    if st.state.detail and st.state.detail.get("trailer"):
        runtime.play_url(st.state.detail["trailer"], "Fanza 预告",
                         "https://www.dmm.co.jp/", source="预告")


def _spawn_play_fetch(task, fetching_msg, fail_msg):
    """启动后台抓取任务；成功后 set_play_request，失败 set_play_error。

    task: 无参函数，返回 (url, title, source) 或 None。
    """
    st.state.status = fetching_msg
    st.state.reload += 1

    def _work():
        result = task()
        if result:
            runtime.set_play_request(*result)
        else:
            runtime.set_play_error(fail_msg)

    threading.Thread(target=_work, daemon=True).start()


def play_jable_preview():
    """播放 Jable 7 秒预览。"""
    code = st.state.detail.get("code") if st.state.detail else ""
    if not code:
        return

    def _fetch():
        preview, _ = fetch_jable(code)
        return (preview, "Jable 预览", "预览") if preview else None

    _spawn_play_fetch(_fetch, "正在获取 Jable 预览...", "Jable 无预览")


def play_jable():
    """播放 Jable 完整视频（m3u8）。"""
    code = st.state.detail.get("code") if st.state.detail else ""
    if not code:
        return

    def _fetch():
        _, full = fetch_jable(code)
        return (full, "Jable 完整视频", "完整视频") if full else None

    _spawn_play_fetch(_fetch, "正在获取 Jable 完整视频...", "Jable 未找到完整视频")


def play_avgle():
    """播放 Avgle 预览。"""
    code = st.state.detail.get("code") if st.state.detail else ""
    if not code:
        return

    def _fetch():
        url = fetch_avgle(code)
        return (url, "Avgle 预览", "预览") if url else None

    _spawn_play_fetch(_fetch, "正在获取 Avgle 预览...", "Avgle 无预览")


def play_missav_preview():
    """播放 Missav 预览（先探测 URL 是否为视频）。"""
    if not (st.state.detail and st.state.detail.get("trailer2")):
        return
    url = st.state.detail["trailer2"]

    def _fetch():
        return (url, "Missav 预览", "预览") if is_video_url(url) else None

    _spawn_play_fetch(_fetch, "正在获取 Missav 预览...", "Missav 预览不可用")


def show_sample(img, link, path=None):
    """点击样片查看大图（在详情所在 NavigationStack 内 push，保持详情滚动位置）。"""
    if path is None:
        path = st.DETAIL_PATH   # 样片只从详情进入：用它自己的栈，不依赖全局活跃栈
    st.state.sample_preview = link
    record_nav_action()
    path.append({"tag": "sample"})


def close_sample():
    """关闭大图视图并回到详情。"""
    ap = st.DETAIL_PATH
    if ap:
        record_nav_action()
        ap.pop(count=1)
    st.state.sample_preview = ""


def copy_code():
    """复制当前番号。"""
    if st.state.detail:
        code = st.state.detail["code"]
        clipboard.set(code)
        st.state.status = "番号 " + code + " 已复制"
        st.state.reload += 1


def copy_magnet(mag):
    """复制磁链地址。"""
    clipboard.set(mag["info"])


def toggle_fav():
    """切换当前详情的收藏状态并落盘。"""
    d = st.state.detail
    if not d:
        return
    # 传入打开详情时固化的列表缩略图，收藏记录即持久缓存封面，无需再解析
    shelf.toggle_bookmark(d, img=st.state.detail_thumb or "")
    st.state.reload += 1