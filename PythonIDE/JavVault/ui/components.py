# -*- coding: utf-8 -*-
"""通用单元格与网格：影片封面、样片、磁链行。"""

import appui
import clipboard

from core import state as st
from core.cache import img_src
from core.config import APP_VERSION
from ui import actions


def app_header():
    """各 tab 页顶部：导航栏已有大标题 JavVault，这里只需 V+版本号灰色小字副标题。"""
    return appui.HStack([
        appui.Text("V" + APP_VERSION).font("caption").foreground_color("secondaryLabel"),
        appui.Spacer(),
    ], spacing=0)


def _cell_id(m):
    """单元格稳定身份：确保 reload 重建时 SwiftUI 保留已渲染图片不闪烁。"""
    return m.get("code") or m.get("link") or (m.get("name") or "")


def movie_cell(m, path=None, before_open=None):
    """影片封面单元格（网格内一列：封面 + 番号 + 日期）。"""
    def open():
        if before_open:
            before_open()
        actions.open_detail(m, path)

    return (
        appui.VStack([
            appui.AsyncImage(url=img_src(m["img"]))
                .frame(height=165).clipped()
                .background("secondarySystemBackground", corner_radius=6),
            appui.Text(m["code"]).font("caption").line_limit(1),
            appui.Text(m["date"]).font("caption2").foreground_color("secondaryLabel"),
        ], spacing=3).on_tap(open).id(_cell_id(m))
    )


def movie_grid(items, on_more, path=None, loading=False):
    """统一的影片封面网格（各 tab / 子作品列表共用外观）。"""
    if path is None:
        path = st.PATH_BROWSE
    return appui.ScrollView(
        appui.VStack([
            appui.LazyVGrid(
                columns=[appui.adaptive(minimum=104)],
                spacing=10,
                content=[movie_cell(m, path) for m in items],
            ),
            appui.ProgressView().frame(height=16 if loading else 0),
            appui.Button("加载更多", action=on_more),
        ], spacing=12).padding()
    )


def sample_cell(s):
    """详情页样片缩略图（点击查看大图）。"""
    def open():
        actions.show_sample(s["link"], s["link"])

    return (
        appui.AsyncImage(url=img_src(s["img"]))
            .frame(height=110).clipped()
            .background("secondarySystemBackground", corner_radius=6)
            .on_tap(open)
    )


def magnet_row(m):
    """磁链行（左滑可复制）。"""
    def copy():
        clipboard.set(m["info"])

    return appui.Label(m["name"], system_image="link").swipe_actions(actions=[
        appui.Button("复制", action=copy, role="destructive"),
    ])
