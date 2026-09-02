# -*- coding: utf-8 -*-
"""影片 tab：页面与翻页加载。"""

from urllib.parse import quote

import appui

from core import cache
from core import state as st
from core.config import APP_TITLE, BASE
from core.net import fill_base
from parser.movies import fetch_movie_page
from ui import components
from ui.detail import detail_destination, sample_destination
from ui.sublist import cur_base, sub_destination


def movie_url(page):
    """首页/搜索/分类共用的分页地址组装。"""
    h = cur_base()
    if st.state.mode == "search":
        return h + "search/" + quote(st.state.keyword) + "/" + str(page)
    if st.state.mode == "cat":
        return fill_base(st.state.cat_link) + "/" + str(page)
    return h + "page/" + str(page)


def load_first():
    """同步加载第一页（启动/切码等场景；与原始可用版本一致）。"""
    st.state.movies_page = 1
    res = fetch_movie_page(movie_url(1), st.state.all_flag)
    st.state.movies = (res if res != "empty" else [])[:st.MAX_LIST_ITEMS]
    for m in st.state.movies:
        cache.request_img(m["img"])


def load_more():
    """同步加载下一页并追加。"""
    if len(st.state.movies) >= st.MAX_LIST_ITEMS:
        return
    res = fetch_movie_page(movie_url(st.state.movies_page + 1), st.state.all_flag)
    if res != "empty":
        st.state.movies_page += 1
        st.state.movies = (st.state.movies + res)[:st.MAX_LIST_ITEMS]
        for m in res:
            # 新追加的封面优先下载，避免排在旧封面队列之后导致迟迟不显示
            cache.request_img(m["img"], priority=True)


def switch_censor(idx):
    """切换有码/无码并回到首页。"""
    st.state.censor = idx
    st.state.mode = "home"
    st.state.keyword = ""
    load_first()


def set_censor0():
    switch_censor(0)


def set_censor1():
    switch_censor(1)


def toggle_all(v):
    """全量开关（含无码与否的 legacy 开关）。"""
    st.state.all_flag = v
    load_first()


def browse_page():
    """影片 tab 根页面。"""
    return appui.NavigationStack(
        appui.ScrollView(
            appui.VStack([
                components.app_header(),
                appui.HStack([
                    appui.Button("有码", action=set_censor0)
                        .button_style("bordered" if st.state.censor != 0 else "bordered_prominent"),
                    appui.Button("无码", action=set_censor1)
                        .button_style("bordered" if st.state.censor != 1 else "bordered_prominent"),
                ], spacing=10),
                appui.LazyVGrid(
                    columns=[appui.adaptive(minimum=104)],
                    spacing=10,
                    content=[components.movie_cell(m, st.PATH_BROWSE) for m in st.state.movies],
                ),
                appui.Button("加载更多", action=load_more),
            ], spacing=12).padding()
        )
        .refreshable(action=load_first)
        .navigation_title(APP_TITLE),
        path=st.PATH_BROWSE,
        destinations={"detail": detail_destination,
                      "sample": sample_destination,
                      "sub": sub_destination},
    ).id("browse")
