# -*- coding: utf-8 -*-
"""影片 / 女优 / 分类 列表页解析与搜索关键词规整。"""

import re

from core.config import BASE
from core.net import fill_base, get


def norm_keyword(kw):
    """把用户输入规整成 JavBus 可识别的番号格式（如 JUL333 -> JUL-333）。"""
    s = re.sub(r"\s+", "", kw)
    s = re.sub(r"([a-zA-Z])(?=\d)(?!-)(?<!fc)", r"\1-", s, flags=re.I)
    s = re.sub(r"(\d)(?=[a-zA-Z])(?!-)", r"\1-", s)
    return s


def parse_movies(html):
    """解析卡片网格 HTML，返回影片列表 dict。"""
    items = []
    for i in re.compile(r'<a class="movie-box"[\s\S]*?</span>\s', re.S).findall(html):
        m = re.search(r'href="([^"]*)"', i)
        im = re.search(r'<img src="([^"]*)"', i)
        code = re.search(r"<date>(.*?)</date>", i)
        date = re.search(r"/\s<date>(.*?)</date></span>", i)
        if not (m and im and code):
            continue
        items.append({"code": code.group(1),
                      "date": date.group(1) if date else "",
                      "img": im.group(1),
                      "link": m.group(1),
                      "hd": "高清" in i, "sub": "字幕" in i})
    return items


def fetch_movie_page(url, all_flag=False):
    """抓取一页影片列表；无结果时返回 'empty'。all_flag 带上 existmag=all。"""
    html = get(url, all_flag)
    if not html or "404 Page Not Found" in html:
        return "empty"
    if "沒有您要的結果" in html:
        return "empty"
    return parse_movies(html)


def fetch_actresses(page, homepage):
    """抓取女优一页（homepage 为当前有码/无码基础路径）。"""
    url = homepage.rstrip("/") + "/actresses/" + str(page)
    html = get(url)
    if not html:
        return []
    items = []
    for i in re.findall(r'<a class="avatar-box text-center"[\s\S]*?</span>', html, re.S):
        m = re.search(r'href="([^"]*)"', i)
        im = re.search(r'<img src="([^"]*)"', i)
        title = re.search(r'title="([^"]*)"', i)
        if not (m and title):
            continue
        items.append({"link": m.group(1),
                      "img": fill_base(im.group(1)) if im else "",
                      "name": title.group(1)})
    return items


def fetch_genres():
    """抓取分类页并按主题分组。"""
    html = get(BASE + "/genre")
    groups = []
    if not html:
        return groups
    for tag in ["主題", "角色", "服裝", "體型", "行為", "玩法", "類別"]:
        g = re.search(tag + r"</h4>([\s\S]*?)</div>", html, re.S)
        if not g:
            continue
        cats = re.findall(r'href="([^"]*)">([^<]*)</a>', g.group(1))
        if cats:
            groups.append({"tag": tag,
                           "cats": [{"link": l, "name": n} for l, n in cats]})
    return groups


def fetch_actress_movies(url):
    """抓取某女优的作品列表。"""
    return parse_movies(get(url))