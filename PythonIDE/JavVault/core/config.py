# -*- coding: utf-8 -*-
"""站点常量、请求头与应用版本号。"""
import json
import os

# JavBus 站点根地址
BASE = "https://www.javbus.com"

# 通用请求头（移动端 Safari 指纹 + 防盗链 Referer）
HEADERS = {
    "User-Agent":
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) "
    "AppleWebKit/605.1.25 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
    "Referer": "https://www.javbus.com/",
}


def _app_version():
    """从 miniapp.json 读取版本号，保证顶部标题与清单一致。"""
    try:
        p = os.path.join(os.getcwd(), "miniapp.json")
        with open(p, "r", encoding="utf-8") as f:
            return str(json.load(f).get("version", "1.2"))
    except Exception:
        return "1.2"


# 各 tab 顶部导航栏标题
APP_TITLE = "JavVault"
# 应用版本号（来自 miniapp.json，作为副标题展示）
APP_VERSION = _app_version()
