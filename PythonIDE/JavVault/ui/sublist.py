# -*- coding: utf-8 -*-
"""子作品列表：女优作品、分类作品、详情筛选共用的一套页面与动作。"""

from core import cache
from core import state as st
from core.config import BASE
from core.net import fill_base
from parser.movies import fetch_movie_page
from ui import components


def cur_base():
    """当前有码/无码模式的基础路径。"""
    return BASE + "/uncensored/" if st.state.censor == 1 else BASE + "/"


def sub_url(page):
    """子作品列表分页 URL。"""
    h = cur_base()
    return fill_base(st.state.sub_link) + ("/" if not st.state.sub_link.endswith("/") else "") + str(page)


def load_sub_first():
    """重新加载子作品列表第一页。"""
    st.state.sub_page = 1
    res = fetch_movie_page(sub_url(1), st.state.all_flag)
    st.state.sub_movies = (res if res != "empty" else [])[:st.MAX_LIST_ITEMS]
    for m in st.state.sub_movies:
        cache.request_img(m["img"])


def load_sub_more():
    """追加子作品列表下一页。"""
    if len(st.state.sub_movies) >= st.MAX_LIST_ITEMS:
        return
    res = fetch_movie_page(sub_url(st.state.sub_page + 1), st.state.all_flag)
    if res != "empty":
        st.state.sub_page += 1
        st.state.sub_movies = (st.state.sub_movies + res)[:st.MAX_LIST_ITEMS]
        for m in res:
            cache.request_img(m["img"], priority=True)


def open_sub(path, link, title):
    """在当前导航栈内 push 一个子作品列表。"""
    st.set_active_path(path)
    st.state.sub_title = title
    st.state.sub_link = link
    st.state.sub_page = 0
    load_sub_first()
    path.append({"tag": "sub"})


def open_cat(link, title):
    """分类作品列表：在分类 tab 自己的栈内 push 子列表。"""
    open_sub(st.PATH_CAT, link, title)


def open_filter(link, title):
    """从详情页按发片商/制作商/系列/导演/类别进入筛选后的作品列表。"""
    if not link:
        st.state.status = "无该字段链接"
        st.state.reload += 1
        return
    open_sub(st.get_active_path(), link, title)


def sub_destination(data):
    """子作品列表页（女优作品、分类作品共用外观）。"""
    return components.movie_grid(st.state.sub_movies, load_sub_more, st.get_active_path()) \
        .navigation_title(st.state.sub_title) \
        .refreshable(action=load_sub_first)
