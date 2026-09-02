# -*- coding: utf-8 -*-
"""分类 tab：页面与加载。"""

import appui

from core import runtime
from core import state as st
from core.config import APP_TITLE
from ui import components
from ui.detail import detail_destination, sample_destination
from ui.sublist import open_cat, sub_destination

# 首次进入 tab 才预加载
GENRE_LOADED = False


def genre_cell(c):
    """单个分类按钮。"""
    def open():
        open_cat(c["link"], c["name"])

    return appui.Button(content=appui.Label(c["name"], system_image="tag"), action=open)


def load_genres():
    """重新加载全部分类（后台抓取，不阻塞点击）。"""
    st.state.genre_loading = True
    runtime.request_page("", "genre")


def load_genres_once():
    """分类 tab 首次出现时预加载。"""
    global GENRE_LOADED
    if GENRE_LOADED:
        return
    GENRE_LOADED = True
    load_genres()


def genre_page():
    """分类 tab 根页面。"""
    # 按屏幕宽度自适应列数（每列最小宽度约 100pt，一行可多列显示）
    sections = [components.app_header()]
    for group in st.state.genres:
        parts = [appui.Text(group["tag"]).font("headline").padding(top=10)]
        parts.append(appui.LazyVGrid(
            columns=[appui.adaptive(minimum=100)],
            spacing=8,
            content=[genre_cell(c) for c in group["cats"]],
        ))
        sections.append(appui.VStack(parts, spacing=8))
    sections.append(appui.ProgressView().frame(height=16 if st.state.genre_loading else 0))
    return appui.NavigationStack(
        appui.ScrollView(
            appui.VStack(sections, spacing=4).padding()
        ).refreshable(action=load_genres).navigation_title(APP_TITLE),
        path=st.PATH_CAT,
        destinations={"detail": detail_destination,
                      "sample": sample_destination,
                      "sub": sub_destination},
    ).on_appear(action=load_genres_once)