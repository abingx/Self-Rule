# -*- coding: utf-8 -*-
# ============================================================
#  JavVault · PythonIDE AppUI
#  数据来源: https://www.javbus.com
#
#  结构
#   ├─ 影片 tab：通用展示函数（封面网格 + 翻页），筛选条件随位置变化
#   └─ 设置 tab：每页项数 / 默认排序 / 全部影片 / 收藏管理
#
#  通用展示函数 movie_display(vid) 是唯一的影片列表实现，
#  影片首页、详情里点演员/导演/公司等跳转的列表、收藏列表都调用它，
#  只是各自的「筛选条件」与「附加设置」不同。
# ============================================================

import datetime
import hashlib
import json
import os
import queue
import re
import struct
import tempfile
import threading
import time
import zlib
from collections import deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import appui
import clipboard
import network
import shortcuts


# ============================================================
#  基础层：站点常量 / 请求头 / 版本
# ============================================================


BASE = "https://www.javbus.com"

HEADERS = {
    "User-Agent":
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) "
    "AppleWebKit/605.1.25 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
    "Referer": "https://www.javbus.com/",
}

def _app_version():
    """从 miniapp.json 读取版本号，保证设置页与清单一致。"""
    try:
        p = os.path.join(os.getcwd(), "miniapp.json")
        with open(p, "r", encoding="utf-8") as f:
            return str(json.load(f).get("version", "2.0"))
    except Exception:
        return "2.0"

APP_TITLE = "JavVault"
APP_VERSION = _app_version()

# 详情页封面宽高比（JavBus 封面标准比例 400x560）。
# 配合 content_mode="fill" 让封面撑满整个容器，上下不留空白。
COVER_RATIO = 5 / 7

# 外部播放器：显示名 -> URL Scheme（设置页「外部播放器」下拉可配）
EXTERNAL_PLAYERS = {
    "SenPlayer": "SenPlayer",
}


# ============================================================
#  基础层：应用内日志
# ============================================================


LOG = []

def log(msg):
    try:
        LOG.append(str(msg))
        if len(LOG) > 300:
            del LOG[:100]
    except Exception:
        pass


# ============================================================
#  基础层：HTTP
# ============================================================


def get(url):
    """GET 请求返回文本；失败返回空串。"""
    try:
        resp = network.get(url, headers=dict(HEADERS), timeout=15)
        if resp and resp.ok:
            return resp.text
    except Exception as e:
        log("get err " + url[:80] + " : " + str(e))
    return ""

def fill_base(src):
    """相对路径补全为完整 URL（已是 http 开头则原样返回）。"""
    if src.startswith("http"):
        return src
    return BASE + src


# ============================================================
#  基础层：封面后台下载与磁盘缓存
# ============================================================


_DOWNLOADED = OrderedDict()
_SRC_CACHE = OrderedDict()     # src -> file:// 路径 的 LRU 缓存（满时逐出最旧，不再整表清空）
_SRC_CACHE_MAX = 4096
MAX_QUEUE = 1024
MAX_DOWNLOADED = 2048
MAX_DOWNLOAD_ATTEMPTS = 5
_SEEN = set()
_INFLIGHT = set()      # 已出队、正在下载中的 url：防止重复排队与重复下载
_DOWNLOAD_ATTEMPTS = {}
_QUEUED = deque()              # 待下载队列（priority=True 时 appendleft 插队首）
_LOCK = threading.Lock()
_QUEUE_NONEMPTY = threading.Condition(_LOCK)   # 空闲 worker 阻塞等待，不再轮询

# 磁盘缓存维护：_DOWNLOADED 只是内存索引 LRU，磁盘文件必须单独设上限
IMAGE_CACHE_LIMIT_MB = 250     # 磁盘缓存上限（MB）
CACHE_GC_EVERY = 100           # 每下载 100 张做一次清理
CACHE_GC_INTERVAL = 600.0      # 或每 10 分钟（双条件先到先清）
_CACHE_GC_STAMP = {"count": 0, "last": 0.0}

def image_cache_maintenance():
    """磁盘图片缓存清理：超过上限时按 mtime 从旧到新删除。

    由下载 worker 低频触发（每 CACHE_GC_EVERY 次下载或每 CACHE_GC_INTERVAL
    秒先到者），不逐张下载都扫描目录。删除后同步核对内存索引并清空
    _SRC_CACHE，避免 img_src 返回指向已删文件的陈旧路径。
    """
    now = time.time()
    st = _CACHE_GC_STAMP
    st["count"] += 1
    if st["count"] < CACHE_GC_EVERY and now - st["last"] < CACHE_GC_INTERVAL:
        return
    st["count"] = 0
    st["last"] = now
    d = _image_dir()
    entries = []
    total = 0
    try:
        for name in os.listdir(d):
            p = os.path.join(d, name)
            try:
                info = os.stat(p)
            except Exception:
                continue
            entries.append((info.st_mtime, info.st_size, p))
            total += info.st_size
    except Exception:
        return
    limit = IMAGE_CACHE_LIMIT_MB * 1024 * 1024
    if total <= limit:
        return
    entries.sort()      # mtime 从旧到新
    removed = 0
    for _, size, p in entries:
        if total <= limit:
            break
        try:
            os.remove(p)
            total -= size
            removed += 1
        except Exception:
            continue
    if removed:
        with _LOCK:
            # 清掉指向已删文件的索引（含占位图路径），让下次访问按需重建
            for u in [u for u in list(_DOWNLOADED)
                      if not os.path.exists(_local_path(u))]:
                _DOWNLOADED.pop(u, None)
            _SRC_CACHE.clear()
        mark_dirty()
WORKERS = 3
_RELOAD_DIRTY = False
_LAST_ACTIVITY = 0.0
_CACHE_STARTED = False
_PLACEHOLDER = None

def _placeholder_bytes():
    """生成一张纯色占位 PNG（8x12 浅灰），仅用 stdlib。"""
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        w, h = 8, 12
        rgb = (0xED, 0xED, 0xEF)
        sig = b"\x89PNG\r\n\x1a\n"

        def _chunk(typ, data):
            return (struct.pack(">I", len(data)) + typ + data +
                    struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))

        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
        idat = zlib.compress(raw, 9)
        _PLACEHOLDER = (sig + _chunk(b"IHDR", ihdr) +
                        _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))
    return _PLACEHOLDER

def _image_dir():
    d = os.path.join(tempfile.gettempdir(), "javbus_img")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d

def _to_abs(src):
    if src.startswith("http") or src.startswith("file://"):
        return src
    return BASE + src

def _local_path(url):
    key = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(_image_dir(), key + ".jpg")

def _is_image(data):
    if not data:
        return False
    head = data[:16]
    if head.startswith(b"\xff\xd8\xff"):
        return True
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return True
    if head.startswith(b"RIFF"):
        return head[8:12] == b"WEBP"
    if head.startswith(b"BM"):
        return True
    return False

def _download_one(url):
    try:
        path = _local_path(url)
        headers = dict(HEADERS)
        with network.stream("GET", url, headers=headers, timeout=12) as resp:
            if not resp.ok:
                return None
            data = resp.read(max_bytes=1 * 1024 * 1024)
            if not data:
                return None
            if not _is_image(data):
                return None
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            return True
    except Exception:
        return None

def request_img(src, priority=False):
    """登记一张图到后台下载队列。priority=True 插到队首。"""
    if not src:
        return ""
    url = _to_abs(src)
    path = _local_path(url)
    try:
        if os.path.exists(path) and os.path.getsize(path) > len(_placeholder_bytes()):
            with _LOCK:
                _DOWNLOADED[url] = None
                _DOWNLOADED.move_to_end(url)
                while len(_DOWNLOADED) > MAX_DOWNLOADED:
                    _DOWNLOADED.popitem(last=False)
            return "file://" + path
    except Exception:
        pass
    with _LOCK:
        if url in _DOWNLOADED:
            _DOWNLOADED.move_to_end(url)
            return "file://" + _local_path(url)
        if url in _SEEN or url in _INFLIGHT:
            # 已排队或正在下载：不重复入队（QUEUED → INFLIGHT → DOWNLOADED）
            return "file://" + _local_path(url)
        if len(_QUEUED) >= MAX_QUEUE:
            if not priority:
                return "file://" + _local_path(url)
            _SEEN.discard(_QUEUED.pop())    # 挤掉队尾（最旧）的待下载项
        _SEEN.add(url)
        if priority:
            _QUEUED.appendleft(url)
        else:
            _QUEUED.append(url)
        _QUEUE_NONEMPTY.notify()            # 唤醒空闲的下载 worker
    return "file://" + _local_path(url)

def img_src(src):
    """返回该封面恒定不变的本地 file:// 路径（未下载时是占位图）。"""
    if not src:
        return ""
    hit = _SRC_CACHE.get(src)
    if hit:
        _SRC_CACHE.move_to_end(src)     # LRU：命中即续期
        return hit
    url = _to_abs(src)
    path = _local_path(url)
    if not os.path.exists(path):
        try:
            if not os.path.exists(_image_dir()):
                os.makedirs(_image_dir(), exist_ok=True)
            with open(path, "wb") as f:
                f.write(_placeholder_bytes())
        except Exception:
            pass
    if os.path.exists(path):
        if len(_SRC_CACHE) >= _SRC_CACHE_MAX:
            _SRC_CACHE.popitem(last=False)      # 逐出最旧一条，而不是整表清空
        _SRC_CACHE[src] = "file://" + path
    return "file://" + path

def _worker():
    while True:
        # 队列空时阻塞在条件变量上（有新任务才唤醒），不再 sleep 轮询空转
        with _QUEUE_NONEMPTY:
            while not _QUEUED:
                _QUEUE_NONEMPTY.wait(timeout=2.0)   # 超时兜底，防唤醒丢失
            url = _QUEUED.popleft()
            _SEEN.discard(url)
            _INFLIGHT.add(url)      # 出队即标记在途，下载完成前不会重复排队
        ok = _download_one(url)     # 网络下载在锁外
        with _LOCK:
            _INFLIGHT.discard(url)
            if ok:
                _DOWNLOADED[url] = None
                _DOWNLOADED.move_to_end(url)
                while len(_DOWNLOADED) > MAX_DOWNLOADED:
                    _DOWNLOADED.popitem(last=False)
                _DOWNLOAD_ATTEMPTS.pop(url, None)
            else:
                attempts = _DOWNLOAD_ATTEMPTS.get(url, 0) + 1
                _DOWNLOAD_ATTEMPTS[url] = attempts
                if attempts < MAX_DOWNLOAD_ATTEMPTS:
                    # 失败退回队列，允许重试
                    _SEEN.add(url)
                    _QUEUED.append(url)
                    _QUEUE_NONEMPTY.notify()
                else:
                    _DOWNLOAD_ATTEMPTS.pop(url, None)
        if ok:
            global _RELOAD_DIRTY, _LAST_ACTIVITY
            _RELOAD_DIRTY = True
            _LAST_ACTIVITY = time.time()
            image_cache_maintenance()   # 低频磁盘缓存清理（每 100 张/10 分钟）
            time.sleep(0.05)
        else:
            time.sleep(0.3 + (attempts * 0.2))

def start_workers():
    global _CACHE_STARTED
    if _CACHE_STARTED:
        return
    _CACHE_STARTED = True
    for _ in range(WORKERS):
        threading.Thread(target=_worker, daemon=True).start()

def is_dirty():
    return _RELOAD_DIRTY

def mark_dirty():
    global _RELOAD_DIRTY, _LAST_ACTIVITY
    _RELOAD_DIRTY = True
    _LAST_ACTIVITY = time.time()

def clear_dirty():
    global _RELOAD_DIRTY
    _RELOAD_DIRTY = False

def last_activity():
    return _LAST_ACTIVITY


# ============================================================
#  基础层：全局状态与导航栈
# ============================================================


state = appui.State(
    tab=0,
    keyword="",
    status="",
    detail=None,
    detail_open=False,      # 详情页是否仍在导航栈顶
    detail_thumb="",        # 打开详情时列表项自带的缩略图（收藏封面用）
    panel="",
    panel_title="",
    play="",                # 当前播放来源："" / 预览 / 预告 / 完整视频
    src_preview="",         # 详情页预览链接（进入详情即并行预取，空表示还没取到）
    src_trailer="",         # 详情页预告链接
    src_video="",           # 详情页完整视频链接
    sample_index=0,         # 样片大图当前页（可左右滑动翻看）
    show_page_input=False,  # 页码跳转弹层（由原生 coordinator 快路径呈现/关闭）
    name_text="",           # 详情页标题的中文译文（空表示尚未翻译完成）
    title_trans=False,      # 标题是否已翻译成中文
    rating_text="",         # 详情页评分文本（JavDB）
    genre_group="全部",     # 类型 tab 当前选中的一级分类
    reload=0,
)

# 每个 tab 独立的导航栈
PATH_MOVIES = appui.NavigationPath()
PATH_ACT = appui.NavigationPath()
PATH_GENRE = appui.NavigationPath()
PATH_FAV = appui.NavigationPath()
PATH_SETTINGS = appui.NavigationPath()

# 详情/大图当前所在的导航栈（跟随打开详情的那个展示位）
DETAIL_HOST = "home"
DETAIL_PATH = PATH_MOVIES
DETAIL_OPEN_AT = 0.0
# 打开详情时的导航栈深度：on_disappear 时用于区分「返回列表」与「进入全屏」
_DETAIL_PATH_DEPTH = 0
# 每个 tab 各自的详情状态栈：[{detail, depth}, ...]，切换 tab 时同步显示该 tab 自己的详情
DETAIL_STACKS = {}


# ============================================================
#  数据层：设置持久化
# ============================================================


SET_FILE = os.path.join(os.getcwd(), "settings.json")

# 每页可选项数。
# 上限取 18 的依据：封面网格 adaptive(minimum=104)，iPhone（约 390pt 宽、
# 左右各 16pt 内边距）每行固定 3 列 —— 18 项 = 6 行；body() 每次重建时
# 需要构造约 18 组封面节点（AsyncImage + 2 个 Text + Button），
# 再加上预加载窗口里同时在下载的封面，量级仍可控。
# 继续加到 24 及以上时，单次重建的节点数、以及预加载窗口内并发下载的
# 封面数都会明显上升，图片下载完成后的去抖整树重建在老设备上容易掉帧。
PAGE_SIZE_OPTIONS = [6, 9, 12, 15, 18]
# Picker 的选项文本（三个 picker 共用同一份）
_PAGE_SIZE_OPTIONS_TEXT = [str(x) for x in PAGE_SIZE_OPTIONS]

# 每页项数按 tab 分开设置：影片 / 女优 / 收藏 各自一个值
DEFAULT_SETTINGS = {
    "page_size_movie": 9,     # 影片 tab（含搜索、跳转出来的影片列表）
    "page_size_actress": 12,  # 女优 tab（头像网格）
    "page_size_fav": 9,       # 收藏 tab
    "player": "SenPlayer",    # 外部播放器
    "mute": True,             # 视频播放是否默认静音
}

def load_settings():
    """读取设置；文件缺失/损坏时回退默认值。"""
    data = dict(DEFAULT_SETTINGS)
    try:
        if os.path.exists(SET_FILE):
            with open(SET_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                for k in data:
                    if k in saved:
                        data[k] = saved[k]
                # 旧版本只有统一的 page_size：迁移成影片的设置
                if "page_size_movie" not in saved and "page_size" in saved:
                    data["page_size_movie"] = saved["page_size"]
    except Exception:
        pass
    for key in ("page_size_movie", "page_size_actress", "page_size_fav"):
        try:
            size = int(data[key])
        except Exception:
            size = DEFAULT_SETTINGS[key]
        data[key] = size if size in PAGE_SIZE_OPTIONS else DEFAULT_SETTINGS[key]
    if data["player"] not in EXTERNAL_PLAYERS:
        data["player"] = DEFAULT_SETTINGS["player"]
    data["mute"] = bool(data["mute"])
    return data

def save_settings():
    try:
        tmp = SET_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SET_FILE)
    except Exception as e:
        log("save_settings err: " + str(e))

SETTINGS = load_settings()

# ------------------------------------------------------------------
#  底部固定分页条：GeometryReader 实测可用高度
# ------------------------------------------------------------------
# 影片 / 女优 / 收藏三个 tab 根页各包一层 GeometryReader，
# 把实测到的可用高度写进 _GRID_GEOMETRY，用于限定滚动区高度，
# 使「上一页 / 第X页 / 下一页」固定在 Tab 栏上方、不随内容滚动。
_GRID_GEOMETRY = {"w": 0.0, "h": 0.0}
PAGE_H_PAD = 16              # 展示内容左右内边距（VStack .padding()）
PAGER_ROW_H = 44             # 分页条自身高度（估）
# 分页条整体上移「半行高度」：与 Tab 栏之间留出半行空隙
PAGER_BOTTOM_PAD = PAGER_ROW_H // 2
PAGER_BLOCK_H = PAGER_ROW_H + PAGER_BOTTOM_PAD

def _size_from_info(info):
    """从 GeometryReader 回调数据里提取 (宽, 高)：兼容 dict / 元组等形态。"""
    if isinstance(info, dict):
        return info.get("width", info.get("w", 0)), info.get("height", info.get("h", 0))
    if isinstance(info, (list, tuple)) and len(info) >= 2:
        return info[0], info[1]
    return 0, 0

def remember_grid_size(info):
    """GeometryReader 回调：记录可用区域高度（供固定分页条限定滚动区用）。"""
    try:
        w, h = _size_from_info(info)
        w = float(w or 0.0)
        h = float(h or 0.0)
    except Exception:
        return
    if w <= 0 or h <= 0:
        return
    if abs(w - _GRID_GEOMETRY["w"]) < 1 and abs(h - _GRID_GEOMETRY["h"]) < 1:
        return               # 同一帧重复回调：忽略
    first = _GRID_GEOMETRY["h"] <= 0
    _GRID_GEOMETRY["w"] = w
    _GRID_GEOMETRY["h"] = h
    if first:
        state.reload += 1    # 首次测到尺寸后再重建一次，应用限定高度

def page_size_key(kind):
    """展示位的 filter.kind -> 使用哪一套每页项数。

    女优 tab 用女优的设置，收藏 tab 用收藏的设置，
    其余（首页 / 搜索 / 演员、分类等跳转出来的影片列表）都用影片的设置。
    """
    if kind == "actress":
        return "page_size_actress"
    if kind == "fav":
        return "page_size_fav"
    return "page_size_movie"

def page_size_of_kind(kind):
    """按展示位类型取每页项数。"""
    key = page_size_key(kind)
    try:
        size = int(SETTINGS[key])
    except Exception:
        size = DEFAULT_SETTINGS[key]
    return size if size in PAGE_SIZE_OPTIONS else DEFAULT_SETTINGS[key]

def page_size(vid=None):
    """每页项数：按展示位类型取；vid 为空时取影片的设置。"""
    return page_size_of_kind(view_kind(vid) if vid else "home")


# ============================================================
#  数据层：收藏持久化
# ============================================================


FAV_FILE = os.path.join(os.getcwd(), "favorites.json")

def load_shelf():
    try:
        if os.path.exists(FAV_FILE):
            with open(FAV_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"fav": []}
        if not isinstance(data, dict):
            data = {"fav": []}
        data.pop("arc", None)
        if not isinstance(data.get("fav"), list):
            data["fav"] = []
        else:
            data["fav"] = [x for x in data["fav"] if isinstance(x, dict)]
            for item in data["fav"]:
                item["img"] = item.get("img") or ""
                # 去掉日期前后空格，避免字符串排序时被排到所有人后面
                item["fav_time"] = str(item.get("fav_time") or "").strip()
            data["fav"].sort(key=lambda x: x.get("fav_time", ""), reverse=True)
        return data
    except Exception:
        return {"fav": []}

SHELF = load_shelf()

def save_shelf():
    try:
        tmp = FAV_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(SHELF, f, ensure_ascii=False, indent=2)
        os.replace(tmp, FAV_FILE)
    except Exception as e:
        log("save_shelf err: " + str(e))

def in_fav(code):
    return any(x.get("code") == code for x in SHELF["fav"])

def fav_count():
    return len(SHELF["fav"])

def now_time():
    return datetime.date.today().strftime("%Y-%m-%d")

_FAV_DIRTY = False

def mark_fav_dirty():
    """收藏有变动：收藏 tab 已加载的数据池需要重建。"""
    global _FAV_DIRTY
    _FAV_DIRTY = True

def add_fav(code, img=""):
    SHELF["fav"].insert(0, {"code": code, "img": img, "fav_time": now_time()})
    mark_fav_dirty()

def remove_fav(code):
    SHELF["fav"] = [x for x in SHELF["fav"] if x.get("code") != code]
    mark_fav_dirty()

def toggle_bookmark(d, img=""):
    code = d["code"]
    if in_fav(code):
        remove_fav(code)
    else:
        add_fav(code, img=img)
    save_shelf()


# ============================================================
#  数据层：收藏封面自动补全
#  旧收藏记录没有 img 字段，按番号后台搜索解析封面（低频限流，
#  带磁盘缓存与失败冷却，避免每次进入收藏页都重复请求）。
# ============================================================


_MOVIE_CACHE_FILE = os.path.join(tempfile.gettempdir(), "javbus_img", "shelf_movies.json")

def _load_movie_cache():
    try:
        with open(_MOVIE_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {str(code): movie for code, movie in data.items()
                if isinstance(movie, dict) and movie.get("img") and movie.get("link")}
    except Exception:
        return {}

def _save_movie_cache(movies):
    try:
        os.makedirs(os.path.dirname(_MOVIE_CACHE_FILE), exist_ok=True)
        tmp = _MOVIE_CACHE_FILE + "." + str(threading.get_ident()) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(movies, f, ensure_ascii=False)
        os.replace(tmp, _MOVIE_CACHE_FILE)
    except Exception:
        pass

_MOVIES = _load_movie_cache()
_MOVIE_PENDING = set()
_MOVIE_ATTEMPTS = {}
_MOVIE_QUEUE = queue.Queue()   # 待解析番号队列（阻塞等待，不再轮询）
_MOVIE_LOCK = threading.Lock()
_MOVIE_MAX_ATTEMPTS = 5
_MOVIE_WORKERS = 2          # 低频补全：低并发，避免洪泛触发站点限流
_MOVIE_OK_SLEEP = 0.7       # 每次成功解析后稍作停顿，进一步限流
_MOVIE_RETRY_SLEEP = 0.6    # 解析失败重试前的退避
_MOVIE_PAUSE_UNTIL = 0.0
_MOVIE_STARTED = False
_MOVIE_UNSAVED = 0
# 解析失败被放弃的番号 -> 放弃时刻；冷却期内不再重搜，
# 避免每次进入收藏页都对搜不到的番号重复请求
_MOVIE_GIVEUP = {}
_MOVIE_GIVEUP_COOL = 600

def _movie_worker():
    global _MOVIE_UNSAVED
    while True:
        # 暂停期（详情页打开等）不取任务，队列里的番号原位保留
        if time.time() < _MOVIE_PAUSE_UNTIL:
            time.sleep(0.2)
            continue
        try:
            code = _MOVIE_QUEUE.get(timeout=0.5)    # 阻塞等待，不再轮询空转
        except queue.Empty:
            continue
        try:
            result = fetch_movie_page(BASE + "/search/" + quote(code) + "/1")
        except Exception as e:
            log("fav movie fetch err: " + str(e))
            result = "empty"
        match = None
        if isinstance(result, list):
            match = next((item for item in result
                          if item.get("code", "").strip().upper() == code), None)
        snapshot = None
        retry_sleep = 0.0
        with _MOVIE_LOCK:
            attempts = _MOVIE_ATTEMPTS.get(code, 0) + 1
            _MOVIE_ATTEMPTS[code] = attempts
            if match:
                _MOVIES[code] = match
                _MOVIE_PENDING.discard(code)
                _MOVIE_UNSAVED += 1
            elif attempts < _MOVIE_MAX_ATTEMPTS:
                _MOVIE_QUEUE.put(code)
                retry_sleep = _MOVIE_RETRY_SLEEP * attempts
            else:
                _MOVIE_PENDING.discard(code)
                _MOVIE_GIVEUP[code] = time.time()
            if _MOVIE_UNSAVED >= 10 or (_MOVIE_UNSAVED and not _MOVIE_PENDING):
                snapshot = dict(_MOVIES)
                _MOVIE_UNSAVED = 0
        if snapshot:
            _save_movie_cache(snapshot)
        if match:
            try:
                request_img(match.get("img", ""), priority=True)
                mark_dirty()
            except Exception as e:
                log("fav image cache err: " + str(e))
            time.sleep(_MOVIE_OK_SLEEP)   # 成功也限流，避免连续请求
        elif retry_sleep:
            time.sleep(retry_sleep)       # 失败退避，缓解并发触发限流

def _start_movie_workers():
    global _MOVIE_STARTED
    if _MOVIE_STARTED:
        return
    _MOVIE_STARTED = True
    for _ in range(_MOVIE_WORKERS):
        threading.Thread(target=_movie_worker, daemon=True).start()

def pause_fav_movies():
    """打开详情等场景时暂停补全线程，避免与详情请求竞争。"""
    global _MOVIE_PAUSE_UNTIL
    with _MOVIE_LOCK:
        _MOVIE_PAUSE_UNTIL = time.time() + 3.0

def _fav_window_items():
    """收藏可视窗口内的条目：当前页 ± 1 页（约 3 页屏幕内容）。

    只对窗口内的收藏做封面检查 / 缺失解析 / 下载排队，
    而不是一次处理全部收藏导致大量
    磁盘 I/O 与网络请求——屏幕上一页往往只有 9 个。
    翻页 / 收藏变动会重新触发 _pump(FAV_VID)，窗口随之前后滑动。
    """
    v = VIEWS.get(FAV_VID)
    page = v["page"] if v else 1
    size = page_size(FAV_VID)
    lo = max(0, (page - 2) * size)      # 当前页前 1 页
    hi = (page + 1) * size              # 当前页 + 后 1 页
    return fav_items()[lo:hi]

def load_fav_movies():
    """收藏可视窗口内缺封面的番号排入后台补全队列；已有封面的直接请求下载。"""
    global _MOVIE_PAUSE_UNTIL
    _start_movie_workers()
    cached_images = []
    with _MOVIE_LOCK:
        _MOVIE_PAUSE_UNTIL = 0.0
        for item in _fav_window_items():
            code = str(item.get("code") or "").strip().upper()
            img = item.get("img") or ""
            if not img and code in _MOVIES:
                img = _MOVIES[code].get("img", "")
            if img:
                cached_images.append(img)
            elif code and code not in _MOVIE_PENDING:
                if code in _MOVIE_GIVEUP:
                    if time.time() - _MOVIE_GIVEUP[code] < _MOVIE_GIVEUP_COOL:
                        continue   # 冷却中，避免重复请求
                    _MOVIE_GIVEUP.pop(code, None)
                _MOVIE_PENDING.add(code)
                _MOVIE_ATTEMPTS[code] = 0
                _MOVIE_QUEUE.put(code)
    for image in reversed(cached_images):
        request_img(image, priority=True)

def fav_movie(code):
    """查某个番号已解析出的封面/链接（无则返回空 dict）。"""
    with _MOVIE_LOCK:
        return _MOVIES.get(str(code).strip().upper(), {})


# ============================================================
#  解析层：列表页 / 详情页 / 播放源
# ============================================================


def norm_keyword(kw):
    """把用户输入规整成 JavBus 可识别的番号格式（如 JUL333 -> JUL-333）。"""
    s = re.sub(r"\s+", "", kw)
    s = re.sub(r"([a-zA-Z])(?=\d)(?!-)(?<!fc)", r"\1-", s, flags=re.I)
    s = re.sub(r"(\d)(?=[a-zA-Z])(?!-)", r"\1-", s)
    return s

# ============================================================
#  解析层：预编译正则（模块级编译一次，热路径不再反复编译/查缓存）
# ============================================================

# 列表卡片：整卡区块 + 卡内字段
_RE_MOVIE_CHUNK = re.compile(r'<a class="movie-box"[\s\S]*?</span>\s', re.S)
_RE_HREF = re.compile(r'href="([^"]*)"')
_RE_IMG = re.compile(r'<img[^>]*?src="([^"]*)"')     # 允许 src 前有其它属性（懒加载等）
_RE_DATE = re.compile(r"<date>(.*?)</date>")          # 卡内第 1 条=番号，第 2 条=发行日期
_RE_GENRE_LINK = re.compile(r'href="([^"]*)">([^<]*)</a>')
_RE_GENRE_LINKS = re.compile(r'href="([^"]*)">([^<]*)</a>', re.S)
# 女优头像（详情页 avatar-box / 女优列表页 avatar-box text-center）
_RE_AVATAR_CHUNK = re.compile(r'<a class="avatar-box"[\s\S]*?</a>', re.S)
_RE_AVATAR_LIST_CHUNK = re.compile(r'<a class="avatar-box text-center"[\s\S]*?</span>', re.S)
_RE_SPAN_TEXT = re.compile(r"<span>(.*?)</span>")
_RE_TITLE_ATTR = re.compile(r'title="([^"]*)"')
# 详情页：封面/标题一次定位（常规 + 兜底）
_RE_BIGIMAGE_FULL = re.compile(r'<a class="bigImage" href="([^"]*)" title="([^"]*)"')
_RE_BIGIMAGE_HREF = re.compile(r'<a class="bigImage" href="([^"]*)"')
_RE_BIGIMAGE_TITLE = re.compile(r'<a class="bigImage"[\s\S]{0,200}?<img[^>]*title="([^"]*)"')
# 详情页：樣圖区块（大图 href + 缩略图 src 成对）
_RE_SAMPLE_PAIR = re.compile(
    r'<a class="sample-box" href="([^"]*)"[\s\S]*?<img src="([^"]*)"', re.S)
# 详情页：影片信息面板各行（"發行日期/長度/發行商/製作商/系列/導演/識別碼"）
_RE_INFO_ROWS = {key: re.compile(pat, re.S) for key, pat in {
    "time": r'<span class="header">發行日期:</span>([\s\S]*?)</p>',
    "last": r'<span class="header">長度:</span>([\s\S]*?)</p>',
    "estab": r'<span class="header">發行商:[\s\S]*?"([^"]*)">([^<]*)</a>',
    "maker": r'<span class="header">製作商:[\s\S]*?"([^"]*)">([^<]*)</a>',
    "series": r'<span class="header">系列:[\s\S]*?"([^"]*)">([^<]*)</a>',
    "director": r'<span class="header">導演:[\s\S]*?"([^"]*)">([^<]*)</a>',
    "code": r'<span class="header">識別碼:[\s\S]*?">([^<]*)</span>',
}.items()}
_RE_MINUTES = re.compile(r"(\d+)\s*分鐘")
_RE_GENRE_BLOCK = re.compile(r"類別:[\s\S]*?button", re.S)
# 类型页分组
_GENRE_GROUP_TAGS = ["主題", "角色", "服裝", "體型", "行為", "玩法", "類別"]
_RE_GENRE_GROUPS = {tag: re.compile(tag + r"</h4>([\s\S]*?)</div>", re.S)
                    for tag in _GENRE_GROUP_TAGS}
# 评分（JavDB）
_RE_SCORE_BLOCK = re.compile(r'class="score">[\s\S]*?div>')
_RE_SCORE = re.compile(r"([0-9.]+)分")
_RE_SCORE_COUNT = re.compile(r"由(\d+)人評價")

def parse_movies(html):
    """解析卡片网格 HTML，返回影片列表 dict。

    健壮性（相对原实现的边界修补）：
      - 只把「番号 + 链接」视为必需字段，缺 img 的卡片不再整卡丢弃；
      - 图片允许 src 前带其它属性（懒加载 / 防爬参数）；
      - 发行日期取卡内第二个 <date>，不再依赖 "/ <date>..</span>" 的
        相邻格式（站点标记顺序一变就会整列日期丢失）。
    """
    items = []
    for i in _RE_MOVIE_CHUNK.findall(html):
        m = _RE_HREF.search(i)
        dates = _RE_DATE.findall(i)
        if not (m and dates):
            continue        # 无链接或无番号的区块无法成为列表项
        im = _RE_IMG.search(i)
        items.append({"code": dates[0],
                      "date": dates[1] if len(dates) > 1 else "",
                      "img": im.group(1) if im else "",
                      "link": m.group(1),
                      "hd": "高清" in i, "sub": "字幕" in i})
    return items

def fetch_movie_page(url):
    """抓取一页影片列表。

    返回值严格区分三种情况：
      list     请求成功（可为空列表 = 这一页确实没有内容）
      "empty"  请求成功但确认没有更多数据（404 / 空结果页）→ 可置 exhausted
      None     网络失败 → 不代表列表结束，允许重试
    """
    html = get(url)
    if not html:
        return None
    if "404 Page Not Found" in html:
        return "empty"
    if "沒有您要的結果" in html:
        return "empty"
    return parse_movies(html)

def fetch_actresses(page):
    """抓取女优一页（实现与原 JS getInitialActress 一致）。"""
    html = get(BASE.rstrip("/") + "/actresses/" + str(page))
    if not html:
        return []
    items = []
    for i in _RE_AVATAR_LIST_CHUNK.findall(html):
        m = _RE_HREF.search(i)
        im = _RE_IMG.search(i)
        title = _RE_TITLE_ATTR.search(i)
        if not (m and title):
            continue
        items.append({"link": m.group(1),
                      "img": fill_base(im.group(1)) if im else "",
                      "name": title.group(1)})
    return items

def fetch_genres():
    """抓取分类页并按主题分组（实现与原 JS 一致）。"""
    html = get(BASE + "/genre")
    groups = []
    if not html:
        return groups
    for tag in _GENRE_GROUP_TAGS:
        g = _RE_GENRE_GROUPS[tag].search(html)
        if not g:
            continue
        cats = _RE_GENRE_LINK.findall(g.group(1))
        if cats:
            groups.append({"tag": tag,
                           "cats": [{"link": l, "name": n} for l, n in cats]})
    return groups

def build_trailer_urls(code):
    """按番号拼出候选预告链接：DMM 优先，eightcha 兜底。"""
    c = str(code or "").strip().lower()
    if not c:
        return []
    urls = []
    fanza = c.replace("-", "00", 1)
    if fanza:
        urls.append("https://cc3001.dmm.co.jp/litevideo/freepv/"
                    + fanza[0] + "/" + fanza[:3] + "/" + fanza
                    + "/" + fanza + "_sm_w.mp4")
        urls.append("https://eightcha.com/" + c + "/preview.mp4")
    return urls

def fetch_detail(url):
    """抓取并解析详情页，返回完整详情 dict。

    解析策略（把全文扫描次数从 ~15 次降到 ~5 次）：
      1. 封面 + 标题合并为一次 bigImage 定位；
      2. 影片信息面板（header 行 + 類別按钮）一次 find 切片，
         7 行字段与類別都只在切片内解析；
      3. 女优 / 样图区块结构独立，保持全文各一次 findall。
    面板定位不可靠时（找不到 / 切片内缺關鍵行）自动回退全文，宁多扫不漏项。
    """
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

    # 封面 + 标题（标题在 <a class="bigImage" href="..." title="..."> 上，与原 JS 一致）
    t = _RE_BIGIMAGE_FULL.search(html)
    if t:
        d["cover"] = t.group(1)
        d["name"] = t.group(2).strip()
    else:
        t = _RE_BIGIMAGE_HREF.search(html)
        if t:
            d["cover"] = t.group(1)
        # 兜底：个别页面 title 属性在 <a> 内的 <img> 上
        t = _RE_BIGIMAGE_TITLE.search(html)
        if t:
            d["name"] = t.group(1).strip()

    # 大区块定位：影片信息面板（header 行与類別按钮都在其中）
    panel_start = html.find('<div class="movie-info">')
    if panel_start >= 0:
        panel_end = html.find("sample-box", panel_start)
        info = html[panel_start:panel_end if panel_end > panel_start else len(html)]
        # 切片内缺关键行说明结构有变：退回全文，宁可多扫不可漏项
        if not _RE_INFO_ROWS["code"].search(info):
            info = html
    else:
        info = html

    t = _RE_INFO_ROWS["time"].search(info)
    if t:
        d["time"] = t.group(1).strip()
    t = _RE_INFO_ROWS["last"].search(info)
    if t:
        dm = _RE_MINUTES.search(t.group(1))
        d["last"] = dm.group(1) if dm else t.group(1).strip()
    for key, field in (("estab", "estab"), ("maker", "maker"),
                       ("series", "series"), ("director", "director")):
        t = _RE_INFO_ROWS[key].search(info)
        if t:
            d[field] = t.group(2)
            d[field + "_link"] = t.group(1)
    t = _RE_INFO_ROWS["code"].search(info)
    if t:
        d["code"] = t.group(1)
    tg = _RE_GENRE_BLOCK.search(info) or _RE_GENRE_BLOCK.search(html)
    if tg and "label" in tg.group(0):
        d["genres"] = [{"link": l, "name": n} for l, n in
                       _RE_GENRE_LINKS.findall(tg.group(0))]

    for i in _RE_AVATAR_CHUNK.findall(html):
        name = _RE_SPAN_TEXT.search(i)
        link = _RE_HREF.search(i)
        img = _RE_IMG.search(i)
        if name and link:
            d["actresses"].append({"name": name.group(1),
                                   "link": link.group(1),
                                   "img": fill_base(img.group(1)) if img else ""})
    for big, thumb in _RE_SAMPLE_PAIR.findall(html):
        d["samples"].append({"link": big, "img": thumb})
    urls = build_trailer_urls(d["code"])
    if urls:
        d["trailer"] = urls[0]
    if len(urls) > 1:
        d["trailer2"] = urls[1]
    return d

def fetch_jable(code):
    """返回 (preview_url, full_m3u8)；失败返回 ('', '')。"""
    try:
        search_url = "https://jable.tv/search/" + code + "/"
        resp = network.get(search_url, headers=dict(HEADERS), timeout=15)
        if not resp or not resp.ok:
            return "", ""
        search_html = resp.text or ""
        if "部影片" not in search_html:
            return "", ""
        preview = ""
        pre = re.search(r'data-preview="(https[^"]*_preview\.mp4)"', search_html)
        if not pre:
            pre = re.search(r'data-preview="(https[^"\']*?_preview\.mp4)', search_html)
        if pre:
            preview = pre.group(1)
        links = re.findall(r'https://jable\.tv/videos/[^"\')\s]+', search_html)
        if not links:
            links = ["https://jable.tv" + u for u in
                     re.findall(r'href="(/videos/[^"]+)"', search_html)]
        cands = [l for l in links if code.lower() in l.lower()]
        if not cands:
            cands = links
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
                    break
        return preview, full
    except Exception as e:
        log("jable err: " + str(e))
        return "", ""


# ============================================================
#  数据层：详情页播放源并行预取
#  进入详情就按番号同时去取「预览 / 预告 / 完整视频」三条链接：
#  Jable 一次搜索即可解析出预览与完整视频，预告由候选链接探测，
#  两路线程并行；只有取到的链接才点亮对应按钮，取不到的保持空串（按钮置灰）。
# ============================================================


# 来源名 -> 对应的 State 字段
SOURCE_FIELDS = {"preview": "src_preview",
                 "trailer": "src_trailer",
                 "video": "src_video"}
# 每次预取同时开几路任务（Jable 一路 + 预告探测一路）
SOURCE_TASK_COUNT = 2
# 链接缓存条数与有效期（秒）：重进同一番号直接复用，不再重复请求
_LINK_CACHE = {}
_LINK_CACHE_MAX = 64
_LINK_TTL = 30 * 60
_LINK_INFLIGHT = {}     # 番号 -> seq（正在预取）
_LINK_PENDING = {}      # seq -> {"code":..., "values":{...}, "left":n}
_LINK_SEQ = 0
_LINK_LOCK = threading.Lock()

def _url_alive(url, timeout=10):
    """探测链接是否可用：HEAD 优先，不支持时退回只读一小段的 GET。"""
    if not url:
        return False
    try:
        resp = network.request("HEAD", url, headers=dict(HEADERS), timeout=timeout)
        if resp is not None and resp.ok:
            return True
    except Exception:
        pass
    try:
        with network.stream("GET", url, headers=dict(HEADERS), timeout=timeout) as resp:
            if resp is None or not resp.ok:
                return False
            resp.read(max_bytes=1024)
            return True
    except Exception:
        return False
    return False

def _submit_sources(code, seq, values):
    """后台线程收口：结果写入缓存，并交给主线程提交到界面。"""
    with _LINK_LOCK:
        if _LINK_INFLIGHT.get(code) != seq:
            return
        rec = _LINK_CACHE.get(code) or {"preview": "", "trailer": "", "video": ""}
        for key, value in values.items():
            # 只缓存取到的链接，避免把上一次的结果冲掉
            if value:
                rec[key] = value
        rec["ts"] = time.time()
        _LINK_CACHE[code] = rec
        while len(_LINK_CACHE) > _LINK_CACHE_MAX:
            _LINK_CACHE.pop(next(iter(_LINK_CACHE)))
        item = _LINK_PENDING.get(seq)
        if item is None:
            item = {"code": code, "values": {}, "left": SOURCE_TASK_COUNT}
            _LINK_PENDING[seq] = item
        item["values"].update(values)
        item["left"] -= 1
        if item["left"] <= 0:
            _LINK_INFLIGHT.pop(code, None)

def _jable_sources_worker(code, seq):
    """Jable：一次搜索同时解析出预览与完整视频。"""
    try:
        preview, full = fetch_jable(code.lower())
    except Exception as e:
        log("jable prefetch err: " + str(e))
        preview, full = "", ""
    _submit_sources(code, seq, {"preview": preview or "", "video": full or ""})

def _trailer_source_worker(code, seq):
    """预告：候选链接逐个探测，取第一个可用的。"""
    url = ""
    for cand in build_trailer_urls(code):
        if _url_alive(cand):
            url = cand
            break
    _submit_sources(code, seq, {"trailer": url})

def prefetch_play_sources(code):
    """进入详情页时并行预取三条播放链接；取不到的保持空串（按钮置灰）。"""
    global _LINK_SEQ
    state.src_preview = ""
    state.src_trailer = ""
    state.src_video = ""
    code = str(code or "").strip().upper()
    if not code:
        return
    with _LINK_LOCK:
        cached = _LINK_CACHE.get(code)
        # 缓存里至少有一条链接且未过期才复用，否则重新去取（避免一次失败就长期置灰）
        if cached and time.time() - cached.get("ts", 0) <= _LINK_TTL \
                and (cached.get("preview") or cached.get("trailer") or cached.get("video")):
            state.src_preview = cached.get("preview", "")
            state.src_trailer = cached.get("trailer", "")
            state.src_video = cached.get("video", "")
            return
        if _LINK_INFLIGHT.get(code):
            return          # 同一番号正在预取，结果回来后由主线程统一提交
        _LINK_SEQ += 1
        seq = _LINK_SEQ
        _LINK_INFLIGHT[code] = seq
    _TASK_POOL.submit(_jable_sources_worker, code, seq)
    _TASK_POOL.submit(_trailer_source_worker, code, seq)

def _commit_sources():
    """主线程：把后台取到的链接写回 State（只认当前详情的番号）。"""
    global _LINK_PENDING
    with _LINK_LOCK:
        if not _LINK_PENDING:
            return
        items = list(_LINK_PENDING.values())
        _LINK_PENDING = {}
    if not state.detail_open:
        return
    code = str((state.detail or {}).get("code") or "").strip().upper()
    if not code:
        return
    changed = False
    for item in items:
        if str(item.get("code") or "") != code:
            continue
        for key, value in (item.get("values") or {}).items():
            field = SOURCE_FIELDS.get(key)
            if not field or not value:
                continue
            if state.get(field) != value:
                state[field] = value
                changed = True
    if changed:
        state.reload += 1


# ============================================================
#  展示层：展示位注册表
#  每个展示位 = 筛选条件 + 附加设置 + 所属导航栈 + 翻页数据
# ============================================================


HOME_FILTER = {"kind": "home", "title": "最新影片"}
HOME_VID = "home"
ACTRESS_VID = "actress"
GENRE_VID = "genre"
FAV_VID = "fav"

def new_view(flt, extras, path):
    """创建一个展示位。

    flt    筛选条件：kind=home / search / link / actress / genre / fav，
           决定抓什么数据
    extras 附加设置：search 搜索框、refresh 下拉刷新、status 提示行
    path   所属导航栈：详情与跳转列表都推入这个栈
    """
    return {
        "filter": flt,
        "extras": extras,
        "path": path,
        "page": 1,          # 当前页码（1 起）
        "pool": [],         # 已抓到的数据池，只追加不重排（顺序固定从新到旧）
        "base": 0,          # pool[0] 对应的全局序号（回收头部数据后前移）
        "remote": 1,        # 下一个待抓的远程页码
        "loading": False,
        "exhausted": False, # 远程已无更多内容
        "generation": 0,    # 递增代号：筛选/数据池重置后 +1，在途 worker 结果作废
    }

VIEWS = {
    # 影片 tab 根页：有搜索框、可下拉刷新
    HOME_VID: new_view(HOME_FILTER,
                       {"search": True, "refresh": True, "status": True},
                       PATH_MOVIES),
    # 女优 tab：头像网格 + 翻页，点击进入该女优的作品列表
    ACTRESS_VID: new_view({"kind": "actress", "title": "女优"},
                          {"refresh": True}, PATH_ACT),
    # 类型 tab：按主题分组的分类按钮（单次抓取，无翻页）
    GENRE_VID: new_view({"kind": "genre", "title": "类型"},
                        {"refresh": True}, PATH_GENRE),
    # 收藏 tab：封面网格 + 翻页，数据来自收藏记录
    FAV_VID: new_view({"kind": "fav", "title": "收藏"},
                      {"refresh": True}, PATH_FAV),
}

_VID_SEQ = [0]

def new_vid(prefix="list"):
    _VID_SEQ[0] += 1
    return prefix + str(_VID_SEQ[0])

# 推入过的跳转列表展示位（按顺序），仅在导航载荷没回传时用于兜底
_PUSHED_VIDS = []

def push_list(path, vid):
    """推入一个跳转列表页。

    NavigationPath.append 的载荷必须写成 {"tag": ..., "data": ...}：
    运行时按 tag 查 destinations，并把 data 原样传给对应 builder。
    """
    _PUSHED_VIDS.append(vid)
    if len(_PUSHED_VIDS) > 50:
        del _PUSHED_VIDS[:25]
    path.append({"tag": "list", "data": {"vid": vid}})

# 根展示位永不回收；动态展示位（详情内跳转的筛选列表）超过上限时回收最旧的
ROOT_VIDS = {HOME_VID, ACTRESS_VID, GENRE_VID, FAV_VID}
MAX_DYNAMIC_VIEWS = 12

def gc_views():
    """动态展示位生命周期回收（简单上限法，不做 LRU）。

    只删除同时满足以下条件的展示位：
      - 非根展示位；
      - 已不在导航链上（不在 _PUSHED_VIDS / DETAIL_STACKS / DETAIL_HOST）；
      - 没有在途 worker（loading=False）。
    回收顺序从最旧开始，保留最新的 MAX_DYNAMIC_VIEWS 个。
    """
    dynamic = [vid for vid in VIEWS if vid not in ROOT_VIDS]
    if len(dynamic) <= MAX_DYNAMIC_VIEWS:
        return
    keep = set(_PUSHED_VIDS) | set(DETAIL_STACKS)
    if DETAIL_HOST:
        keep.add(DETAIL_HOST)
    with _VIEWS_LOCK:
        for vid in dynamic[:-MAX_DYNAMIC_VIEWS]:    # dict 保持插入序：最旧优先
            if vid in keep:
                continue
            v = VIEWS.get(vid)
            if not v or v["loading"]:
                continue      # 在途 worker 结束后，下一轮再回收
            del VIEWS[vid]
        # 同步清掉指向已回收展示位的陈旧引用
        _PUSHED_VIDS[:] = [vid for vid in _PUSHED_VIDS if vid in VIEWS]

def view_title(vid):
    """展示位标题（导航栏）。"""
    v = VIEWS.get(vid)
    if not v:
        return APP_TITLE
    flt = v["filter"]
    if flt["kind"] == "home":
        return APP_TITLE
    return flt.get("title") or "影片列表"

def view_kind(vid):
    """展示位的筛选类型。"""
    v = VIEWS.get(vid)
    return v["filter"]["kind"] if v else ""

def view_url(v, page):
    """按筛选条件拼出第 page 个远程页的 URL。"""
    flt = v["filter"]
    kind = flt["kind"]
    if kind == "home":
        return BASE + "/page/" + str(page)
    if kind == "search":
        return BASE + "/search/" + quote(flt.get("keyword", "")) + "/" + str(page)
    if kind == "link":
        link = fill_base(flt.get("link", ""))
        if not link:
            return ""
        return link.rstrip("/") + "/" + str(page)
    return ""

def fetch_view_page(v, page):
    """按展示位类型抓取一页数据；无结果返回 [] 或 'empty'。"""
    kind = v["filter"]["kind"]
    if kind == "actress":
        return fetch_actresses(page)
    return fetch_movie_page(view_url(v, page))

def fav_items():
    """收藏列表的数据源：由收藏记录构造，按收藏时间（date）从新到旧。"""
    out = []
    for item in SHELF["fav"]:
        code = str(item.get("code") or "").strip().upper()
        if not code:
            continue
        out.append({"code": code,
                    "img": item.get("img") or "",
                    "date": str(item.get("fav_time") or "").strip(),
                    "link": BASE + "/" + quote(code)})
    return sorted(out, key=lambda x: x.get("date") or "", reverse=True)

def sort_new_items(items):
    """固定顺序：发布时间从新到旧。

    只对「本次新抓到的一批」排序，绝不重排整个数据池，
    否则后续增量加载会把已经翻过的页码内容重新洗牌（表现为当前内容被覆盖）。
    """
    return sorted(items, key=lambda x: x.get("date") or "", reverse=True)

def pool_end(v):
    """数据池末尾对应的全局序号（不含）。

    注意：裸读不持锁；需要跨多个字段的一致性快照时，
    由调用方持有 _VIEWS_LOCK 后调用（所有调用方均已如此）。
    """
    return v["base"] + len(v["pool"])

def page_items(vid):
    """当前页要显示的影片：按已固定的数据池顺序直接切片。"""
    v = VIEWS.get(vid)
    if not v:
        return []
    size = page_size(vid)
    with _VIEWS_LOCK:      # 短临界区：切片即快照，锁外不再访问共享字段
        start = (v["page"] - 1) * size - v["base"]
        if start < 0:
            return []
        return list(v["pool"][start:start + size])

def page_loading(vid):
    """当前页还没被数据池完整覆盖（用于在网格下方显示加载指示）。"""
    v = VIEWS.get(vid)
    if not v:
        return False
    with _VIEWS_LOCK:
        return pool_end(v) < v["page"] * page_size(vid) and not v["exhausted"]

def can_next(vid):
    """是否还能往后翻。"""
    v = VIEWS[vid]
    with _VIEWS_LOCK:
        if pool_end(v) > v["page"] * page_size(vid):
            return True
        return not v["exhausted"]


# ============================================================
#  展示层：数据抓取（增量追加 + 预加载窗口）
# ============================================================


# 当前页之外额外预加载的页数：翻到最后一页时，下一页的数据已经在路上
PRELOAD_AHEAD_PAGES = 2
# 一轮后台任务最多抓几个远程页（避免一次性加载过多造成内存与限流压力）
MAX_FETCH_PER_ROUND = 2
# 同一轮内两次远程请求之间的间隔（秒）
FETCH_GAP = 0.3
# 数据池最多保留的页数，超出后只回收「当前页之前」的旧数据
POOL_LIMIT_PAGES = 24

_VIEWS_DIRTY = False
# 按展示位隔离的脏标记：不可见展示位的数据变化不触发整树重建，
# 标记保留到该展示位可见时（翻回该 tab / 关闭详情）再消费
_DIRTY_VIDS = set()

def _view_visible(vid):
    """展示位当前是否可能显示在屏幕上（属于当前 tab，或它正承载详情）。"""
    v = VIEWS.get(vid)
    if not v:
        return True       # 未知展示位：保守视为可见
    root = TAB_ROOT_VIDS.get(state.tab)
    cur_path = VIEWS[root]["path"] if root in VIEWS else None
    if cur_path is not None and v["path"] is cur_path:
        return True       # 属于当前 tab 的导航栈
    return vid == DETAIL_HOST and vid in VIEWS
# VIEWS 共享字段的短临界区锁：只保护 pool/base/remote/exhausted/loading 的
# 一致性读写，不包裹网络请求与 UI 计算（避免 UI 线程与 worker 互相阻塞）
_VIEWS_LOCK = threading.Lock()

def mark_views_dirty(vid=None):
    """标记展示数据已变化，等主线程刷新。

    指明 vid 时按展示位隔离：_sync_dirty 只在展示位可见时才触发重建，
    后台为隐藏 tab 预加载 / 补数据不再引起界面重建。
    """
    global _VIEWS_DIRTY
    if vid is None:
        _VIEWS_DIRTY = True     # 未指明来源：保守处理，无条件刷新
    else:
        _DIRTY_VIDS.add(vid)

def preload_ahead(v):
    """预加载页数：每页项数越大，预加载页数越少，控制同时下载与渲染的封面量。"""
    return 1 if page_size() >= 12 else 2

def load_window_end(v):
    """预加载窗口末尾（全局序号，不含）。"""
    return (v["page"] + preload_ahead(v)) * page_size()

def _trim(v, size):
    """数据池超过上限时，从头部回收当前页之前的旧数据。

    只回收已经翻过的部分，当前页及之后的内容不会被丢弃。
    """
    limit = POOL_LIMIT_PAGES * size
    if len(v["pool"]) <= limit:
        return
    keep_from = (v["page"] - 1) * size - v["base"]   # 当前页起点在 pool 中的下标
    drop = min(len(v["pool"]) - limit, max(0, keep_from))
    if drop <= 0:
        return
    del v["pool"][:drop]
    v["base"] += drop

def _pump(vid, force=False):
    """补足展示位的预加载窗口；不足则后台增量抓取。"""
    v = VIEWS.get(vid)
    if not v:
        return
    kind = v["filter"]["kind"]
    if kind == "fav":
        # 收藏：本地数据一次取全；已加载且非显式要求时不重复重建
        with _VIEWS_LOCK:
            if not (v["exhausted"] and not force):
                v["pool"] = fav_items()
                v["base"] = 0
                v["remote"] = 1
                v["exhausted"] = True
                v["loading"] = False
        # 可视窗口的封面检查 / 解析 / 下载：数据池未重建（仅翻页）时也要滑动窗口
        load_fav_movies()
        mark_views_dirty(vid)
        return
    if kind == "genre":
        # 分类：单次抓取全部分组，无翻页
        with _VIEWS_LOCK:
            if v["exhausted"] and not force:
                return
            if v["loading"]:
                return
            v["loading"] = True
            gen = v["generation"]
        threading.Thread(target=_genre_worker, args=(vid, gen), daemon=True).start()
        return
    with _VIEWS_LOCK:
        if v["loading"] or v["exhausted"]:
            return
        if pool_end(v) >= load_window_end(v):
            return
        v["loading"] = True
        gen = v["generation"]
    threading.Thread(target=_pump_worker, args=(vid, gen), daemon=True).start()

def _genre_worker(vid, gen):
    """后台抓取分类分组（一次抓完，无翻页）。gen 校验防止 stale 提交。"""
    v = VIEWS.get(vid)
    if not v:
        return
    try:
        groups = fetch_genres()
        with _VIEWS_LOCK:
            if VIEWS.get(vid) is not v or v["generation"] != gen:
                return      # 结果已过期：丢弃
            v["pool"] = groups if isinstance(groups, list) else []
            v["exhausted"] = True
    except Exception as e:
        log("genre err: " + str(e))
        # 失败不置 exhausted：loading 复位后由下轮 _pump 自动重试
    finally:
        with _VIEWS_LOCK:
            if VIEWS.get(vid) is v and v["generation"] == gen:
                v["loading"] = False
        mark_views_dirty(vid)

def _pump_worker(vid, gen):
    """后台抓远程页：一轮最多抓 MAX_FETCH_PER_ROUND 页，只追加不覆盖。

    与详情页 _DETAIL_SEQ 同一套设计：worker 启动时记录 generation，
    每次准备提交结果前校验「这个结果还是不是当前状态需要的」，
    筛选切换 / 数据池重置后的在途结果一律作废。
    """
    v = VIEWS.get(vid)
    if not v:
        return
    try:
        fetched = 0
        while fetched < MAX_FETCH_PER_ROUND:
            with _VIEWS_LOCK:
                if VIEWS.get(vid) is not v or v["generation"] != gen:
                    return      # stale：用户已切换筛选或重置数据池
                if pool_end(v) >= load_window_end(v) or v["exhausted"]:
                    break
            res = fetch_view_page(v, v["remote"])       # 网络请求在锁外
            if res is None:
                # 网络失败 ≠ 没有更多数据：不置 exhausted，留给下轮 _pump 重试
                log("pump net err: page " + str(v["remote"]))
                break
            with _VIEWS_LOCK:
                if VIEWS.get(vid) is not v or v["generation"] != gen:
                    return
                if res == "empty" or not res:
                    v["exhausted"] = True
                    break
                # 增量追加：新数据排在已有数据之后，已翻过的页码内容不受影响
                v["pool"].extend(sort_new_items(res))
                v["remote"] += 1
                _trim(v, page_size(vid))
            fetched += 1
            for m in res:
                request_img(m.get("img") or "")
            mark_views_dirty(vid)
            if fetched < MAX_FETCH_PER_ROUND:
                time.sleep(FETCH_GAP)
    except Exception as e:
        log("pump err: " + str(e))
    finally:
        with _VIEWS_LOCK:
            if VIEWS.get(vid) is v and v["generation"] == gen:
                v["loading"] = False
        mark_views_dirty(vid)

def pump_all_views():
    """定时补足各展示位的预加载窗口（每轮只抓少量，逐步填充）。"""
    for vid in list(VIEWS):
        _pump(vid)

def set_filter(vid, flt):
    """切换展示位的筛选条件（重置翻页状态并重新抓取）。"""
    v = VIEWS.get(vid)
    if not v:
        return
    with _VIEWS_LOCK:
        v["filter"] = flt
        v["page"] = 1
        v["pool"] = []
        v["base"] = 0
        v["remote"] = 1
        v["exhausted"] = False
        v["loading"] = False
        v["generation"] += 1    # 旧筛选的在途 worker 结果全部作废
    _pump(vid)
    state.reload += 1

def reset_view(vid):
    """按当前筛选条件重新加载（下拉刷新 / 设置变更后）。"""
    v = VIEWS.get(vid)
    if v:
        set_filter(vid, v["filter"])

def apply_page(vid, page):
    """应用页码（含回收与越界处理）；只改数据不触发界面刷新。"""
    v = VIEWS.get(vid)
    if not v:
        return False
    page = max(1, int(page))
    with _VIEWS_LOCK:
        size = page_size(vid)
        if (page - 1) * size < v["base"]:
            # 该页已被回收，回到第 1 页重新累积，避免一次性回抓大量历史页
            page = 1
            v["pool"] = []
            v["base"] = 0
            v["remote"] = 1
            v["exhausted"] = False
            v["generation"] += 1    # 数据池重置：在途 worker 结果作废
        elif v["exhausted"]:
            # 已知列表总长时，不允许跳过最后一页
            page = min(page, max(1, (pool_end(v) + size - 1) // size))
        if page != v["page"]:
            v["page"] = page
    _pump(vid)
    return True

def goto_page(vid, page):
    """翻页：页码立即生效，缺失的数据由后台增量补足。"""
    if apply_page(vid, page):
        state.reload += 1

def max_page(vid):
    """已知的最大页码；列表尚未取完时返回 None。"""
    v = VIEWS.get(vid)
    if not v:
        return 1
    with _VIEWS_LOCK:
        if v["exhausted"]:
            size = page_size(vid)
            return max(1, (pool_end(v) + size - 1) // size)
    return None

# 页码弹层的临时输入（普通变量：按键时不写入 State，避免每次按键整树重建闪动）
_PAGE_INPUT = {"vid": "", "value": ""}
# 根视图 sheet 注册的呈现字段（由原生 coordinator 快路径呈现/关闭）
SHEET_PAGE_INPUT = "show_page_input"

def open_page_input(vid):
    """点击「第 X 页」：呈现页码弹层。

    走原生 PresentationCoordinator 快路径，不触发 body() 重建，
    因此原有界面不会闪动、也不会滚动回顶部。
    """
    _PAGE_INPUT["vid"] = vid
    _PAGE_INPUT["value"] = ""
    appui.presentation_present(SHEET_PAGE_INPUT)

def set_page_input_value(v):
    _PAGE_INPUT["value"] = v      # 只记录，不写 State：按键不触发整树重建

def cancel_page_input():
    appui.presentation_dismiss(SHEET_PAGE_INPUT)

def submit_page_input():
    """跳页：先走快路径关闭弹层，仅在页码有效时才刷新列表。"""
    vid = _PAGE_INPUT["vid"]
    try:
        page = int(str(_PAGE_INPUT["value"]).strip())
    except Exception:
        page = 0
    appui.presentation_dismiss(SHEET_PAGE_INPUT)
    if page >= 1 and apply_page(vid, page):
        state.reload += 1

def page_input_view():
    """页码跳转弹层（注册在根视图的 sheet 上，由原生 coordinator 呈现）。"""
    return appui.Form([
        appui.Section([
            appui.TextField("输入页码", text="", on_change=set_page_input_value,
                            keyboard_type="number", submit_label="go")
                .on_submit(submit_page_input),
        ], header="跳转到页码",
           footer="输入页码后点击「跳转」；未加载的页会按需抓取，"
                  "列表已取完时会自动收敛到最后一页。"),
        appui.Section([
            appui.HStack([
                appui.Button("跳转", action=submit_page_input)
                    .button_style("bordered")
                    .frame(max_width=appui.infinity),
                appui.Button("取消", action=cancel_page_input)
                    .button_style("bordered")
                    .frame(max_width=appui.infinity),
            ], spacing=8),
        ]),
    ])


# ============================================================
#  调度层：详情 / 播放 / 刷新的后台任务与主线程提交
# ============================================================


_DETAIL_READY = None
_DETAIL_ERROR = False
_DETAIL_SEQ = 0
_PLAY_REQUEST = None
_PLAY_ERROR = ""
_BG_STARTED = False
# 短任务线程池：详情抓取 / 翻译 / 评分 / 播放源共用。
# 以前打开一次详情要起约 5 个短生命周期线程，快速进出详情会反复创建；
# 统一入池（图片下载 ×3、收藏解析 ×2 仍为常驻消费者，不走此池）
_TASK_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="task")

# 导航转场静默期：push/pop 期间的后台刷新暂缓，避免打断转场动画
_RELOAD_SILENT_UNTIL = 0.0
_NAV_SILENCE = 0.8
_DETAIL_SAFE_AFTER = 0.6
_LAST_TAB = -1
_LAST_TAB_SWITCH = 0.0
TAB_RELOAD_GRACE = 0.6

# 图片刷新去抖
_LAST_IMG_RELOAD = 0.0
IMG_SILENCE_INTERVAL = 0.9
IMG_MAX_RELOAD_INTERVAL = 3.0
IMG_RELOAD_MIN_GAP = 2.0
IMG_MAX_RELOAD_LONG = 6.0
IMG_RELOAD_MIN_GAP_DETAIL = 2.5

def note_nav_action():
    """导航/转场前调用：开启静默窗。"""
    global _RELOAD_SILENT_UNTIL
    _RELOAD_SILENT_UNTIL = time.time() + _NAV_SILENCE

def reload_allowed():
    """当前是否允许整树刷新。"""
    return time.time() >= _RELOAD_SILENT_UNTIL

def detail_commit_allowed():
    """详情提交是否允许立即刷新（已避开返回转场）。"""
    if reload_allowed():
        return True
    if state.detail_open and DETAIL_OPEN_AT > 0 \
            and time.time() - DETAIL_OPEN_AT >= _DETAIL_SAFE_AFTER:
        return True
    return False

def request_detail(link):
    global _DETAIL_READY, _DETAIL_ERROR, _DETAIL_SEQ
    _DETAIL_SEQ += 1
    seq = _DETAIL_SEQ
    _DETAIL_READY = None
    _DETAIL_ERROR = False
    _TASK_POOL.submit(_detail_worker, link, seq)

def take_ready(link):
    """取回后台已抓好的同链接详情（重进同一番号时秒开）。"""
    global _DETAIL_READY
    if _DETAIL_READY and _DETAIL_READY.get("link") == link \
            and not _DETAIL_READY.get("error"):
        r = _DETAIL_READY
        _DETAIL_READY = None
        return r
    return None

def _detail_worker(link, seq):
    global _DETAIL_READY, _DETAIL_ERROR
    if not link:
        return
    try:
        result = fetch_detail(link)
        if seq == _DETAIL_SEQ:
            _DETAIL_READY = result
    except Exception:
        if seq == _DETAIL_SEQ:
            _DETAIL_ERROR = True

def set_play_request(url, title, source):
    global _PLAY_REQUEST, _PLAY_ERROR
    _PLAY_REQUEST = (url, title, source)
    _PLAY_ERROR = ""

def set_play_error(message):
    global _PLAY_REQUEST, _PLAY_ERROR
    _PLAY_REQUEST = None
    _PLAY_ERROR = message

def _sync_dirty():
    """主线程周期任务：图片刷新 + 列表提交 + 播放请求 + 详情提交。"""
    global _PLAY_REQUEST, _PLAY_ERROR, _VIEWS_DIRTY, _LAST_IMG_RELOAD
    global _LAST_TAB, _LAST_TAB_SWITCH, _FAV_DIRTY
    now = time.time()
    if state.tab != _LAST_TAB:
        # 兜底复位：若 on_change 回调未触发（纯绑定同步），这里也能
        # 检测到切换并把停在详情页的旧 tab 退回主页面
        leave_tab_reset(_LAST_TAB)
        _LAST_TAB = state.tab
        _LAST_TAB_SWITCH = now
    settled = reload_allowed() and (now - _LAST_TAB_SWITCH) >= TAB_RELOAD_GRACE

    # 收藏变动后重建收藏 tab 的数据池（保持当前页码不变）
    if _FAV_DIRTY:
        _FAV_DIRTY = False
        fv = VIEWS.get(FAV_VID)
        if fv and fv["exhausted"]:
            fv["pool"] = fav_items()
            fv["base"] = 0
            load_fav_movies()
            mark_views_dirty(FAV_VID)

    if is_dirty():
        quiet = now - last_activity() >= IMG_SILENCE_INTERVAL
        detail = state.detail_open
        max_wait = IMG_MAX_RELOAD_LONG if detail else IMG_MAX_RELOAD_INTERVAL
        min_gap = IMG_RELOAD_MIN_GAP_DETAIL if detail else IMG_RELOAD_MIN_GAP
        overdue = now - _LAST_IMG_RELOAD >= max_wait
        if (quiet or overdue) and settled and now - _LAST_IMG_RELOAD >= min_gap:
            clear_dirty()
            _LAST_IMG_RELOAD = now
            state.reload += 1

    if (_VIEWS_DIRTY or _DIRTY_VIDS) and settled:
        # 可见性隔离：只在本轮有「屏幕上可能显示的」脏展示位时才重建。
        # 一次重建刷新整棵树，因此可见脏位存在时顺带消费全部标记；
        # 全部不可见时保留标记，等翻回对应 tab / 关闭详情后再刷新。
        if _VIEWS_DIRTY or any(_view_visible(vid) for vid in _DIRTY_VIDS):
            state.reload += 1
            _VIEWS_DIRTY = False
            _DIRTY_VIDS.clear()

    # 翻到已加载内容的末尾后，继续把预加载窗口填满（每轮只抓少量）
    if settled:
        pump_all_views()

    if _PLAY_REQUEST and settled:
        url, title, source = _PLAY_REQUEST
        _PLAY_REQUEST = None
        state.status = ""
        play_url(url, title, source=source)
    elif _PLAY_ERROR and settled:
        state.status = _PLAY_ERROR
        _PLAY_ERROR = ""
        state.reload += 1

    _commit_detail()
    _commit_translation()
    _commit_rating()
    _commit_sources()

def _commit_detail():
    global _DETAIL_READY, _DETAIL_ERROR
    if _DETAIL_READY is not None:
        d = _DETAIL_READY
        _DETAIL_READY = None
        cur = state.detail
        if not state.detail_open:
            if cur and cur.get("link") == d.get("link"):
                _DETAIL_READY = d
            return
        if cur and cur.get("link") != d.get("link"):
            return
        if not detail_commit_allowed():
            _DETAIL_READY = d
            return
        log("detail ready code=" + str(d.get("code")))
        if d.get("error"):
            if cur and cur.get("_loading"):
                cur["_loading"] = False
                cur["error"] = True
            state.reload += 1
            return
        if not d.get("code") and cur and cur.get("code"):
            d["code"] = cur["code"]
        if not d.get("cover") and cur and cur.get("cover"):
            d["cover"] = cur["cover"]
        if cur:
            for k, v in d.items():
                cur[k] = v
            cur.pop("_loading", None)
            cur.pop("error", None)
        else:
            state.detail = d
        for a in d["actresses"]:
            request_img(a["img"], priority=True)
        request_img(d["cover"], priority=True)
        # 缩略图进入详情即加载；大图不预取，点击查看大图时才加载（见 show_sample）
        for s in d["samples"]:
            request_img(s["img"], priority=True)
        # 标题默认翻译成中文展示（封面下方那一行）
        state.name_text = d.get("name") or ""
        state.title_trans = False
        translate_title_async(d)
        # JavDB 评分（发行日期下一行展示）
        state.rating_text = ""
        rating_async(d)
        state.reload += 1
    elif _DETAIL_ERROR:
        _DETAIL_ERROR = False
        if not state.detail_open:
            return
        cur = state.detail
        if cur and cur.get("_loading"):
            cur["_loading"] = False
            cur["error"] = True
        state.reload += 1

# ============================================================
#  调度层：标题翻译（接口与原 JS translate() 一致）
# ============================================================


TRANS_URL = ("https://translate.google.hk/translate_a/single"
             "?client=it&dt=t&dt=rmt&dt=bd&dt=rms&dt=qca&dt=ss&dt=md&dt=ld&dt=ex"
             "&otf=3&dj=1&hl=zh_CN&ie=UTF-8&oe=UTF-8&sl=auto&tl=zh-CN&q=")
TRANS_HEADERS = {
    "User-Agent": "GoogleTranslate/5.8.58002 (iPhone; iOS 10.3; zh_CN; iPhone8,1)",
}

_TRANS_CACHE = {}          # 日文原文 -> 中文译文
_TRANS_READY = None        # {"seq","ok","text","link"}，后台线程写入、主线程提交
_TRANS_SEQ = 0

def fetch_translation(text):
    """按原 JS 的翻译接口把标题翻译成中文；失败返回空串。"""
    try:
        resp = network.get(TRANS_URL + quote(text, safe=""),
                           headers=dict(TRANS_HEADERS), timeout=15)
        if not resp or not resp.ok:
            return ""
        data = json.loads(resp.text)
        sentences = data.get("sentences") or []
        out = "".join(s.get("trans", "") for s in sentences)
        return out.strip()
    except Exception as e:
        log("translate err: " + str(e))
        return ""

def translate_title_async(d):
    """发起标题翻译：命中缓存直接显示，否则后台请求（结果由主线程提交）。"""
    global _TRANS_SEQ
    text = str(d.get("name") or "").strip()
    if not text:
        return
    cached = _TRANS_CACHE.get(text)
    if cached:
        state.name_text = cached
        state.title_trans = True
        return
    state.name_text = "翻译中..."
    state.title_trans = False
    _TRANS_SEQ += 1
    seq = _TRANS_SEQ
    link = d.get("link") or ""
    _TASK_POOL.submit(_translate_worker, link, text, seq)

def _translate_worker(link, text, seq):
    global _TRANS_READY
    result = fetch_translation(text)
    if seq != _TRANS_SEQ:
        return
    # 成功与失败都要回传：失败时恢复原标题，不能永远停在「翻译中...」
    _TRANS_READY = {"seq": seq, "ok": bool(result),
                    "text": result or "", "link": link}

def _commit_translation():
    """主线程提交翻译结果（转场静默期内暂缓，下一轮再试）。"""
    global _TRANS_READY
    if _TRANS_READY is None or not reload_allowed():
        return
    r = _TRANS_READY
    _TRANS_READY = None
    cur = state.detail
    if cur and cur.get("link") == r["link"] and state.detail_open:
        if r["ok"]:
            if len(_TRANS_CACHE) > 200:
                _TRANS_CACHE.clear()
            _TRANS_CACHE[str(cur.get("name") or "").strip()] = r["text"]
            state.name_text = r["text"]
            state.title_trans = True
        else:
            # 翻译失败：恢复日文原标题
            state.name_text = str(cur.get("name") or "")
            state.title_trans = False


# ============================================================
#  调度层：JavDB 评分（与原 JS javdbRate() 一致）
# ============================================================


JAVDB_SEARCH_URL = "https://javdb.com/search?q={code}&f=all"

_RATING_READY = None      # {"seq","ok","text","link"}，后台线程写入、主线程提交
_RATING_SEQ = 0

def fetch_rating(code):
    """按原 JS javdbRate() 抓取 JavDB 评分；失败返回空串。"""
    try:
        url = JAVDB_SEARCH_URL.replace("{code}", quote(code, safe=""))
        resp = network.get(url, headers=dict(HEADERS), timeout=15)
        if not resp or not resp.ok:
            return ""
        html = resp.text or ""
        block = _RE_SCORE_BLOCK.search(html)
        if not block:
            return ""
        score = _RE_SCORE.search(block.group(0))
        count = _RE_SCORE_COUNT.search(block.group(0))
        if not score:
            return ""
        text = "评分：" + score.group(1)
        if count:
            text += "（" + count.group(1) + " 人评价）"
        return text
    except Exception as e:
        log("rating err: " + str(e))
        return ""

def rating_async(d):
    """发起评分抓取（后台线程，结果由主线程提交）。"""
    global _RATING_SEQ
    code = str(d.get("code") or "").strip()
    if not code:
        return
    state.rating_text = "评分：获取中..."
    _RATING_SEQ += 1
    seq = _RATING_SEQ
    link = d.get("link") or ""
    _TASK_POOL.submit(_rating_worker, link, code, seq)

def _rating_worker(link, code, seq):
    global _RATING_READY
    result = fetch_rating(code)
    if seq != _RATING_SEQ:
        return
    # 成功与失败都要回传：失败时清空评分行，不能永远停在「获取中...」
    _RATING_READY = {"seq": seq, "ok": bool(result),
                     "text": result or "", "link": link}

def _commit_rating():
    """主线程提交评分（转场静默期内暂缓，下一轮再试）。"""
    global _RATING_READY
    if _RATING_READY is None or not reload_allowed():
        return
    r = _RATING_READY
    _RATING_READY = None
    cur = state.detail
    if cur and cur.get("link") == r["link"] and state.detail_open:
        # 失败 → 不显示评分（rating_text 为空时详情页不渲染该行）
        state.rating_text = r["text"] if r["ok"] else ""

def reset_pending():
    global _DETAIL_READY, _DETAIL_ERROR, _DETAIL_SEQ, _PLAY_REQUEST, _PLAY_ERROR
    _DETAIL_SEQ += 1
    _DETAIL_READY = None
    _DETAIL_ERROR = False
    _PLAY_REQUEST = None
    _PLAY_ERROR = ""

def init_background():
    global _BG_STARTED
    if _BG_STARTED:
        return
    _BG_STARTED = True
    start_workers()
    appui.Timer(interval=0.5, action=_sync_dirty).start()


# ============================================================
#  UI 层：业务动作（打开详情 / 播放 / 复制 / 收藏）
# ============================================================


_PLAYER = None

def get_player():
    """详情页内嵌播放器（唯一实例，便于统一控制播放/静音/画中画）。

    autoplay=True：加载后自动开始播放。
    volume=0.0：默认静音（播放后可用系统控件自行开声）。
    pause_on_disappear=False：必须为 False。进入全屏时内联视图会被移除，
    开启它会导致全屏瞬间被暂停；改为在真正离开详情页时显式暂停（见
    on_detail_closed），进出全屏不会改变播放状态与进度。
    """
    global _PLAYER
    if _PLAYER is None:
        _PLAYER = appui.PlayerController(id="main", url="", autoplay=True,
                                         volume=0.0, allows_pip=True,
                                         pause_on_disappear=False)
    return _PLAYER

def start_playback(url):
    """加载并自动开始播放；音量按设置（默认静音）。"""
    player = get_player()
    player.load(url, autoplay=True)
    player.set_volume(0.0 if SETTINGS["mute"] else 1.0)
    player.play()

def pause_local_playback():
    """暂停本地播放，保留播放进度与播放面板。"""
    try:
        get_player().pause()
    except Exception as e:
        log("pause player err: " + str(e))

def stop_local_playback():
    """暂停并停止本地播放、关闭画中画，避免与外部播放器同时播放。"""
    try:
        player = get_player()
        player.pause()
        player.stop()
    except Exception as e:
        log("stop player err: " + str(e))
    state.panel = ""
    state.panel_title = ""

def play_url(url, title="", source=""):
    log("play: " + str(title) + " -> " + str(url)[:120])
    try:
        start_playback(url)      # 自动播放 + 默认静音
    except Exception as e:
        log("player load err: " + str(e))
    state.panel = url
    state.panel_title = title
    state.play = source
    state.status = ""
    state.reload += 1

def open_detail(movie, vid):
    """打开影片详情：在展示位 vid 所属的导航栈内 push 详情页。"""
    log("open_detail: " + str(movie.get("link")))
    global DETAIL_OPEN_AT, DETAIL_HOST, DETAIL_PATH
    if vid in VIEWS and VIEWS[vid]["filter"]["kind"] == "fav":
        # 暂停收藏封面补全线程，避免与详情请求竞争
        pause_fav_movies()
    thumb = movie.get("img") or ""
    if state.detail_thumb != thumb:
        state.detail_thumb = thumb
    if state.panel or state.panel_title or state.play or state.status:
        state.panel = ""
        state.panel_title = ""
        state.play = ""
        state.status = ""

    link = movie.get("link") or ""
    ready = take_ready(link)
    cur = state.detail
    need_fetch = False
    if ready:
        state.detail = ready
    elif (cur and cur.get("link") == link
          and not cur.get("_loading") and not cur.get("error")):
        state.detail = cur
    else:
        # 加载期间不展示列表封面：留空，等详情抓到后再整体渲染
        state.detail = {"_loading": True,
                        "code": movie.get("code", ""),
                        "cover": "",
                        "name": movie.get("title", ""),
                        "link": link}
        need_fetch = True
    state.detail_open = True
    DETAIL_OPEN_AT = time.time()
    # 标题显示复位为日文原文，随后自动翻译成中文
    state.name_text = str((state.detail or {}).get("name") or "")
    state.title_trans = False
    state.rating_text = ""
    if not need_fetch and state.name_text:
        translate_title_async(state.detail)
        rating_async(state.detail)
    # 进入详情即并行预取预览 / 预告 / 视频链接
    prefetch_play_sources((state.detail or {}).get("code"))
    # 详情与它内部的跳转列表都推入「打开它的那个展示位」的导航栈
    DETAIL_HOST = vid if vid in VIEWS else HOME_VID
    DETAIL_PATH = VIEWS[DETAIL_HOST]["path"]
    note_nav_action()
    DETAIL_PATH.append({"tag": "detail", "host": DETAIL_HOST})
    global _DETAIL_PATH_DEPTH
    _DETAIL_PATH_DEPTH = DETAIL_PATH.count
    # 记入该 tab 自己的详情栈（含栈深基准），切回这个 tab 时恢复显示它的详情
    DETAIL_STACKS.setdefault(DETAIL_HOST, []).append(
        {"detail": state.detail, "depth": _DETAIL_PATH_DEPTH})
    if need_fetch:
        request_detail(link)

def on_detail_closed(host):
    """某 tab 的详情视图消失：区分「用户返回列表」与「被覆盖」。

    进入全屏、切换 tab、推入大图时详情视图同样会收到 on_disappear，
    但该 tab 自己的导航栈深度不变；只有该 tab 的栈变浅（用户返回列表）
    才暂停播放并复位，被覆盖的情况不做 State 修改，避免视频被暂停。
    """
    if host not in VIEWS:
        return
    stack = DETAIL_STACKS.get(host)
    if not stack:
        return
    if VIEWS[host]["path"].count >= stack[-1]["depth"]:
        return      # 该 tab 导航栈未变浅：详情仍在使用中
    stack.pop()
    if stack:
        # 同一 tab 内连续打开两层详情：返回时恢复上一层
        state.detail = stack[-1]["detail"]
    else:
        DETAIL_STACKS.pop(host, None)
        state.detail_open = False
    note_nav_action()
    if state.panel:
        pause_local_playback()

def open_filter_at(path, link, value):
    """在指定导航栈推入一个按 link 筛选的影片列表（通用展示）。"""
    if not link:
        state.status = "无该字段链接"
        state.reload += 1
        return
    gc_views()      # 新建展示位前回收超出上限的旧展示位
    vid = new_vid()
    # 附加设置：跳转列表没有搜索框，只保留下拉刷新
    VIEWS[vid] = new_view({"kind": "link", "link": link, "title": value},
                          {"refresh": True}, path)
    note_nav_action()
    _pump(vid)
    push_list(path, vid)

def open_filter(link, value):
    """详情页点击演员/导演/公司/系列/类别：调用通用展示，筛选条件即所点项。"""
    host = DETAIL_HOST if DETAIL_HOST in VIEWS else HOME_VID
    open_filter_at(VIEWS[host]["path"], link, value)

def open_actress(link, value):
    """女优 tab 点击某位女优：按该女优筛选展示其作品。"""
    open_filter_at(PATH_ACT, link, value)

def open_genre(link, value):
    """类型 tab 点击某个分类：按该分类筛选展示影片。"""
    open_filter_at(PATH_GENRE, link, value)

def clear_panel():
    """关闭播放：停止本地播放（含画中画）。"""
    stop_local_playback()
    state.play = ""

def open_external_player():
    """把当前播放链接交给设置里选定的外部播放器（URL Scheme 可配置）。"""
    url = state.panel or ""
    if not url:
        state.status = "请先播放视频"
        state.reload += 1
        return
    name = SETTINGS["player"]
    scheme = EXTERNAL_PLAYERS.get(name, name)
    code = (state.detail or {}).get("code", "")
    target = (scheme + "://x-callback-url/play?url=" + quote(url, safe="") +
              "&name=" + quote(code, safe="") + "&User-Agent=" + scheme)
    # 先暂停并停止本地播放、关闭画中画，避免与外部播放器同时播放/冲突
    stop_local_playback()
    if shortcuts.open_url(target):
        state.play = ""
        state.status = "已跳转 " + name
    else:
        state.status = "打开失败"
    state.reload += 1

def copy_video_link():
    if state.panel:
        clipboard.set(state.panel)
        state.status = "链接已复制"
    else:
        state.status = "请先播放视频"
    state.reload += 1

def play_preview():
    """播放预览：链接在进入详情时就已并行取好。"""
    if state.src_preview:
        play_url(state.src_preview, "预览", source="预览")

def play_trailer():
    """播放预告：链接在进入详情时就已并行取好（DMM / eightcha 取可用的那个）。"""
    if state.src_trailer:
        play_url(state.src_trailer, "预告", source="预告")

def play_video():
    """播放完整视频：链接在进入详情时就已并行取好。"""
    if state.src_video:
        play_url(state.src_video, "完整视频", source="完整视频")

def show_sample(link):
    """查看样片大图：加载全部样片大图后推入浏览（可左右滑动翻看）。"""
    samples = (state.detail or {}).get("samples") or []
    for s in samples:
        request_img(s["link"], priority=True)
    idx = 0
    for i, s in enumerate(samples):
        if s.get("link") == link:
            idx = i
            break
    state.sample_index = idx
    note_nav_action()
    DETAIL_PATH.append({"tag": "sample"})

def close_sample():
    note_nav_action()
    DETAIL_PATH.pop(count=1)
    state.sample_index = 0

def copy_code():
    if state.detail:
        code = state.detail["code"]
        clipboard.set(code)
        state.status = "番号 " + code + " 已复制"
        state.reload += 1

def toggle_fav():
    d = state.detail
    if not d:
        return
    toggle_bookmark(d, img=state.detail_thumb or d.get("cover") or "")
    state.reload += 1


# ============================================================
#  UI 层：通用展示函数（封面网格 + 翻页）
# ============================================================


# 封面网格列宽下限：同时用作叠在封面上的文字的最大宽度，
# 保证文字再长也不会把单元格撑得比列还宽（adaptive 的列宽一定 >= 该值）
GRID_MIN_COLUMN = 104
# 封面网格间距：影片 / 收藏 / 女优 三个 tab 共用同一套网格与单元格
GRID_SPACING = 3
# 叠在封面上的文字框最大宽度：必须 <= GRID_MIN_COLUMN。
# adaptive 保证实际列宽一定 >= GRID_MIN_COLUMN，因此文字框永远落在封面边框之内，
# 不会横向溢出到列间距里（否则会让横向空隙看起来比行间距小）
GRID_CAPTION_WIDTH = 104
# 已收藏的强调色：与原 JS recGra（colorData[9]）一致，
# 整张封面盖一层蓝紫渐变，透明度 0.4（原 JS 的 alpha）。
FAV_GRADIENT = ["#2f74e0", "#5d44e0"]
FAV_TINT_ALPHA = 0.4
COVER_CELL_RADIUS = 6

def grid_cover(url):
    """网格封面：与详情页封面同一套已验证的填充模式。

    aspect_ratio + content_mode="fill" 让图片按比例撑满自身框，
    clipped 裁掉多余部分——图片严格贴合框内，不会溢出盖住相邻单元格
    之间的空隙（此前构造参数形式的 content_mode="fill" + 固定高度
    存在溢出，表现为女优头像之间没有间距）。
    """
    return appui.AsyncImage(url=img_src(url)) \
        .aspect_ratio(COVER_RATIO, content_mode="fill") \
        .frame(max_width=appui.infinity) \
        .clipped() \
        .background("secondarySystemBackground", corner_radius=COVER_CELL_RADIUS) \
        .z_index(0)

def fav_tint_layer():
    """已收藏标记：铺满封面的一层强调色渐变（对齐原 JS recGra）。

    层级夹在封面与「番号 | 日期」之间：封面 0 -> 强调色 0.5 -> 文字 1。
    高度跟随封面（撑满 ZStack），不写死像素。
    """
    return appui.Spacer(min_length=0) \
        .frame(max_width=appui.infinity, max_height=appui.infinity) \
        .background(gradient=FAV_GRADIENT, gradient_type="linear",
                    corner_radius=COVER_CELL_RADIUS, opacity=FAV_TINT_ALPHA) \
        .z_index(0.5)

def grid_columns():
    """列规格：显式带上列间距，使其与 LazyVGrid 的行间距一致。"""
    col = appui.adaptive(minimum=GRID_MIN_COLUMN)
    col["spacing"] = GRID_SPACING
    return [col]


def _caption_line(text):
    """叠在封面上的一行文字（番号 / 发布日期 / 女优名共用同一样式）。"""
    return appui.Text(text) \
        .font("caption2") \
        .foreground_color("white") \
        .line_limit(1) \
        .minimum_scale_factor(0.6)

def movie_cell(m, vid):
    """影片封面单元格：番号与发布日期分两行叠在封面底部（下对齐 + 左右居中）。

    信息叠在图片内而不是排在图片下方，行与行的空隙就等于列与列的空隙。
    """

    def open():
        open_detail(m, vid)

    code = m.get("code") or ""
    date = m.get("date") or ""
    # 番号与发布日期不再合并成一行：各占一行，同一个半透明胶囊内
    lines = [_caption_line(code)] if code else []
    if date:
        lines.append(_caption_line(date))
    caption = appui.VStack(lines, spacing=1) \
        .padding(horizontal=4, vertical=3) \
        .frame(max_width=GRID_CAPTION_WIDTH) \
        .background("black", corner_radius=4, opacity=0.55) \
        .padding(bottom=6) \
        .z_index(1)      # 提升层级，保证叠在封面之上而不是被封面盖住
    # 封面撑满整列宽度：与详情页封面同一套填充模式（见 grid_cover），
    # 图片严格贴合自身框内，不会溢出盖住单元格之间的空隙；
    # 文字框宽度 <= 列宽下限，因此一定包含在封面边框内
    cover = grid_cover(m["img"])
    # 已收藏的影片盖一层强调色（收藏 tab 里全是收藏，无需再标记）
    layers = [cover]
    if code and in_fav(code) and view_kind(vid) != "fav":
        layers.append(fav_tint_layer())
    layers.append(caption)
    # ZStack：后声明的子视图绘制在上层，再配 z_index 保证文字一定压在封面之上
    return appui.Button(
        action=open,
        content=appui.ZStack(layers, alignment="bottom"),
    ).button_style("plain").id(m.get("code") or m.get("link") or "")

def actress_cell(a):
    """女优头像单元格：名字叠在头像底部，样式与封面的「番号 | 日期」一致。"""

    def open():
        open_actress(a["link"], a["name"])

    caption = appui.Text(a.get("name") or "") \
        .font("caption2") \
        .foreground_color("white") \
        .line_limit(1) \
        .minimum_scale_factor(0.6) \
        .padding(horizontal=4, vertical=3) \
        .frame(max_width=GRID_CAPTION_WIDTH) \
        .background("black", corner_radius=4, opacity=0.55) \
        .padding(bottom=6) \
        .z_index(1)
    # 与影片封面完全同一套填充模式（grid_cover）：头像按 5:7 比例贴合框内，
    # 不溢出、不留白，单元格之间的空隙得以保留
    cover = grid_cover(a["img"])
    return appui.Button(
        action=open,
        content=appui.ZStack([cover, caption], alignment="bottom"),
    ).button_style("plain").id(a.get("link") or a.get("name") or "")

def genre_cell(c):
    """二级分类按钮：等宽 + 背景色，点击按该分类筛选影片。"""

    def open():
        open_genre(c["link"], c["name"])

    return appui.Button(
        action=open,
        content=appui.Label(c["name"], system_image="tag")
            .font("caption")
            .line_limit(1)
            .minimum_scale_factor(0.7)
            .frame(max_width=appui.infinity)
            .padding(vertical=9)
            .background("secondarySystemBackground", corner_radius=8),
    ).button_style("plain")

def fav_cell(m):
    """收藏封面单元格：外观与首页一致，封面缺失时用后台解析结果，长按可移除。"""
    resolved = fav_movie(m["code"])
    item = {"code": m["code"],
            "img": m.get("img") or resolved.get("img", ""),
            "date": m.get("date") or "",
            "link": m.get("link") or resolved.get("link", "")}

    def unfav():
        remove_fav(m["code"])
        save_shelf()

    return movie_cell(item, FAV_VID).context_menu(content=[
        appui.Button("从收藏移除", action=unfav, role="destructive"),
    ]).id(m.get("code") or "")

def grid_cell(item, vid):
    """按展示位类型选择单元格：影片/收藏用封面，女优用头像。"""
    kind = view_kind(vid)
    if kind == "actress":
        return actress_cell(item)
    if kind == "fav":
        return fav_cell(item)
    return movie_cell(item, vid)

def sample_cell(s):
    """详情页样图格：缩略图随详情加载，点击查看大图（大图此时才加载）。"""

    def open():
        show_sample(s["link"])

    return appui.Button(
        action=open,
        content=appui.AsyncImage(url=img_src(s["img"]))
            .frame(height=110).clipped()
            .background("secondarySystemBackground", corner_radius=6),
    ).button_style("plain")

def magnet_row(m):
    """磁链行（左滑可复制）。"""

    def copy():
        clipboard.set(m["info"])

    return appui.Label(m["name"], system_image="link").swipe_actions(actions=[
        appui.Button("复制", action=copy, role="destructive"),
    ])

# 搜索框的临时输入（普通变量：按键时不写入 State，避免每字符整树重建）
_SEARCH_INPUT = {"value": ""}

def set_search_input(v):
    _SEARCH_INPUT["value"] = v      # 只记录，不写 State：按键不触发重建

def search_row(vid):
    """搜索栏（只有影片首页这一处展示需要）。"""
    field = appui.TextField("番号或演员", text=_SEARCH_INPUT["value"],
                            on_change=set_search_input) \
        .text_field_style("rounded_border") \
        .on_submit(do_search)
    buttons = [appui.Button("搜索", action=do_search).button_style("bordered_prominent")]
    if VIEWS[vid]["filter"]["kind"] == "search":
        buttons.append(appui.Button("取消", action=clear_search).button_style("bordered"))
    return appui.HStack([field] + buttons, spacing=8)

def pager_row(vid):
    """翻页条：左上翻、右下翻、中间显示当前页码。"""

    def prev():
        goto_page(vid, VIEWS[vid]["page"] - 1)

    def next_page():
        goto_page(vid, VIEWS[vid]["page"] + 1)

    page = VIEWS[vid]["page"]

    def open_input():
        open_page_input(vid)

    prev_btn = appui.Button(
        content=appui.Label("上一页", system_image="chevron.left"),
        action=prev,
    ).button_style("bordered").disabled(page <= 1)
    next_btn = appui.Button(
        content=appui.Label("下一页", system_image="chevron.right"),
        action=next_page,
    ).button_style("bordered").disabled(not can_next(vid))
    # 中间页码可点击：弹出页码输入框直接跳转
    center = appui.Button(
        content=appui.Text("第 " + str(page) + " 页").font("subheadline").bold(),
        action=open_input,
    ).button_style("plain")
    return appui.HStack([
        prev_btn,
        appui.Spacer(min_length=8),
        center,
        appui.Spacer(min_length=8),
        next_btn,
    ], spacing=8)

def fav_count_row():
    """收藏页顶部「共XX部」：占位位置与高度与影片 tab 的搜索栏一致，文字居中。

    搜索栏是展示 VStack 的首个元素（外层 .padding() 相同），默认高度约
    36pt，这里用 min_height=36 复刻同一占位，文字水平居中。
    """
    return appui.Text("共 %d 部" % len(SHELF["fav"])) \
        .font("body") \
        .foreground_color("secondaryLabel") \
        .frame(min_height=36, max_width=appui.infinity, alignment="center")

def movie_display(vid, with_pager=True):
    """通用影片展示：封面网格（+ 翻页条）。

    vid 决定用哪个展示位；展示位的 filter 决定筛选条件，
    extras 决定这一处额外显示什么（搜索框 / 下拉刷新 / 提示行）。
    with_pager=False 用于三个 tab 根页：分页条由 display_page_view
    固定显示在 Tab 栏上方，不进滚动区。
    数据按发布时间从新到旧固定排列，增量加载只追加、不覆盖已有内容。
    """
    v = VIEWS.get(vid)
    if not v:
        return appui.Text("")
    ex = v["extras"]
    parts = []

    if ex.get("search"):
        parts.append(search_row(vid))

    if view_kind(vid) == "fav":
        # 收藏 tab 顶部：已收藏总数（占位与搜索栏一致）
        parts.append(fav_count_row())

    loading = page_loading(vid)
    items = page_items(vid)
    if items:
        parts.append(appui.LazyVGrid(
            columns=grid_columns(),
            spacing=GRID_SPACING,
            content=[grid_cell(m, vid) for m in items],
        ))
        # 翻到已加载内容的末尾：在已有内容下方追加加载指示，不替换当前页
        if loading:
            parts.append(appui.HStack([
                appui.ProgressView(),
                appui.Text("正在加载更多...").font("caption")
                    .foreground_color("secondaryLabel"),
            ], spacing=8))
    elif loading:
        parts.append(appui.HStack([
            appui.ProgressView(),
            appui.Text("加载中...").font("caption").foreground_color("secondaryLabel"),
        ], spacing=8))
    else:
        parts.append(appui.Text("没有找到影片").foreground_color("secondaryLabel"))

    if with_pager:
        parts.append(pager_row(vid))

    if ex.get("status") and state.status:
        parts.append(appui.Text(state.status).font("caption")
                     .foreground_color("secondaryLabel"))

    return appui.VStack(parts, spacing=12).padding()

def genre_display(vid):
    """类型展示：顶部一级分类下拉 + 所选分组的二级分类（一行 3 个，等宽背景）。"""
    v = VIEWS.get(vid)
    if not v:
        return appui.Text("")
    if not v["pool"] and v["loading"]:
        return appui.HStack([
            appui.ProgressView(),
            appui.Text("加载中...").font("caption").foreground_color("secondaryLabel"),
        ], spacing=8).padding()
    if not v["pool"]:
        return appui.Text("没有找到分类").foreground_color("secondaryLabel").padding()

    groups = v["pool"]
    tags = ["全部"] + [g["tag"] for g in groups]
    sel = state.genre_group if state.genre_group in tags else "全部"
    shown = [g for g in groups if sel == "全部" or g["tag"] == sel]

    parts = [appui.HStack([
        appui.Text("类型").font("body").foreground_color("secondaryLabel"),
        appui.Spacer(min_length=8),
        appui.Picker("类型", selection=sel, options=tags,
                     on_change=set_genre_group).picker_style("menu"),
    ], spacing=8)]
    for group in shown:
        block = [appui.Text(group["tag"]).font("headline").padding(top=10)]
        block.append(appui.LazyVGrid(
            columns=[appui.flexible() for _ in range(3)],   # 一行固定 3 个，等宽
            spacing=8,
            content=[genre_cell(c) for c in group["cats"]],
        ))
        parts.append(appui.VStack(block, spacing=8))
    return appui.VStack(parts, spacing=12).padding()

def set_genre_group(v):
    """切换一级分类。"""
    state.genre_group = v
    state.reload += 1

def display_page_view(vid, titled=True):
    """把通用展示包装成可导航的页面（下拉刷新按附加设置决定）。

    titled=False 用于影片 / 女优 / 收藏三个 tab 根页：
      - 分页条放在滚动区之外并限定滚动区高度，固定在 Tab 栏上方，
        任何情况下都无需滚动页面即可点击；
      - 外层包 GeometryReader 实测可用高度，用于限定滚动区高度。
    推入的跳转列表仍保留标题（作为页面说明与返回键文字）。
    """
    v = VIEWS.get(vid)
    if not v:
        return appui.Text("")

    def refresh_view():
        reset_view(vid)

    kind = view_kind(vid)
    if kind == "genre":
        # 类型页：无网格翻页，保持原结构
        sv = appui.ScrollView(genre_display(vid))
        if v["extras"].get("refresh"):
            sv = sv.refreshable(action=refresh_view)
        if titled:
            sv = sv.navigation_title(view_title(vid))
        return sv

    with_pager = bool(titled)        # tab 根页：分页条移出滚动区
    sv = appui.ScrollView(movie_display(vid, with_pager=with_pager))
    if v["extras"].get("refresh"):
        sv = sv.refreshable(action=refresh_view)
    if titled:
        return sv.navigation_title(view_title(vid))

    # 限定滚动区高度：内容再多也放不到分页条下面，分页条始终可见
    h = _GRID_GEOMETRY["h"]
    if h > 0:
        sv = sv.frame(height=max(160.0, h - PAGER_BLOCK_H))
    pager = pager_row(vid) \
        .padding(horizontal=PAGE_H_PAD) \
        .padding(bottom=PAGER_BOTTOM_PAD)
    page = appui.VStack([sv, pager], spacing=4)
    # 实测可用区域：动态决定每页项数（影片 / 女优 / 收藏三个 tab 根页）
    return appui.GeometryReader(content=page, on_change=remember_grid_size)


# ============================================================
#  UI 层：路由目标（详情 / 大图 / 跳转列表）
# ============================================================


def detail_destination(data):
    """详情路由：所有入口统一走 detail_page_view()，展示完全一致。

    每个 tab 的详情状态互相独立：按推送载荷里的 host 恢复该 tab 自己的
    详情，切换 tab 时同步切换到对应 tab 的详情内容。
    """
    host = data.get("host") if isinstance(data, dict) else None
    global DETAIL_HOST, DETAIL_PATH, _DETAIL_PATH_DEPTH
    if host not in VIEWS:
        host = DETAIL_HOST if DETAIL_HOST in VIEWS else HOME_VID
    stack = DETAIL_STACKS.get(host)
    if stack:
        entry = stack[-1]
        if entry["detail"] is not state.detail:
            state.detail = entry["detail"]      # 切回该 tab：显示它自己的详情
        state.detail_open = True
        DETAIL_HOST = host
        DETAIL_PATH = VIEWS[host]["path"]
        _DETAIL_PATH_DEPTH = entry["depth"]

    def on_closed():
        on_detail_closed(host)

    return detail_page_view().on_disappear(action=on_closed)

def sample_destination(data):
    return sample_preview_view()

def list_destination(data):
    """跳转列表：复用通用展示，只是展示位不同。"""
    vid = data.get("vid") if isinstance(data, dict) else ""
    if vid not in VIEWS:
        # 兜底：载荷没回传时用最近一次推入的展示位，避免出现空白页
        while _PUSHED_VIDS and _PUSHED_VIDS[-1] not in VIEWS:
            _PUSHED_VIDS.pop()
        vid = _PUSHED_VIDS[-1] if _PUSHED_VIDS else ""
    if vid not in VIEWS:
        return appui.Text("列表已失效").navigation_title("影片")
    return display_page_view(vid)


# ============================================================
#  UI 层：详情页
# ============================================================


# 详情页封面：按标准比例撑满宽度，上下不留空白
def _cover_view(url):
    return appui.AsyncImage(url=img_src(url)) \
        .aspect_ratio(COVER_RATIO, content_mode="fill") \
        .frame(max_width=appui.infinity) \
        .clipped() \
        .background("secondarySystemBackground", corner_radius=8)

def _loading_view(d):
    """详情加载中：不预显示列表封面，只留空白与一个加载指示，数据到位后再整体渲染。"""
    return appui.VStack([
        appui.ProgressView(),
    ], spacing=0).frame(max_width=appui.infinity, max_height=appui.infinity)

# ============================================================
#  UI 层：友商连接（与原 JS 详情页菜单一致，磁链除外）
#  选择站点后用 Safari 打开对应搜索页（$app.openURL 的等价实现）
# ============================================================


PARTNER_SITES = [
    ("JavDB", "https://javdb.com/search?q={code}&f=all"),
    ("JavLibrary", "http://www.javlibrary.com/cn/vl_searchbyid.php?keyword={code}"),
    ("Fanza",
     "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid={code_lower_nodash}/?dmmref=aMonoDvd_List"),
    ("Netflav", "https://netflav.com/search?type=title&keyword={code}"),
    ("JAV.GURU", "https://jav.guru/zh/?s={code}"),
    ("Jable.TV", "https://jable.tv/search/{code}/"),
    ("Missav", "https://missav.com/{code}"),
    ("JavDay", "https://javday.tv/videos/{code_nodash}"),
]

def build_partner_url(pattern, code):
    """按原 JS 规则生成链接：Fanza 小写并去掉连字符，JavDay 去掉连字符。"""
    return (pattern
            .replace("{code_lower_nodash}", code.lower().replace("-", "", 1))
            .replace("{code_nodash}", code.replace("-", "", 1))
            .replace("{code}", code))

def partner_menu(code):
    """友商链接：系统下拉，默认显示「选择源」，选择后用 Safari 打开。"""
    def make_open(pattern, name):
        def open_site():
            url = build_partner_url(pattern, code)
            if url:
                log("partner: " + name + " -> " + url[:120])
                shortcuts.open_url(url)
        return open_site

    return appui.Menu("选择源",
                      content=[appui.Button(title=name, action=make_open(pattern, name))
                               for name, pattern in PARTNER_SITES])

def detail_page_view():
    """影片详情页 —— 唯一的详情实现（公共函数）。

    任何入口（影片列表、搜索结果、详情跳转列表……）都通过
    detail_destination() -> detail_page_view() 进入，
    因此不同位置打开的详情页展示完全一致。
    """
    d = state.detail
    if not d:
        return appui.Text("载入中...")
    if d.get("_loading"):
        return _loading_view(d)
    if d.get("error"):
        return appui.VStack([
            appui.Text("加载失败，请返回重试").foreground_color("secondaryLabel"),
        ], spacing=12).padding()

    # 顶部番号：点击即复制（唯一的一处番号展示）
    code_btn = appui.Button(
        content=appui.Text(d["code"]).font("title2").bold().line_limit(1),
        action=copy_code,
    ).button_style("plain")

    cover = _cover_view(d["cover"])

    # 视频标题：中文译文在上（原文格式）、日文原文在下（译文格式），同时展示
    title_rows = []
    if state.name_text:
        title_rows.append(appui.Text(state.name_text)
                          .font("subheadline").line_limit(3))
    title_rows.append(appui.Text(d["name"]).font("caption")
                      .foreground_color("secondaryLabel").line_limit(3))
    title_block = appui.VStack(title_rows, spacing=4, alignment="leading")

    meta = appui.HStack([
        appui.Text("发行日期：" + d["time"]).font("caption"),
        appui.Spacer(min_length=12),
        appui.Text("时长：" + str(d["last"])).font("caption"),
    ], spacing=8)
    # 评分（JavDB）：发行日期下一行，左对齐；颜色与发行日期保持一致
    rating_rows = []
    if state.rating_text:
        rating_rows.append(appui.Text(state.rating_text).font("caption"))
    meta_block = appui.VStack([meta] + rating_rows, spacing=4, alignment="leading")

    def eq_btn(label, action, source=None, prominent=False):
        """等宽按钮：文字不折行（自动缩字号），同排均分宽度、间距一致。"""
        style = "bordered_prominent" if prominent else "bordered"
        if source is not None and state.play == source:
            style = "bordered_prominent"
        return appui.Button(
                content=appui.Text(label).line_limit(1).minimum_scale_factor(0.5),
                action=action,
            ) \
            .button_style(style) \
            .frame(min_height=34, max_width=appui.infinity)

    fav_title = "已收藏" if in_fav(d["code"]) else "收藏"
    # 链接没取到的按钮保持置灰：进入详情时就已并行预取，取到后自动点亮
    action_btns = appui.HStack([
        eq_btn("预览", play_preview, "预览").disabled(not state.src_preview),
        eq_btn("预告", play_trailer, "预告").disabled(not state.src_trailer),
        eq_btn("视频", play_video, "完整视频").disabled(not state.src_video),
        eq_btn(fav_title, toggle_fav, prominent=in_fav(d["code"])),
    ], spacing=8)

    top = appui.VStack([code_btn, cover, title_block, meta_block, action_btns],
                       spacing=12, alignment="leading")

    if state.panel:
        op_buttons = [eq_btn("关闭播放", clear_panel)]
        if state.play == "完整视频":
            op_buttons = [
                eq_btn("外部播放", open_external_player),
                eq_btn("复制链接", copy_video_link),
                eq_btn("关闭播放", clear_panel),
            ]
        panel_rows = [
            appui.Text(state.panel_title).font("caption").foreground_color("secondaryLabel"),
            appui.VideoPlayer(player=get_player(), autoplay=True,
                              pause_on_disappear=False).frame(height=220),
            appui.HStack(op_buttons, spacing=8),
        ]
        top = appui.VStack([top] + panel_rows, spacing=8)
    if state.status:
        top = appui.VStack([
            top,
            appui.Text(state.status).font("caption").foreground_color("secondaryLabel"),
        ], spacing=4)

    def filter_row(value, link):
        """可点击的筛选项：点击后调用通用展示，筛选条件即该项。"""

        def open():
            open_filter(link, value)

        if link:
            return appui.Button(action=open, content=appui.Text(value).line_limit(1)) \
                .button_style("borderless")
        return appui.Text(value).font("body").foreground_color("secondaryLabel")

    def who_row(label, value, link):
        return appui.HStack([
            appui.Text(label).font("body").foreground_color("secondaryLabel"),
            appui.Spacer(min_length=8),
            filter_row(value, link),
        ], spacing=8)

    def actress_block(a):
        def open():
            open_filter(a["link"], a["name"])

        return appui.Button(
            action=open,
            content=appui.VStack([
                appui.AsyncImage(url=img_src(a["img"]))
                    .frame(width=58, height=58).clipped()
                    .background("secondarySystemBackground", corner_radius=8),
                appui.Text(a["name"]).font("caption2").line_limit(1),
            ], spacing=3),
        ).button_style("plain")

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
        # 类别：系统下拉，默认显示「X类」（X 为类别总数），展开后选择
        genre_btns = []
        seen = set()
        for g in d["genres"]:
            if g["name"] in seen:
                continue
            seen.add(g["name"])

            def pick_genre(link=g["link"], name=g["name"]):
                open_filter(link, name)

            genre_btns.append(appui.Button(title=g["name"], action=pick_genre))
        detail_rows.append(appui.HStack([
            appui.Text("类别").font("body").foreground_color("secondaryLabel"),
            appui.Spacer(min_length=8),
            appui.Menu("%d类" % len(genre_btns), content=genre_btns),
        ], spacing=8))
    # 友商链接：类别下一行，下拉选择站点后用 Safari 打开
    if d["code"]:
        detail_rows.append(appui.HStack([
            appui.Text("友商链接").font("body").foreground_color("secondaryLabel"),
            appui.Spacer(min_length=8),
            partner_menu(d["code"]),
        ], spacing=8))
    if d["actresses"]:
        detail_rows.append(appui.VStack([
            appui.Text("女优").font("body").foreground_color("secondaryLabel"),
            appui.LazyVGrid(
                columns=[appui.adaptive(minimum=72)],
                spacing=10,
                content=[actress_block(a) for a in d["actresses"]],
            ),
        ], spacing=8, alignment="leading"))

    sections = [appui.Section(detail_rows, header="详情")]
    if d["samples"]:
        sections.append(appui.Section([
            appui.LazyVGrid(
                columns=[appui.adaptive(minimum=118)],
                spacing=8,
                content=[sample_cell(s) for s in d["samples"]],
            )
        ], header="样图"))
    if d["magnets"]:
        sections.append(appui.Section(
            [magnet_row(m) for m in d["magnets"]], header="磁链"))

    # 不再以番号作为导航标题：番号只在正文中展示（点击可复制）
    return appui.List([appui.Section([top.padding()])] + sections) \
        .navigation_title("")

def sample_preview_view():
    """样片大图浏览：左右滑动查看其他样片。

    页码指示器紧贴图片下方（独占一行），关闭按钮单独放在底部，
    两者不再同排，避免互相挤占。
    """
    samples = (state.detail or {}).get("samples") or []
    pages = []
    for i, s in enumerate(samples):
        pages.append(appui.Tab(
            content=appui.AsyncImage(url=img_src(s["link"]), content_mode="fit")
                .frame(max_width=appui.infinity, max_height=appui.infinity),
            tag=i,
        ))
    if not pages:
        return appui.VStack([
            appui.Text("没有样片").foreground_color("secondaryLabel"),
            appui.Button("关闭", action=close_sample),
        ], spacing=12).padding(bottom=24)
    index = max(0, min(int(state.sample_index), len(pages) - 1))
    gallery = appui.VStack([
        appui.TabView(tabs=pages, selection=state.bind.sample_index)
            .tab_view_style("page")
            .frame(max_width=appui.infinity, max_height=appui.infinity),
        appui.Text(str(index + 1) + " / " + str(len(pages)))
            .font("caption").foreground_color("secondaryLabel"),
    ], spacing=6)
    return appui.VStack([
        gallery,
        appui.Button("关闭", action=close_sample),
    ], spacing=14).padding(bottom=24)


# ============================================================
#  UI 层：影片 tab / 设置 tab
# ============================================================


def do_search():
    """在影片首页发起搜索：把首页展示位的筛选条件换成关键词。

    只在提交时读取临时输入并写一次 State（触发一次重建），
    输入过程的每个按键都不经过 State。
    """
    kw = norm_keyword(_SEARCH_INPUT["value"])
    state.keyword = kw
    _SEARCH_INPUT["value"] = kw
    if not kw:
        clear_search()
        return
    set_filter(HOME_VID, {"kind": "search", "keyword": kw, "title": "搜索 " + kw})

def clear_search():
    """退出搜索，回到最新影片。"""
    state.keyword = ""
    _SEARCH_INPUT["value"] = ""
    set_filter(HOME_VID, HOME_FILTER)

_LIST_DESTINATIONS = {"detail": detail_destination,
                      "sample": sample_destination,
                      "list": list_destination}

def movies_tab():
    return appui.NavigationStack(
        display_page_view(HOME_VID, titled=False),
        path=PATH_MOVIES,
        destinations=_LIST_DESTINATIONS,
    ).id("movies")

def actress_tab():
    """女优 tab：头像网格 + 翻页，点击进入该女优的作品列表。"""
    return appui.NavigationStack(
        display_page_view(ACTRESS_VID, titled=False),
        path=PATH_ACT,
        destinations=_LIST_DESTINATIONS,
    ).on_appear(action=load_actresses_once).id("actress")

def genre_tab():
    """类型 tab：按主题分组的分类按钮，点击进入该分类的影片列表。"""
    return appui.NavigationStack(
        display_page_view(GENRE_VID, titled=False),
        path=PATH_GENRE,
        destinations=_LIST_DESTINATIONS,
    ).on_appear(action=load_genres_once).id("genre")

def fav_tab():
    """收藏 tab：封面网格 + 翻页，长按可从收藏移除。"""
    return appui.NavigationStack(
        display_page_view(FAV_VID, titled=False),
        path=PATH_FAV,
        destinations=_LIST_DESTINATIONS,
    ).id("fav")

def set_page_size(kind, v):
    """修改某一类展示位的每页项数：只重置受影响的展示位。"""
    try:
        size = int(v)
    except Exception:
        return
    if size not in PAGE_SIZE_OPTIONS:
        return
    key = page_size_key(kind)
    SETTINGS[key] = size
    save_settings()
    for vid in list(VIEWS):
        item = VIEWS[vid]
        with _VIEWS_LOCK:
            if page_size_key(item["filter"]["kind"]) != key:
                continue        # 该展示位不受这项设置影响，保持原样
            item["page"] = 1
            if item["base"]:
                # 每页项数变了，旧的分页偏移失效，回到起点重新累积
                item["pool"] = []
                item["base"] = 0
                item["remote"] = 1
                item["exhausted"] = False
                item["generation"] += 1     # 在途 worker 结果作废
        _pump(vid)
    state.reload += 1

def set_page_size_movie(v):
    set_page_size("movie", v)

def set_page_size_actress(v):
    set_page_size("actress", v)

def set_page_size_fav(v):
    set_page_size("fav", v)

def set_player(name):
    if name not in EXTERNAL_PLAYERS:
        return
    SETTINGS["player"] = name
    save_settings()
    state.reload += 1

def set_mute(v):
    SETTINGS["mute"] = bool(v)
    save_settings()
    state.reload += 1

def settings_tab():
    return appui.NavigationStack(
        appui.Form([
            appui.Section([
                appui.Picker("影片每页",
                             selection=str(page_size(HOME_VID)),
                             options=_PAGE_SIZE_OPTIONS_TEXT,
                             on_change=set_page_size_movie),
                appui.Picker("女优每页",
                             selection=str(page_size(ACTRESS_VID)),
                             options=_PAGE_SIZE_OPTIONS_TEXT,
                             on_change=set_page_size_actress),
                appui.Picker("收藏每页",
                             selection=str(page_size(FAV_VID)),
                             options=_PAGE_SIZE_OPTIONS_TEXT,
                             on_change=set_page_size_fav),
            ], header="展示",
               footer="影片 / 女优 / 收藏 三个 tab 的每页项数分别设置；"
                      "影片的设置同时作用于搜索结果和演员、分类等跳转出来的影片列表。"
                      "列表顺序固定为发布时间从新到旧。"),
            appui.Section([
                appui.Toggle("视频默认静音", is_on=SETTINGS["mute"],
                             on_change=set_mute),
                appui.Picker("外部播放器",
                             selection=SETTINGS["player"],
                             options=list(EXTERNAL_PLAYERS.keys()),
                             on_change=set_player),
            ], header="播放",
               footer="在详情页播放视频后，可用「外部播放」把链接交给选定的播放器。"),
            appui.Section([
                appui.LabeledContent("版本", value=APP_VERSION),
                appui.LabeledContent("数据来源", value="javbus.com"),
            ], header="关于",
               footer="JavBus.js移植版"),
        ]),
        path=PATH_SETTINGS,
    ).id("settings")


# ============================================================
#  入口
# ============================================================


def start():
    """冷启动：初始化后台线程并复位到影片 tab。"""
    init_background()
    reset_pending()
    state.tab = 0
    state.keyword = ""
    state.detail = None
    state.detail_open = False
    state.detail_thumb = ""
    state.panel = ""
    state.panel_title = ""
    state.play = ""
    state.src_preview = ""
    state.src_trailer = ""
    state.src_video = ""
    state.status = ""
    state.sample_index = 0
    state.show_page_input = False
    state.name_text = ""
    state.title_trans = False
    DETAIL_STACKS.clear()      # 全部栈复位：各 tab 的详情状态一并清空
    PATH_MOVIES.pop_to_root()
    PATH_ACT.pop_to_root()
    PATH_GENRE.pop_to_root()
    PATH_FAV.pop_to_root()
    PATH_SETTINGS.pop_to_root()
    _pump(HOME_VID)
    _pump(FAV_VID)

# 首次进入 tab 才预加载（避免启动时并发请求过多）
_ACTRESS_LOADED = False
_GENRE_LOADED = False

def load_actresses_once():
    global _ACTRESS_LOADED
    if _ACTRESS_LOADED:
        return
    _ACTRESS_LOADED = True
    _pump(ACTRESS_VID)

def load_genres_once():
    global _GENRE_LOADED
    if _GENRE_LOADED:
        return
    _GENRE_LOADED = True
    _pump(GENRE_VID)

# tab 序号 → 根页展示位（切换 tab 时复位详情用）
TAB_ROOT_VIDS = {0: HOME_VID, 1: ACTRESS_VID, 2: FAV_VID, 3: GENRE_VID}

def leave_tab_reset(prev):
    """离开某 tab 时复位：若该 tab 停在详情页（含多层），整条导航链退回主页面。

    prev 是我们自行记录的上一个标签页序号（不能用 state.tab 取：
    双向绑定在回调触发前就已把它写成新值）。
    """
    root = TAB_ROOT_VIDS.get(prev)
    if root not in VIEWS:
        return
    path = VIEWS[root]["path"]
    # 找出属于该 tab 导航栈的所有详情（宿主可能是栈内的跳转列表）
    hosts = [h for h in DETAIL_STACKS
             if h in VIEWS and VIEWS[h]["path"] is path]
    if not hosts:
        return      # 该 tab 未停在详情页：保留它的导航位置
    for h in hosts:
        DETAIL_STACKS.pop(h, None)
    state.detail_open = False
    note_nav_action()
    path.pop_to_root()      # 整条导航链（含多层详情）回到主页面

def set_tab(v):
    """记录当前标签页：确保 State 与界面选择一致，重建时停留在最后切换的标签页。"""
    global _LAST_TAB
    try:
        v = int(v)
    except Exception:
        pass
    leave_tab_reset(_LAST_TAB)
    _LAST_TAB = v
    state.tab = v

def make_body():
    return appui.TabView(
        tabs=[
            appui.Tab("影片", system_image="play.rectangle", content=movies_tab(), tag=0),
            appui.Tab("女优", system_image="person.2", content=actress_tab(), tag=1),
            appui.Tab("收藏", system_image="star", content=fav_tab(), tag=2),
            appui.Tab("类型", system_image="tag", content=genre_tab(), tag=3),
            appui.Tab("设置", system_image="gear", content=settings_tab(), tag=4),
        ],
        selection=state.bind.tab,
        on_change=set_tab,
    ).sheet(
        is_presented=state.bind.show_page_input,
        content=page_input_view,
        detents="medium",
        drag_indicator="visible",
    )

start()

def body():
    return make_body()

appui.run(body, state=state, presentation="fullscreen_with_close")
