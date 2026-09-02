# -*- coding: utf-8 -*-
# ============================================================
#  JavBus 播放器 · PythonIDE AppUI  (入口文件)
#  移植自 JSBox 版 (核心功能 + 多源预览)
#  数据来源: https://www.javbus.com
#
#  代码结构:
#    core/    基础层     - 常量/日志/网络/状态/图片缓存/后台调度
#    parser/  解析层     - 列表 / 详情 / 多源地址抓取
#    data/    数据层     - 收藏持久化
#    ui/      界面层     - 各 tab 页面 / 单元格 / 业务动作
# ============================================================

import appui

from core import runtime
from core.state import state
from core.state import (PATH_ACT, PATH_BROWSE, PATH_CAT, PATH_SEARCH,
                        PATH_SHELF)
from ui import actress, browse, genre, search, shelf


def start():
    """冷启动：初始化后台线程并复位到主页。"""
    runtime.init_background()
    runtime.reset_pending()
    # 清掉上次会话的搜索/分类/详情/播放状态
    state.tab = 0
    state.censor = 0
    state.mode = "home"
    state.keyword = ""
    state.cat_link = ""
    state.cat_title = ""
    state.detail = None
    state.detail_error = False
    state.panel = ""
    state.panel_title = ""
    state.play = ""
    state.status = ""
    state.sample_preview = ""
    state.movies_page = 1
    state.actress_page = 1
    state.sub_movies = []
    state.search_movies = []
    state.search_keyword = ""
    # 各 tab 导航栈回到根
    PATH_BROWSE.pop_to_root()
    PATH_ACT.pop_to_root()
    PATH_CAT.pop_to_root()
    PATH_SEARCH.pop_to_root()
    PATH_SHELF.pop_to_root()
    browse.load_first()


def make_body():
    """组装五个 tab。"""
    return appui.TabView(
        tabs=[
            appui.Tab("影片", system_image="play.rectangle", content=browse.browse_page(), tag=0),
            appui.Tab("女优", system_image="person.2", content=actress.actress_page(), tag=1),
            appui.Tab("分类", system_image="tag", content=genre.genre_page(), tag=2),
            appui.Tab("搜索", system_image="magnifyingglass", content=search.search_page(), tag=3),
            appui.Tab("收藏", system_image="star", content=shelf.shelf_page(), tag=4),
        ],
        selection=state.bind.tab,
    )


start()


def body():
    return make_body()


appui.run(body, state=state, presentation="fullscreen_with_close")