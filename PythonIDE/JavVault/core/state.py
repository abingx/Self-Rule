# -*- coding: utf-8 -*-
"""全局 AppUI 状态与各 tab 导航路径。"""

import appui

# Bound in-memory collections so repeated pagination cannot grow without limit.
MAX_LIST_ITEMS = 1000

# 全局界面状态（唯一实例，由 main.py 传入 appui.run）
state = appui.State(
    censor=0,           # 0 有码 1 无码
    all_flag=False,
    mode="home",        # home / search / cat
    keyword="",
    cat_link="",
    cat_title="",
    movies=[],
    movies_page=1,
    search_keyword="",
    search_movies=[],
    search_page=1,
    search_empty=False,
    search_loading=False,
    sub_title="",
    sub_link="",
    sub_movies=[],
    sub_page=1,
    actresses=[],
    actress_page=1,
    genres=[],
    detail=None,
    detail_open=False,
    detail_error=False,
    detail_thumb="",        # 打开详情时列表项自带的缩略图（收藏封面用，详情抓取后保留）
    panel="",
    panel_title="",
    play="",            # 当前播放来源："" / 预览 / 预告 / 完整视频
    sample_preview="",
    tab=0,
    reload=0,
    status="",
)

# 每个 tab 独立的导航栈（详情 / 子列表用 NavigationPath 推送，避免 body 重建丢失路由）
PATH_BROWSE = appui.NavigationPath()
PATH_ACT = appui.NavigationPath()
PATH_CAT = appui.NavigationPath()
PATH_SEARCH = appui.NavigationPath()
PATH_SHELF = appui.NavigationPath()

# 详情/大图当前所在的导航栈（跨模块共享，通过函数读写避免 stale 引用）
ACTIVE_PATH = PATH_BROWSE


def set_active_path(path):
    """切换到目标导航栈（详情、筛选列表在当前栈内 push）。"""
    global ACTIVE_PATH
    ACTIVE_PATH = path


def get_active_path():
    """返回当前活跃的导航栈。"""
    return ACTIVE_PATH
