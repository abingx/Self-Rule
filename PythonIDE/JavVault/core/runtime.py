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

# 导航转场"静默期"：每次点击引起的导航（push/pop/面板动画）前开启，
# 期间所有后台驱动的整树刷新（图片去抖、详情提交、列表提交）暂缓，
# 使快速点击 / 跨 tab 点击也不会出现 reload 打断转场动画的乱跳。
_RELOAD_SILENT_UNTIL = 0.0
_NAV_SILENCE = 0.5         # 秒；导航转场动画约 0.35s，留 0.15s 余量即可

# 播放请求（后台抓取成功后由主线程提交给播放器）
_PLAY_REQUEST = None       # (url, title, source)
_PLAY_ERROR = ""           # 后台抓取失败时的提示

# 图片刷新：下载完成后需静默多久才整树重建（去抖，防止闪烁）
_LAST_IMG_RELOAD = 0.0
IMG_SILENCE_INTERVAL = 0.5
IMG_MAX_RELOAD_INTERVAL = 2.0
# 任意两次整树刷新之间的最小间隔（压住下载风暴期高频刷新，
# 大幅降低刷新撞上返回转场窗口的概率）
IMG_RELOAD_MIN_GAP = 1.2
# 详情页打开期间 overdue 触发刷新的最大等待：详情页读图不急于整树重建，
# 避免 20 张大图下载期间反复刷新导致持续闪烁
IMG_MAX_RELOAD_LONG = 8.0

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


def take_ready(link):
    """取回后台已抓好的同链接详情（返回后重进同一番号时秒开，零请求）。

    失败结果的详情不返回：重进时走重新抓取。取走后清除，避免下次误复用。
    """
    global _DETAIL_READY, _DETAIL_REQUEST
    if _DETAIL_READY and _DETAIL_READY.get("link") == link \
            and not _DETAIL_READY.get("error"):
        r = _DETAIL_READY
        _DETAIL_READY = None
        _DETAIL_REQUEST = None
        return r
    return None


def note_nav_action():
    """任何点击引起的导航/面板转场前调用：开启转场静默窗。

    期间所有后台驱动的整树刷新（图片去抖、详情提交、列表提交）全部暂缓，
    使快速连点 / 跨 tab 点击也不会出现 reload 打断转场导致的乱跳。
    """
    global _RELOAD_SILENT_UNTIL
    _RELOAD_SILENT_UNTIL = time.time() + _NAV_SILENCE


def reload_allowed():
    """当前是否允许整树刷新（避开 push/pop 转场动画窗口）。"""
    return time.time() >= _RELOAD_SILENT_UNTIL


# 详情提交专用门控：只避开"返回转场"。进入详情超过 _DETAIL_SAFE_AFTER 后，
# 顶部视图上整树刷新与转场动画不再冲突，抓取一完成即可立刻提交，
# 不再被进入时的静默窗拖慢。
_DETAIL_SAFE_AFTER = 0.5


def detail_commit_allowed():
    """详情提交是否允许立即刷新（已避开所有转场窗口）。"""
    if reload_allowed():
        return True
    if st.state.detail_open and st.DETAIL_OPEN_AT > 0 \
            and time.time() - st.DETAIL_OPEN_AT >= _DETAIL_SAFE_AFTER:
        return True
    return False


def _detail_worker(link, seq):
    """后台详情抓取线程（不会阻塞主循环）."""
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


# 列表页抓取（影片 / 子列表 / 女优 / 分类共用后台通道）
_PAGE_REQUEST = None       # (url, kind, append, all_flag)
_PAGE_READY = None         # (kind, append, result)
_PAGE_SEQ = 0


def request_page(url, kind, append=False, all_flag=False):
    """登记列表页抓取请求并启动后台线程（主线程不再同步阻塞网络）。"""
    global _PAGE_REQUEST, _PAGE_READY, _PAGE_SEQ
    _PAGE_SEQ += 1
    seq = _PAGE_SEQ
    _PAGE_REQUEST = (url, kind, append, all_flag)
    _PAGE_READY = None
    threading.Thread(target=_page_worker, args=(url, kind, append, all_flag, seq), daemon=True).start()


def _page_worker(url, kind, append, all_flag, seq):
    """后台列表抓取线程（不阻塞主循环）。"""
    global _PAGE_READY
    if kind == "genre":
        from parser.movies import fetch_genres
        fetcher = fetch_genres
        args = ()
    elif kind == "actress":
        from parser.movies import fetch_actresses
        from core.config import BASE
        fetcher = fetch_actresses
        page = url.rsplit("/", 1)[-1]
        try:
            page = int(page)
        except Exception:
            page = 0
        home = BASE.rstrip("/") + ("/uncensored/" if st.state.censor == 1 else "/")
        args = (page, home)
    else:
        from parser.movies import fetch_movie_page
        fetcher = fetch_movie_page
        args = (url, all_flag)
    try:
        result = fetcher(*args)
    except Exception:
        result = "empty" if kind in ("browse", "sub", "search") else []
    if seq == _PAGE_SEQ:
        _PAGE_READY = (kind, append, result)


def _commit_page():
    """主线程 Timer：提交后台抓回的列表页数据（转场静默窗内暂缓）。"""
    global _PAGE_READY, _PAGE_REQUEST
    if _PAGE_READY is not None:
        kind, append, res = _PAGE_READY
        _PAGE_READY = None
        _PAGE_REQUEST = None
        if not reload_allowed():
            _PAGE_READY = (kind, append, res)
            return
        if kind == "browse":
            items = (res if res != "empty" else [])[:st.MAX_LIST_ITEMS]
            if append:
                if items:
                    st.state.movies_page += 1
                    st.state.movies = (st.state.movies + items)[:st.MAX_LIST_ITEMS]
            else:
                st.state.movies_page = 1
                st.state.movies = items
            for m in items:
                cache.request_img(m["img"], priority=append)
            st.state.browse_loading = False
        elif kind == "sub":
            items = (res if res != "empty" else [])[:st.MAX_LIST_ITEMS]
            if append:
                if items:
                    st.state.sub_page += 1
                    st.state.sub_movies = (st.state.sub_movies + items)[:st.MAX_LIST_ITEMS]
            else:
                st.state.sub_page = 1
                st.state.sub_movies = items
            for m in items:
                cache.request_img(m["img"], priority=append)
            st.state.sub_loading = False
        elif kind == "search":
            items = (res if res != "empty" else [])[:st.MAX_LIST_ITEMS]
            if res == "empty":
                st.state.search_empty = True
            elif append:
                if items:
                    st.state.search_page += 1
                    st.state.search_movies = (st.state.search_movies + items)[:st.MAX_LIST_ITEMS]
            else:
                st.state.search_page = 1
                st.state.search_movies = items
                st.state.search_empty = False
            for m in items:
                cache.request_img(m["img"], priority=append)
            st.state.search_loading = False
        elif kind == "actress":
            items = (res if isinstance(res, list) else [])[:st.MAX_LIST_ITEMS]
            if append:
                if items:
                    st.state.actress_page += 1
                    st.state.actresses = (st.state.actresses + items)[:st.MAX_LIST_ITEMS]
            else:
                st.state.actress_page = 1
                st.state.actresses = items
            for it in items:
                cache.request_img(it["img"], priority=append)
            st.state.actress_loading = False
        elif kind == "genre":
            st.state.genres = res if isinstance(res, list) else []
            st.state.genre_loading = False
        st.state.reload += 1


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
        # 详情页打开期间：overdue 用长间隔，避免下载风暴反复整树重建
        max_wait = IMG_MAX_RELOAD_LONG if st.state.detail_open else IMG_MAX_RELOAD_INTERVAL
        overdue = now - _LAST_IMG_RELOAD >= max_wait
        if (quiet or overdue) and reload_allowed() \
                and now - _LAST_IMG_RELOAD >= IMG_RELOAD_MIN_GAP:
            cache.clear_dirty()
            _LAST_IMG_RELOAD = now
            st.state.reload += 1
    # 提交后台线程抓到的待播放链接（转场静默窗内暂缓，避免撞上返回动画）
    if _PLAY_REQUEST and reload_allowed():
        url, title, source = _PLAY_REQUEST
        _PLAY_REQUEST = None
        st.state.status = ""
        play_url(url, title, source=source)
    elif _PLAY_ERROR and reload_allowed():
        st.state.status = _PLAY_ERROR
        _PLAY_ERROR = ""
        st.state.reload += 1
    _commit_page()
    _commit_detail()


def _commit_detail():
    """主线程 Timer：若后台详情已就绪则提交到 state。"""
    global _DETAIL_READY, _DETAIL_ERROR, _DETAIL_REQUEST
    if _DETAIL_READY is not None:
        d = _DETAIL_READY
        _DETAIL_READY = None
        cur = st.state.detail
        # 用户已返回列表（详情被 pop）：静默保留同链接数据供重进秒开，
        # 不写 state、不请求图片、不触发整树刷新（避开返回转场窗口）。
        if not st.state.detail_open:
            if cur and cur.get("link") == d.get("link"):
                _DETAIL_READY = d
                _DETAIL_REQUEST = None
            return
        # 若用户已切换到别的详情，则不强制覆盖当前占位
        _DETAIL_REQUEST = None
        if cur and cur.get("link") != d.get("link"):
            return
        # 详情提交只避开"返回转场"；仍在详情阅读中则立即提交，不拖慢展示
        if not detail_commit_allowed():
            _DETAIL_READY = d
            return
        log("detail ready code=" + str(d.get("code")))
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
        # 就地合并到现有 dict：不换对象，避免 State 赋值自动刷新 + 显式
        # reload 造成两次连续整树重建（闪烁来源之一）
        if cur:
            for k, v in d.items():
                cur[k] = v
            cur.pop("_loading", None)
            cur.pop("error", None)
        else:
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
        # 用户已返回：静默丢弃错误（重进会重新抓取），不触发整树刷新
        if not st.state.detail_open:
            return
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
