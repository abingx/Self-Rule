# -*- coding: utf-8 -*-
"""搜索 tab：页面与搜索动作。"""

from urllib.parse import quote

import appui

from core import runtime
from core import state as st
from core.config import APP_TITLE
from parser.movies import norm_keyword
from ui import components
from ui.detail import detail_destination, sample_destination
from ui.sublist import cur_base, sub_destination


def set_search(v):
    """输入框回调：写入搜索关键词。"""
    st.state.search_keyword = v


def search_url(page):
    """搜索分页地址。"""
    h = cur_base()
    return h + "search/" + quote(st.state.search_keyword) + "/" + str(page)


def _search_load_first():
    """加载搜索第一页（后台抓取）。"""
    st.state.search_page = 1
    st.state.search_loading = True
    runtime.request_page(search_url(1), "search", all_flag=st.state.all_flag)


def do_search():
    """发起搜索（规整关键词后加载第一页）。"""
    kw = norm_keyword(st.state.search_keyword)
    st.state.search_keyword = kw
    st.state.search_movies = []
    st.state.search_page = 0
    st.state.search_empty = False
    st.state.search_loading = True
    _search_load_first()
    st.state.reload += 1


def load_search_more():
    """追加搜索下一页（后台抓取）。"""
    if len(st.state.search_movies) >= st.MAX_LIST_ITEMS:
        return
    st.state.search_loading = True
    runtime.request_page(search_url(st.state.search_page + 1), "search",
                         append=True, all_flag=st.state.all_flag)


def search_page():
    """搜索 tab 根页面。"""
    def submit():
        do_search()

    content = []
    if not st.state.search_movies and not st.state.search_loading:
        if st.state.search_keyword:
            content.append(appui.Text("未找到结果").foreground_color("secondaryLabel"))
        else:
            content.append(appui.Text("输入番号或演员进行搜索")
                           .foreground_color("secondaryLabel"))
    if st.state.search_movies:
        grid = appui.LazyVGrid(
            columns=[appui.adaptive(minimum=104)],
            spacing=10,
            content=[components.movie_cell(m, st.PATH_SEARCH) for m in st.state.search_movies],
        )
        content.append(grid)
    if st.state.search_movies and not st.state.search_empty:
        content.append(appui.Button("加载更多", action=load_search_more))
    content.append(appui.ProgressView().frame(height=16 if st.state.search_loading else 0))
    body_v = appui.VStack([
        components.app_header(),
        appui.HStack([
            appui.TextField("番号或演员", text=st.state.search_keyword, on_change=set_search)
                .text_field_style("rounded_border")
                .on_submit(submit),
            appui.Button("搜索", action=do_search).button_style("bordered_prominent"),
        ], spacing=8),
        *content,
    ], spacing=12).padding()

    return appui.NavigationStack(
        appui.ScrollView(body_v)
        .refreshable(action=do_search)
        .navigation_title(APP_TITLE),
        path=st.PATH_SEARCH,
        destinations={"detail": detail_destination,
                      "sample": sample_destination,
                      "sub": sub_destination},
    ).id("search")
