# -*- coding: utf-8 -*-
"""影片详情页与磁链接口解析。"""

import re
from urllib.parse import quote, unquote

from core.config import BASE
from core.log import log
from core.net import fill_base, get


def fetch_magnets(code):
    """按番号请求磁链 AJAX 接口，解析出磁链列表。"""
    if not code:
        return []
    url = BASE + "/uncledatoolsbyajax.php?lang=cn&code=" + quote(code)
    html = get(url)
    mags = []
    if not html:
        return mags
    for i in re.findall(r"<tr onmouseover[\s\S]*?</tr>", html, re.S):
        m = re.search(r"window\.open\('([^']*)'", i)
        if not m:
            continue
        maglink = m.group(1)
        m_name = re.search(r"dn=(.*)", maglink)
        size_m = re.findall(r"href[\s\S]*?>([^<]*)</a>", i)
        mags.append({"info": maglink,
                     "name": unquote(m_name.group(1)) if m_name else "",
                     "size": size_m[1].strip() if len(size_m) > 1 else "",
                     "time": size_m[2].strip() if len(size_m) > 2 else ""})
    return mags


def fetch_detail(url):
    """抓取并解析详情页，返回完整详情 dict（含磁链与预告地址）。"""
    d = {"code": "", "name": "", "cover": "", "time": "????-??-??",
         "last": "???", "estab": "", "maker": "", "series": "", "director": "",
         "estab_link": "", "maker_link": "", "series_link": "", "director_link": "",
         "genres": [], "samples": [], "actresses": [],
         "link": url, "magnets": [], "trailer": "", "error": False}
    html = get(url)
    if not html:
        log("fetch_detail empty: " + url)
        d["error"] = True
        return d
    m = re.search(r'<a class="bigImage" href="([^"]*)"', html)
    if m:
        d["cover"] = m.group(1)
        t = re.search(r'title="([^"]*)"', m.group(0))
        if t:
            d["name"] = t.group(1)
    t = re.search(r'<span class="header">發行日期:</span>([\s\S]*?)</p>', html)
    if t:
        d["time"] = t.group(1).strip()
    t = re.search(r'<span class="header">長度:</span>([\s\S]*?)</p>', html)
    if t:
        dm = re.search(r"(\d+)\s*分鐘", t.group(1))
        d["last"] = dm.group(1) if dm else t.group(1).strip()
    t = re.search(r'<span class="header">發行商:[\s\S]*?"([^"]*)">([^<]*)</a>', html)
    if t:
        d["estab"] = t.group(2)
        d["estab_link"] = t.group(1)
    t = re.search(r'<span class="header">製作商:[\s\S]*?"([^"]*)">([^<]*)</a>', html)
    if t:
        d["maker"] = t.group(2)
        d["maker_link"] = t.group(1)
    t = re.search(r'<span class="header">系列:[\s\S]*?"([^"]*)">([^<]*)</a>', html)
    if t:
        d["series"] = t.group(2)
        d["series_link"] = t.group(1)
    t = re.search(r'<span class="header">導演:[\s\S]*?"([^"]*)">([^<]*)</a>', html)
    if t:
        d["director"] = t.group(2)
        d["director_link"] = t.group(1)
    t = re.search(r'<span class="header">識別碼:[\s\S]*?">([^<]*)</span>', html)
    if t:
        d["code"] = t.group(1)
    tg = re.search(r"類別:[\s\S]*?button", html, re.S)
    if tg and "label" in tg.group(0):
        d["genres"] = [{"link": l, "name": n} for l, n in
                       re.findall(r'href="([^"]*)">([^<]*)</a>', tg.group(0))]
    for i in re.findall(r'<a class="avatar-box"[\s\S]*?</a>', html, re.S):
        name = re.search(r"<span>(.*?)</span>", i)
        link = re.search(r'href="([^"]*)"', i)
        img = re.search(r'<img src="([^"]*)"', i)
        if name and link:
            d["actresses"].append({"name": name.group(1),
                                   "link": link.group(1),
                                   "img": fill_base(img.group(1)) if img else ""})
    for i in re.findall(r'<a class="sample-box" href="([^"]*)"[\s\S]*?<img src="([^"]*)"', html, re.S):
        d["samples"].append({"link": i[0], "img": i[1]})
    # 完整视频走 Jable m3u8，磁链用不到；跳过 fetch_magnets 的第二次串行请求，
    # 详情只等一页 HTML 即返回，加载更快。
    # Fanza 预告：原 JS 将第一个 "-" 替换为 "00" 后拼接
    code = d["code"].lower()
    fanza = code.replace("-", "00", 1)
    if fanza:
        d["trailer"] = (f"https://cc3001.dmm.co.jp/litevideo/freepv/{fanza[0]}/"
                        f"{fanza[:3]}/{fanza}/{fanza}_sm_w.mp4")
        # 第二预告来源：Missav 预览（对应原 JS preMissav）
        d["trailer2"] = "https://eightcha.com/" + d["code"].lower() + "/preview.mp4"
    return d
