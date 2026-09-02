# -*- coding: utf-8 -*-
"""女优 tab：页面与加载。"""

import appui

from core import cache
from core import state as st
from core.cache import img_src
from core.config import APP_TITLE
from parser.movies import fetch_actresses
from ui import components
from ui.detail import detail_destination, sample_destination
from ui.sublist import cur_base, open_sub, sub_destination

# 首次进入 tab 才预加载（避免启动时重复请求）
ACTRESS_LOADED = False


def actress_cell(a):
    """女优头像单元格（点击进入作品列表）。"""
    def open():
        open_sub(st.PATH_ACT, a["link"], a["name"])

    return (
        appui.VStack([
            appui.AsyncImage(url=img_src(a["img"]))
                .frame(height=130).clipped()
                .background("secondarySystemBackground", corner_radius=6),
            appui.Text(a["name"]).font("caption").line_limit(1),
        ], spacing=3).on_tap(open).id(a.get("link") or a.get("name") or "")
    )


def load_actresses():
    """重新加载女优第一页。"""
    st.state.actress_page = 1
    items = fetch_actresses(1, cur_base())
    for it in items:
        cache.request_img(it["img"])
    st.state.actresses = items[:st.MAX_LIST_ITEMS]


def load_actresses_once():
    """女优 tab 首次出现时预加载第一页。"""
    global ACTRESS_LOADED
    if ACTRESS_LOADED:
        return
    ACTRESS_LOADED = True
    load_actresses()


def load_actresses_more():
    """追加女优下一页。"""
    if len(st.state.actresses) >= st.MAX_LIST_ITEMS:
        return
    res = fetch_actresses(st.state.actress_page + 1, cur_base())
    if res:
        for it in res:
            cache.request_img(it["img"], priority=True)
        st.state.actress_page += 1
        st.state.actresses = (st.state.actresses + res)[:st.MAX_LIST_ITEMS]


def actress_page():
    """女优 tab 根页面。"""
    return appui.NavigationStack(
        appui.ScrollView(
            appui.VStack([
                components.app_header(),
                appui.LazyVGrid(
                    columns=[appui.adaptive(minimum=100)],
                    spacing=10,
                    content=[actress_cell(a) for a in st.state.actresses],
                ),
                appui.Button("加载更多", action=load_actresses_more),
            ], spacing=10).padding()
        ).refreshable(action=load_actresses)
        .navigation_title(APP_TITLE),
        path=st.PATH_ACT,
        destinations={"detail": detail_destination,
                      "sample": sample_destination,
                      "sub": sub_destination},
    ).on_appear(action=load_actresses_once)
