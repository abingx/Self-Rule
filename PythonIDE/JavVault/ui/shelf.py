# -*- coding: utf-8 -*-
"""收藏 tab：页面。"""

import json
import os
import tempfile
import threading
import time
from urllib.parse import quote

import appui

from core import cache
from core import state as st
from core.config import APP_TITLE, BASE
from core.log import log
from data import shelf
from parser.movies import fetch_movie_page
from ui import components
from ui.detail import detail_destination, sample_destination

_MOVIE_CACHE_FILE = os.path.join(tempfile.gettempdir(), "javbus_img", "shelf_movies.json")


def _load_movie_cache():
    try:
        with open(_MOVIE_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {str(code): movie for code, movie in data.items()
                if isinstance(movie, dict) and movie.get("img") and movie.get("link")}
    except Exception:
        return {}


def _save_movie_cache(movies):
    try:
        os.makedirs(os.path.dirname(_MOVIE_CACHE_FILE), exist_ok=True)
        tmp = _MOVIE_CACHE_FILE + "." + str(threading.get_ident()) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(movies, f, ensure_ascii=False)
        os.replace(tmp, _MOVIE_CACHE_FILE)
    except Exception:
        pass


_MOVIES = _load_movie_cache()
_MOVIE_PENDING = set()
_MOVIE_ATTEMPTS = {}
_MOVIE_QUEUE = []
_MOVIE_LOCK = threading.Lock()
_MOVIE_MAX_ATTEMPTS = 5
_MOVIE_WORKERS = 2                # 低频补全：低并发，避免洪泛触发限流
_MOVIE_OK_SLEEP = 0.7           # 每次成功解析后稍作停顿，进一步限流
_MOVIE_RETRY_SLEEP = 0.6       # 解析失败重试前的退避，避免短时间内连发请求触发限流
_MOVIE_PAUSE_UNTIL = 0.0
_MOVIE_STARTED = False
_MOVIE_UNSAVED = 0
# 解析失败被放弃的番号 -> 放弃时刻。冷却期间进收藏 tab 不再重搜，
# 避免"每次进入都对一批搜不到的番号重复请求"导致限流/卡顿。
_MOVIE_GIVEUP = {}
_MOVIE_GIVEUP_COOL = 600   # 秒，冷却后允许再试一次


def _movie_worker():
    global _MOVIE_UNSAVED
    while True:
        with _MOVIE_LOCK:
            ready = time.time() >= _MOVIE_PAUSE_UNTIL
            code = _MOVIE_QUEUE.pop(0) if _MOVIE_QUEUE and ready else ""
        if not code:
            time.sleep(0.15)
            continue
        try:
            result = fetch_movie_page(BASE + "/search/" + quote(code) + "/1")
        except Exception as e:
            log("shelf movie fetch err: " + str(e))
            result = "empty"
        match = None
        if isinstance(result, list):
            match = next((item for item in result
                          if item.get("code", "").strip().upper() == code), None)
        snapshot = None
        retry_sleep = 0.0
        with _MOVIE_LOCK:
            attempts = _MOVIE_ATTEMPTS.get(code, 0) + 1
            _MOVIE_ATTEMPTS[code] = attempts
            if match:
                _MOVIES[code] = match
                _MOVIE_PENDING.discard(code)
                _MOVIE_UNSAVED += 1
            elif attempts < _MOVIE_MAX_ATTEMPTS:
                _MOVIE_QUEUE.append(code)
                retry_sleep = _MOVIE_RETRY_SLEEP * attempts
            else:
                _MOVIE_PENDING.discard(code)
                _MOVIE_GIVEUP[code] = time.time()
            if _MOVIE_UNSAVED >= 10 or (_MOVIE_UNSAVED and not _MOVIE_PENDING):
                snapshot = dict(_MOVIES)
                _MOVIE_UNSAVED = 0
        if snapshot:
            _save_movie_cache(snapshot)
        if match:
            try:
                cache.request_img(match.get("img", ""), priority=True)
                cache.mark_dirty()
            except Exception as e:
                log("shelf image cache err: " + str(e))
            time.sleep(_MOVIE_OK_SLEEP)   # 成功也限流，避免连续请求
        elif retry_sleep:
            time.sleep(retry_sleep)   # 失败退避，缓解并发触发站点限流


def _start_movie_workers():
    global _MOVIE_STARTED
    if _MOVIE_STARTED:
        return
    _MOVIE_STARTED = True
    for _ in range(_MOVIE_WORKERS):
        threading.Thread(target=_movie_worker, daemon=True).start()


def pause_shelf_movies():
    global _MOVIE_PAUSE_UNTIL
    with _MOVIE_LOCK:
        _MOVIE_PAUSE_UNTIL = time.time() + 3.0


def load_shelf_movies():
    global _MOVIE_PAUSE_UNTIL
    _start_movie_workers()
    cached_images = []
    with _MOVIE_LOCK:
        _MOVIE_PAUSE_UNTIL = 0.0
        for item in shelf.SHELF["fav"][:st.MAX_LIST_ITEMS]:
            code = str(item.get("code") or "").strip().upper()
            # 已固化在收藏记录里的封面（新收藏，零请求）优先直接下载
            img = item.get("img") or ""
            if not img and code in _MOVIES:
                img = _MOVIES[code].get("img", "")
            if img:
                cached_images.append(img)
            elif code and code not in _MOVIE_PENDING:
                if code in _MOVIE_GIVEUP:
                    if time.time() - _MOVIE_GIVEUP[code] < _MOVIE_GIVEUP_COOL:
                        continue   # 冷却中，避免重复请求
                    _MOVIE_GIVEUP.pop(code, None)
                _MOVIE_PENDING.add(code)
                _MOVIE_ATTEMPTS[code] = 0
                _MOVIE_QUEUE.append(code)
    for image in reversed(cached_images):
        cache.request_img(image, priority=True)


def shelf_cell_item(item):
    """收藏封面单元格：与其他 tab 完全一致的封面外观（movie_cell），
    额外提供长按/右键菜单移除。"""
    code = str(item.get("code") or "").strip().upper()
    with _MOVIE_LOCK:
        resolved = _MOVIES.get(code, {})
    movie = {
        "code": code,
        "img": item.get("img") or resolved.get("img", ""),
        "date": item.get("fav_time") or "",
        "link": resolved.get("link") or BASE + "/" + quote(code),
    }

    def unfav():
        shelf.remove_fav(item.get("code"))
        shelf.save_shelf()
        st.state.reload += 1

    # 复用统一封面单元格，再叠加移除菜单与稳定身份
    return components.movie_cell(
        movie, st.PATH_SHELF, before_open=pause_shelf_movies).context_menu(content=[
        appui.Button("从收藏移除", action=unfav, role="destructive"),
    ]).id(item.get("code") or "")


def shelf_page():
    """收藏 tab 根页面。"""
    def fav_rows():
        # 按收藏时间从新到旧展示
        items = sorted(shelf.SHELF["fav"],
                       key=lambda x: x.get("fav_time", ""),
                       reverse=True)[:st.MAX_LIST_ITEMS]
        return [shelf_cell_item(item) for item in items]

    return appui.NavigationStack(
        appui.ScrollView(
            appui.VStack([
                components.app_header(),
                appui.Text("收藏 " + str(shelf.fav_count())).font("footnote").foreground_color("secondaryLabel"),
                appui.LazyVGrid(
                    columns=[appui.adaptive(minimum=104)],
                    spacing=10,
                    content=fav_rows(),
                ),
            ], spacing=10).padding()
        )
        .navigation_title(APP_TITLE),
        path=st.PATH_SHELF,
        destinations={"detail": detail_destination,
                      "sample": sample_destination},
    ).on_appear(action=load_shelf_movies)
