# -*- coding: utf-8 -*-
"""详情视图与大图视图，以及它们的 NavigationPath 路由目标。"""

import appui

from core import state as st
from core.cache import img_src
from data import shelf
from ui import actions
from ui import components
from ui.sublist import open_filter


def detail_destination(data):
    """路由：详情页。挂 on_disappear 感知用户离开，防止后台提交撞上返回转场。"""
    return detail_view().on_disappear(action=actions.on_detail_closed)


def _loading_view(d):
    """详情加载中的占位视图：有封面则立刻展示真实布局骨架，无封面回退纯进度条。"""
    code = d.get("code") or ""
    name = d.get("name") or ""
    cover = d.get("cover") or ""
    if not cover:
        return appui.VStack([
            appui.ProgressView(),
            appui.Text("加载中..." + name).foreground_color("secondaryLabel"),
        ], spacing=12).padding()

    info = appui.VStack([
        appui.Text(code).font("title3").bold(),
        appui.Text(name).font("caption").foreground_color("secondaryLabel").line_limit(2),
        appui.HStack([
            appui.ProgressView().frame(height=14),
            appui.Text("正在加载详情...").font("caption").foreground_color("secondaryLabel"),
        ], spacing=6),
    ], spacing=4, alignment="leading")

    header = appui.HStack([
        appui.AsyncImage(url=img_src(cover))
            .frame(width=160, height=108).clipped()
            .background("secondarySystemBackground", corner_radius=8),
        info,
    ], spacing=12)

    return appui.List([
        appui.Section([header.padding()]),
        appui.Section([appui.ProgressView()], header="详情"),
    ]).navigation_title(code)


def sample_destination(data):
    """路由：大图页。"""
    return sample_preview_view()


def detail_view():
    """影片详情页（封面、收藏/复制、播放按钮、资料、样片、磁链）。"""
    d = st.state.detail
    if not d:
        return appui.Text("载入中...")
    if d.get("_loading"):
        # 占位骨架：进入页面瞬间先用列表项已有的封面/番号/片名撑满布局，
        # 剩余资料在此后进行补全，视觉上"秒进"。
        return _loading_view(d)
    if d.get("error"):
        return appui.VStack([
            appui.Text("加载失败，请返回重试").foreground_color("secondaryLabel"),
        ], spacing=12).padding()

    fav_title = "已收藏" if shelf.in_fav(d["code"]) else "收藏"
    fav_style = "bordered_prominent" if shelf.in_fav(d["code"]) else "bordered"

    info = appui.VStack([
        appui.Text(d["code"]).font("title3").bold(),
        appui.Text(d["name"]).font("caption").foreground_color("secondaryLabel").line_limit(2),
        appui.Text("发行日期 " + d["time"]).font("caption"),
        appui.Text("时长 " + d["last"]).font("caption"),
    ], spacing=4, alignment="leading")

    header = appui.HStack([
        appui.AsyncImage(url=img_src(d["cover"]), content_mode="fit")
            .frame(width=160, height=108).clipped()
            .background("secondarySystemBackground", corner_radius=8),
        info,
    ], spacing=12)

    action_btns = appui.HStack([
        appui.Button(fav_title, action=actions.toggle_fav)
            .button_style(fav_style)
            .frame(max_width=appui.infinity),
        appui.Button("复制番号", action=actions.copy_code)
            .button_style("bordered")
            .frame(max_width=appui.infinity),
    ], spacing=8)

    def equal_btn(label, action, source=None, prominent_when_active=True):
        """等宽按钮：文字不折行（自动缩字号），同排均分宽度。"""
        style = "bordered"
        if source is not None and prominent_when_active and st.state.play == source:
            style = "bordered_prominent"
        return appui.Button(
                content=appui.Text(label)
                    .line_limit(1)
                    .minimum_scale_factor(0.5),
                action=action,
            ) \
            .button_style(style) \
            .frame(min_height=34, max_width=appui.infinity)

    video_btns = appui.HStack([
        equal_btn("预览", actions.play_jable_preview, "预览"),
        equal_btn("预告", actions.play_trailer, "预告"),
        equal_btn("完整视频", actions.play_jable, "完整视频"),
    ], spacing=8)

    def eq_btn(label, action):
        return appui.Button(
                content=appui.Text(label)
                    .line_limit(1)
                    .minimum_scale_factor(0.5),
                action=action,
            ) \
            .button_style("bordered") \
            .frame(min_height=34, max_width=appui.infinity)

    top = appui.VStack([
        header,
        action_btns,
        video_btns,
    ], spacing=10)

    if st.state.panel:
        # 完整视频下方显示 SenPlayer / 复制链接 / 关闭；预览、预告只显示关闭
        op_buttons = [eq_btn("关闭", actions.clear_panel)]
        if st.state.play == "完整视频":
            op_buttons = [
                eq_btn("SenPlayer", actions.open_senplayer),
                eq_btn("复制链接", actions.copy_video_link),
                eq_btn("关闭", actions.clear_panel),
            ]
        panel_rows = [
            appui.Text(st.state.panel_title).font("caption").foreground_color("secondaryLabel"),
            appui.VideoPlayer(url=st.state.panel, autoplay=True).frame(height=220),
            appui.HStack(op_buttons, spacing=8),
        ]
        top = appui.VStack([top, *panel_rows], spacing=8)
    if st.state.status:
        top = appui.VStack([
            top,
            appui.Text(st.state.status).font("caption").foreground_color("secondaryLabel"),
        ], spacing=4)

    def filter_row(label, value, link):
        def open():
            open_filter(link, value)

        clickable = bool(link)
        if clickable:
            return appui.Button(action=open,
                                content=appui.Text(value).line_limit(1)) \
                .button_style("borderless")
        return appui.Text(value).font("body").foreground_color("secondaryLabel")

    def who_row(label, value, link):
        # 单个可点击内容：一行显示，标签左、值右
        return appui.HStack([
            appui.Text(label).font("body").foreground_color("secondaryLabel"),
            appui.Spacer(min_length=8),
            filter_row(label, value, link),
        ], spacing=8)

    def cat_chip(genre):
        def open():
            open_filter(genre["link"], genre["name"])

        return appui.Button(content=appui.Text(genre["name"]).line_limit(1),
                            action=open).button_style("bordered")

    def actress_block(a):
        def open():
            open_filter(a["link"], a["name"])

        return (
            appui.Button(
                action=open,
                content=appui.VStack([
                    appui.AsyncImage(url=img_src(a["img"]))
                        .frame(width=58, height=58).clipped()
                        .background("secondarySystemBackground", corner_radius=8),
                    appui.Text(a["name"]).font("caption2").line_limit(1),
                ], spacing=3),
            ).button_style("plain")
        )

    detail_rows = []
    if d["estab"]:
        detail_rows.append(who_row("发片商", d["estab"], d["estab_link"]))
    if d["maker"]:
        detail_rows.append(who_row("制作商", d["maker"], d["maker_link"]))
    if d["series"]:
        detail_rows.append(who_row("系列", d["series"], d["series_link"]))
    if d["director"]:
        detail_rows.append(who_row("导演", d["director"], d["director_link"]))
    if d["genres"]:
        detail_rows.append(appui.VStack([
            appui.Text("类别").font("body").foreground_color("secondaryLabel"),
            appui.LazyVGrid(
                columns=[appui.adaptive(minimum=90)],
                spacing=6,
                content=[cat_chip(g) for g in d["genres"]],
            ),
        ], spacing=8, alignment="leading"))
    if d["actresses"]:
        detail_rows.append(appui.VStack([
            appui.Text("女优").font("body").foreground_color("secondaryLabel"),
            appui.LazyVGrid(
                columns=[appui.adaptive(minimum=72)],
                spacing=10,
                content=[actress_block(a) for a in d["actresses"]],
            ),
        ], spacing=8, alignment="leading"))

    sections = [
        appui.Section(detail_rows, header="详情"),
    ]
    if d["samples"]:
        sections.append(appui.Section([
            appui.LazyVGrid(
                columns=[appui.adaptive(minimum=118)],
                spacing=8,
                content=[components.sample_cell(s) for s in d["samples"]],
            )
        ], header="样片(点击看大图)"))
    if d["magnets"]:
        sections.append(appui.Section(
            [components.magnet_row(m) for m in d["magnets"]], header="磁链"))

    return appui.List([
        appui.Section([top.padding()]),
        *sections,
    ]).navigation_title(d["code"])


def sample_preview_view():
    """大图查看页（已由详情所在 NavigationStack push，不再嵌套新的 NavigationStack）。"""
    return appui.VStack([
        appui.AsyncImage(url=img_src(st.state.sample_preview), content_mode="fit")
            .frame(max_height=appui.infinity)
            .padding(),
        appui.Button("关闭", action=actions.close_sample),
    ], spacing=12).navigation_title("查看大图")
