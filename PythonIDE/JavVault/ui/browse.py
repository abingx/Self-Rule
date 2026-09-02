# -*- coding: utf-8 -*-
"""影片 tab：页面与翻页加载。"""

from urllib.parse import quote

import appui

from core import runtime
from core import state as st
from core.config import APP_TITLE, BASE
from core.net import fill_base
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
    """加载第一页（后台抓取，不再阻塞点击）。"""
    st.state.movies_page = 1
    st.state.browse_loading = True
    runtime.request_page(movie_url(1), "browse", all_flag=st.state.all_flag)


def load_more():
    """追加下一页（后台抓取）。"""
    if len(st.state.movies) >= st.MAX_LIST_ITEMS:
        return
    st.state.browse_loading = True
    runtime.request_page(movie_url(st.state.movies_page + 1), "browse",
                         append=True, all_flag=st.state.all_flag)


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
                appui.ProgressView().frame(height=16 if st.state.browse_loading else 0),
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
