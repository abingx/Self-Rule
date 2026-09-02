# -*- coding: utf-8 -*-
"""收藏持久化：存为本地 JSON 文件（放在 MiniApp 包目录），便于同步与备份。"""

import datetime
import json
import os

from core.log import log
from core.state import MAX_LIST_ITEMS

BACKUP_FILE = os.path.join(os.getcwd(), "JavVault_Backup.json")
_NEEDS_SAVE = False


def load_shelf():
    """从备份文件读取收藏数据；文件缺失/损坏时返回空结构。"""
    global _NEEDS_SAVE
    try:
        if os.path.exists(BACKUP_FILE):
            with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"fav": []}
        if not isinstance(data, dict):
            data = {"fav": []}
        # 兼容旧版残留的 arc 数据，只保留收藏
        data.pop("arc", None)
        if not isinstance(data.get("fav"), list):
            data["fav"] = []
        else:
            data["fav"] = [item for item in data["fav"] if isinstance(item, dict)]
            for item in data["fav"]:
                # 保留封面 img（持久缓存）；缺失的记为空，后续由 ui/shelf 低频补全
                item["img"] = item.get("img") or ""
            data["fav"].sort(key=lambda item: item.get("fav_time", ""), reverse=True)
            data["fav"] = data["fav"][:MAX_LIST_ITEMS]
        return data
    except Exception:
        return {"fav": []}


# 内存中的收藏数据（唯一实例）；写操作后调用 save_shelf()
SHELF = load_shelf()


def save_shelf():
    """原子写回备份文件（先写临时文件再替换）。"""
    try:
        tmp = BACKUP_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(SHELF, f, ensure_ascii=False, indent=2)
        os.replace(tmp, BACKUP_FILE)
    except Exception as e:
        log("save_shelf err: " + str(e))


if _NEEDS_SAVE:
    save_shelf()


def in_fav(code):
    """判断番号是否已收藏。"""
    return any(x.get("code") == code for x in SHELF["fav"])


def fav_count():
    """收藏总数。"""
    return len(SHELF["fav"])


def now_time():
    """今天的日期字符串（收藏时间）。"""
    return datetime.date.today().strftime("%Y-%m-%d")


def add_fav(code, img=""):
    """插入一条收藏（新收藏置顶）。img 为与首页一致的列表缩略图，直接持久缓存。"""
    SHELF["fav"].insert(0, {
        "code": code,
        "img": img,
        "fav_time": now_time(),   # 收藏时间（年月日）
    })
    del SHELF["fav"][MAX_LIST_ITEMS:]


def remove_fav(code):
    """按番号移除收藏。"""
    SHELF["fav"] = [x for x in SHELF["fav"] if x.get("code") != code]


def set_fav_img(code, img):
    """为缺失封面的收藏补全 img（低频补全成功后回写并落盘）。返回是否更新。"""
    if not img:
        return False
    for item in SHELF["fav"]:
        if item.get("code") == code and not item.get("img"):
            item["img"] = img
            save_shelf()
            return True
    return False


def toggle_bookmark(d, img=""):
    """切换收藏状态并保存；d 为当前详情 dict。img 为列表缩略图（零请求缓存封面）。"""
    code = d["code"]
    if in_fav(code):
        remove_fav(code)
    else:
        add_fav(code, img=img)
    save_shelf()
