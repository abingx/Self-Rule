# -*- coding: utf-8 -*-
"""Jable / Avgle 多源播放地址抓取。"""

import re
from urllib.parse import quote

import network

from core.config import HEADERS
from core.log import log
from core.net import get


def fetch_jable(code):
    """按原 JS jableTv 逻辑返回 (preview_url, full_m3u8)；失败返回 ('', '')。"""
    try:
        # 原 JS 直接拼接大写番号，不做 lower/quote
        search_url = "https://jable.tv/search/" + code + "/"
        resp = network.get(search_url, headers=dict(HEADERS), timeout=15)
        if not resp or not resp.ok:
            log(f"jable: 搜索页 HTTP "
                + str(getattr(resp, "status_code", "no-resp")))
            return "", ""
        search_html = resp.text or ""
        if "部影片" not in search_html:
            log("jable: 搜索页无『部影片』(可能被 Cloudflare 质询拦截)")
            return "", ""
        # 7秒预览：搜索卡片上的 data-preview 属性
        preview = ""
        pre = re.search(r'data-preview="(https[^"]*_preview\.mp4)"', search_html)
        if not pre:
            pre = re.search(r'data-preview="(https[^"\']*?_preview\.mp4)', search_html)
        if pre:
            preview = pre.group(1)
            log("jable: 预览 " + preview)
        # 影片页链接：收集 jable.tv/videos 候选(兼容绝对/相对 href)，优先与番号匹配的
        links = re.findall(r'https://jable\.tv/videos/[^"\')\s]+', search_html)
        if not links:
            links = ["https://jable.tv" + u for u in
                     re.findall(r'href="(/videos/[^"]+)"', search_html)]
        cands = [l for l in links if code.lower() in l.lower()]
        if not cands:
            cands = links
        # 完整视频 m3u8：详情页内联 hlsUrl 变量(签名URL，必须实时抓取)
        full = ""
        ma = re.search(r"hlsUrl\s*=\s*'([^']+)'", search_html)
        if ma:
            full = ma.group(1)
        else:
            for video_url in cands[:5]:
                html = get(video_url)
                if not html:
                    continue
                mm = re.search(r"hlsUrl\s*=\s*'([^']+)'", html)
                if not mm:
                    mm = re.search(r'hlsUrl\s*=\s*"([^"]+)"', html)
                if mm and mm.group(1):
                    full = mm.group(1)
                    log("jable: 完整 " + full)
                    break
        return preview, full
    except Exception as e:
        log("jable err: " + str(e))
        return "", ""


def fetch_avgle(code):
    """Avgle 预览：返回 preview_video_url；失败返回 ''。"""
    try:
        url = ("https://api.avgle.com/v1/search/" + quote(code) +
               "/0?limit=5&t=a&o=bw")
        resp = network.get(url, headers=dict(HEADERS), timeout=8)
        if not resp or not resp.ok:
            return ""
        data = resp.json()
        if not data.get("success"):
            return ""
        videos = data.get("response", {}).get("videos", [])
        if videos:
            return videos[0].get("preview_video_url", "")
        return ""
    except Exception:
        return ""