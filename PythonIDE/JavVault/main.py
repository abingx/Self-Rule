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
import re
import struct
import tempfile
import threading
import time
import zlib
from collections import OrderedDict
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

# 收藏条数上限
MAX_LIST_ITEMS = 1000

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
_SRC_CACHE = {}
_SRC_CACHE_MAX = 4096
MAX_QUEUE = 1024
MAX_DOWNLOADED = 2048
MAX_DOWNLOAD_ATTEMPTS = 5
_SEEN = set()
_DOWNLOAD_ATTEMPTS = {}
_QUEUED = []
_LOCK = threading.Lock()
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
        if url in _SEEN:
            return "file://" + _local_path(url)
        if len(_QUEUED) >= MAX_QUEUE:
            if not priority:
                return "file://" + _local_path(url)
            _SEEN.discard(_QUEUED.pop())
        _SEEN.add(url)
        if priority:
            _QUEUED.insert(0, url)
        else:
            _QUEUED.append(url)
    return "file://" + _local_path(url)

def img_src(src):
    """返回该封面恒定不变的本地 file:// 路径（未下载时是占位图）。"""
    if not src:
        return ""
    hit = _SRC_CACHE.get(src)
    if hit:
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
            _SRC_CACHE.clear()
        _SRC_CACHE[src] = "file://" + path
    return "file://" + path

def _worker():
    while True:
        with _LOCK:
            if _QUEUED:
                url = _QUEUED.pop(0)
                _SEEN.discard(url)
            else:
                url = None
        if url is None:
            time.sleep(0.15)
            continue
        if _download_one(url):
            with _LOCK:
                _DOWNLOADED[url] = None
                _DOWNLOADED.move_to_end(url)
                while len(_DOWNLOADED) > MAX_DOWNLOADED:
                    _DOWNLOADED.popitem(last=False)
                _DOWNLOAD_ATTEMPTS.pop(url, None)
            global _RELOAD_DIRTY, _LAST_ACTIVITY
            _RELOAD_DIRTY = True
            _LAST_ACTIVITY = time.time()
            time.sleep(0.05)
        else:
            with _LOCK:
                attempts = _DOWNLOAD_ATTEMPTS.get(url, 0) + 1
                _DOWNLOAD_ATTEMPTS[url] = attempts
                if attempts < MAX_DOWNLOAD_ATTEMPTS:
                    _SEEN.add(url)
                    _QUEUED.append(url)
                else:
                    _DOWNLOAD_ATTEMPTS.pop(url, None)
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
    sample_index=0,         # 样片大图当前页（可左右滑动翻看）
    show_page_input=False,  # 页码跳转弹层（由原生 coordinator 快路径呈现/关闭）
    name_text="",           # 详情页标题的中文译文（空表示尚未翻译完成）
    title_trans=False,      # 标题是否已翻译成中文
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

DEFAULT_SETTINGS = {
    "page_size": 9,         # 每页显示多少项
    "player": "SenPlayer",  # 外部播放器
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
    except Exception:
        pass
    try:
        size = int(data["page_size"])
    except Exception:
        size = DEFAULT_SETTINGS["page_size"]
    data["page_size"] = size if size in PAGE_SIZE_OPTIONS else DEFAULT_SETTINGS["page_size"]
    if data["player"] not in EXTERNAL_PLAYERS:
        data["player"] = DEFAULT_SETTINGS["player"]
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

def page_size():
    """当前每页项数。"""
    try:
        return max(1, int(SETTINGS["page_size"]))
    except Exception:
        return 9


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
            data["fav"] = data["fav"][:MAX_LIST_ITEMS]
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
    del SHELF["fav"][MAX_LIST_ITEMS:]
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
_MOVIE_QUEUE = []
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
        with _MOVIE_LOCK:
            ready = time.time() >= _MOVIE_PAUSE_UNTIL
            code = _MOVIE_QUEUE.pop(0) if _MOVIE_QUEUE and ready else ""
        if not code:
            time.sleep(0.15)
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
                _MOVIE_QUEUE.append(code)
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

def load_fav_movies():
    """收藏里缺封面的番号排入后台补全队列；已有封面的直接请求下载。"""
    global _MOVIE_PAUSE_UNTIL
    _start_movie_workers()
    cached_images = []
    with _MOVIE_LOCK:
        _MOVIE_PAUSE_UNTIL = 0.0
        for item in SHELF["fav"][:MAX_LIST_ITEMS]:
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
                _MOVIE_QUEUE.append(code)
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

def fetch_movie_page(url):
    """抓取一页影片列表；无结果时返回 'empty'。"""
    html = get(url)
    if not html or "404 Page Not Found" in html:
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
    """抓取分类页并按主题分组（实现与原 JS 一致）。"""
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

def fetch_detail(url):
    """抓取并解析详情页，返回完整详情 dict。"""
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
    # 标题在 <a class="bigImage" href="..." title="..."> 标签上（与原 JS 一致）
    t = re.search(r'<a class="bigImage" href="[^"]*" title="([^"]*)"', html)
    if t:
        d["name"] = t.group(1).strip()
    else:
        # 兜底：个别页面 title 属性在 <a> 内的 <img> 上
        t = re.search(r'<a class="bigImage"[\s\S]{0,200}?<img[^>]*title="([^"]*)"', html)
        if t:
            d["name"] = t.group(1).strip()
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
    code = d["code"].lower()
    fanza = code.replace("-", "00", 1)
    if fanza:
        d["trailer"] = (f"https://cc3001.dmm.co.jp/litevideo/freepv/{fanza[0]}/"
                        f"{fanza[:3]}/{fanza}/{fanza}_sm_w.mp4")
        d["trailer2"] = "https://eightcha.com/" + code + "/preview.mp4"
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
    """数据池末尾对应的全局序号（不含）。"""
    return v["base"] + len(v["pool"])

def page_items(vid):
    """当前页要显示的影片：按已固定的数据池顺序直接切片。"""
    v = VIEWS.get(vid)
    if not v:
        return []
    size = page_size()
    start = (v["page"] - 1) * size - v["base"]
    if start < 0:
        return []
    return list(v["pool"][start:start + size])

def page_loading(vid):
    """当前页还没被数据池完整覆盖（用于在网格下方显示加载指示）。"""
    v = VIEWS.get(vid)
    if not v:
        return False
    return pool_end(v) < v["page"] * page_size() and not v["exhausted"]

def can_next(vid):
    """是否还能往后翻。"""
    v = VIEWS[vid]
    if pool_end(v) > v["page"] * page_size():
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

def mark_views_dirty():
    """标记展示数据已变化，等主线程刷新。"""
    global _VIEWS_DIRTY
    _VIEWS_DIRTY = True

def preload_ahead():
    """预加载页数：每页项数越大，预加载页数越少，控制同时下载与渲染的封面量。"""
    return 1 if page_size() >= 12 else 2

def load_window_end(v):
    """预加载窗口末尾（全局序号，不含）。"""
    return (v["page"] + preload_ahead()) * page_size()

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
        if v["exhausted"] and not force:
            return
        v["pool"] = fav_items()
        v["base"] = 0
        v["remote"] = 1
        v["exhausted"] = True
        v["loading"] = False
        # 自动补全封面：已有封面的直接下载，缺失的按番号后台解析
        load_fav_movies()
        mark_views_dirty()
        return
    if kind == "genre":
        # 分类：单次抓取全部分组，无翻页
        if v["exhausted"] and not force:
            return
        if v["loading"]:
            return
        v["loading"] = True
        threading.Thread(target=_genre_worker, args=(vid,), daemon=True).start()
        return
    if v["loading"] or v["exhausted"]:
        return
    if pool_end(v) >= load_window_end(v):
        return
    v["loading"] = True
    threading.Thread(target=_pump_worker, args=(vid,), daemon=True).start()

def _genre_worker(vid):
    """后台抓取分类分组（一次抓完，无翻页）。"""
    v = VIEWS.get(vid)
    if not v:
        return
    try:
        groups = fetch_genres()
        v["pool"] = groups if isinstance(groups, list) else []
        v["exhausted"] = True
    except Exception as e:
        log("genre err: " + str(e))
    finally:
        v["loading"] = False
        mark_views_dirty()

def _pump_worker(vid):
    """后台抓远程页：一轮最多抓 MAX_FETCH_PER_ROUND 页，只追加不覆盖。"""
    v = VIEWS.get(vid)
    if not v:
        return
    try:
        fetched = 0
        while fetched < MAX_FETCH_PER_ROUND:
            if pool_end(v) >= load_window_end(v) or v["exhausted"]:
                break
            res = fetch_view_page(v, v["remote"])
            if not res or res == "empty":
                v["exhausted"] = True
                break
            # 增量追加：新数据排在已有数据之后，已翻过的页码内容不受影响
            v["pool"].extend(sort_new_items(res))
            v["remote"] += 1
            fetched += 1
            for m in res:
                request_img(m.get("img") or "")
            _trim(v, page_size())
            mark_views_dirty()
            if fetched < MAX_FETCH_PER_ROUND:
                time.sleep(FETCH_GAP)
    except Exception as e:
        log("pump err: " + str(e))
    finally:
        v["loading"] = False
        mark_views_dirty()

def pump_all_views():
    """定时补足各展示位的预加载窗口（每轮只抓少量，逐步填充）。"""
    for vid in list(VIEWS):
        _pump(vid)

def set_filter(vid, flt):
    """切换展示位的筛选条件（重置翻页状态并重新抓取）。"""
    v = VIEWS.get(vid)
    if not v:
        return
    v["filter"] = flt
    v["page"] = 1
    v["pool"] = []
    v["base"] = 0
    v["remote"] = 1
    v["exhausted"] = False
    v["loading"] = False
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
    size = page_size()
    if (page - 1) * size < v["base"]:
        # 该页已被回收，回到第 1 页重新累积，避免一次性回抓大量历史页
        page = 1
        v["pool"] = []
        v["base"] = 0
        v["remote"] = 1
        v["exhausted"] = False
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
    if v["exhausted"]:
        size = page_size()
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
    threading.Thread(target=_detail_worker, args=(link, seq), daemon=True).start()

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
            mark_views_dirty()

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

    if _VIEWS_DIRTY and settled:
        _VIEWS_DIRTY = False
        state.reload += 1

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
        for s in d["samples"]:
            request_img(s["img"], priority=True)
            request_img(s["link"], priority=True)
        request_img(d["cover"], priority=True)
        # 标题默认翻译成中文展示（封面下方那一行）
        state.name_text = d.get("name") or ""
        state.title_trans = False
        translate_title_async(d)
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
_TRANS_READY = None        # (link, 译文)，由后台线程写入、主线程提交
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
    threading.Thread(target=_translate_worker, args=(link, text, seq),
                     daemon=True).start()

def _translate_worker(link, text, seq):
    global _TRANS_READY
    result = fetch_translation(text)
    if seq == _TRANS_SEQ and result:
        _TRANS_READY = (link, result)

def _commit_translation():
    """主线程提交翻译结果（转场静默期内暂缓，下一轮再试）。"""
    global _TRANS_READY
    if _TRANS_READY is None or not reload_allowed():
        return
    link, text = _TRANS_READY
    _TRANS_READY = None
    cur = state.detail
    if cur and cur.get("link") == link and state.detail_open:
        if len(_TRANS_CACHE) > 200:
            _TRANS_CACHE.clear()
        _TRANS_CACHE[str(cur.get("name") or "").strip()] = text
        state.name_text = text
        state.title_trans = True

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
    """详情页内嵌播放器（唯一实例，便于统一暂停/停止/关闭画中画）。"""
    global _PLAYER
    if _PLAYER is None:
        _PLAYER = appui.PlayerController(id="main", url="", autoplay=False,
                                         allows_pip=True, pause_on_disappear=True)
    return _PLAYER

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
        get_player().load(url, autoplay=True)
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
        state.detail = {"_loading": True,
                        "code": movie.get("code", ""),
                        "cover": movie.get("img", ""),
                        "name": movie.get("title", ""),
                        "link": link}
        need_fetch = True
    state.detail_open = True
    DETAIL_OPEN_AT = time.time()
    # 标题显示复位为日文原文，随后自动翻译成中文
    state.name_text = str((state.detail or {}).get("name") or "")
    state.title_trans = False
    if not need_fetch and state.name_text:
        translate_title_async(state.detail)
    # 详情与它内部的跳转列表都推入「打开它的那个展示位」的导航栈
    DETAIL_HOST = vid if vid in VIEWS else HOME_VID
    DETAIL_PATH = VIEWS[DETAIL_HOST]["path"]
    note_nav_action()
    DETAIL_PATH.append({"tag": "detail"})
    if need_fetch:
        request_detail(link)

def on_detail_closed():
    """详情被返回/关闭：复位标志并开启转场静默窗。"""
    state.detail_open = False
    note_nav_action()

def open_filter_at(path, link, value):
    """在指定导航栈推入一个按 link 筛选的影片列表（通用展示）。"""
    if not link:
        state.status = "无该字段链接"
        state.reload += 1
        return
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

def play_trailer():
    if state.detail and state.detail.get("trailer"):
        play_url(state.detail["trailer"], "Fanza 预告", source="预告")

def _spawn_play_fetch(task, fetching_msg, fail_msg):
    state.status = fetching_msg
    state.reload += 1

    def _work():
        result = task()
        if result:
            set_play_request(*result)
        else:
            set_play_error(fail_msg)

    threading.Thread(target=_work, daemon=True).start()

def play_jable_preview():
    code = state.detail.get("code") if state.detail else ""
    if not code:
        return

    def _fetch():
        preview, _ = fetch_jable(code)
        return (preview, "Jable 预览", "预览") if preview else None

    _spawn_play_fetch(_fetch, "正在获取 Jable 预览...", "Jable 无预览")

def play_jable():
    code = state.detail.get("code") if state.detail else ""
    if not code:
        return

    def _fetch():
        _, full = fetch_jable(code)
        return (full, "Jable 完整视频", "完整视频") if full else None

    _spawn_play_fetch(_fetch, "正在获取 Jable 完整视频...", "Jable 未找到完整视频")

def show_sample(link):
    """点击样片：定位到该样片页码后推入大图浏览，可左右滑动翻看其他样片。"""
    if not link:
        return
    samples = (state.detail or {}).get("samples") or []
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


def movie_cell(m, vid):
    """影片封面单元格（封面 + 番号 + 日期）。"""

    def open():
        open_detail(m, vid)

    return appui.Button(
        action=open,
        content=appui.VStack([
            appui.AsyncImage(url=img_src(m["img"]))
                .frame(height=165).clipped()
                .background("secondarySystemBackground", corner_radius=6),
            appui.Text(m["code"]).font("caption").line_limit(1),
            appui.Text(m["date"]).font("caption2").foreground_color("secondaryLabel"),
        ], spacing=3),
    ).button_style("plain").id(m.get("code") or m.get("link") or "")

def actress_cell(a):
    """女优头像单元格（与原 JS 一致：头像 + 名字，点击进入其作品列表）。"""

    def open():
        open_actress(a["link"], a["name"])

    return appui.Button(
        action=open,
        content=appui.VStack([
            appui.AsyncImage(url=img_src(a["img"]))
                .frame(height=130).clipped()
                .background("secondarySystemBackground", corner_radius=6),
            appui.Text(a["name"]).font("caption").line_limit(1),
        ], spacing=3),
    ).button_style("plain").id(a.get("link") or a.get("name") or "")

def genre_cell(c):
    """分类按钮（与原 JS 一致）。"""

    def open():
        open_genre(c["link"], c["name"])

    return appui.Button(content=appui.Label(c["name"], system_image="tag"),
                        action=open)

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
    """详情页样片缩略图（点击查看大图）。"""

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

def search_row(vid):
    """搜索栏（只有影片首页这一处展示需要）。"""
    field = appui.TextField("番号或演员", text=state.keyword, on_change=set_keyword) \
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

def movie_display(vid):
    """通用影片展示：封面网格 + 翻页条。

    vid 决定用哪个展示位；展示位的 filter 决定筛选条件，
    extras 决定这一处额外显示什么（搜索框 / 下拉刷新 / 提示行）。
    数据按发布时间从新到旧固定排列，增量加载只追加、不覆盖已有内容。
    """
    v = VIEWS.get(vid)
    if not v:
        return appui.Text("")
    ex = v["extras"]
    parts = []

    if ex.get("search"):
        parts.append(search_row(vid))

    loading = page_loading(vid)
    items = page_items(vid)
    if items:
        parts.append(appui.LazyVGrid(
            columns=[appui.adaptive(minimum=104)],
            spacing=10,
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

    parts.append(pager_row(vid))

    if ex.get("status") and state.status:
        parts.append(appui.Text(state.status).font("caption")
                     .foreground_color("secondaryLabel"))

    return appui.VStack(parts, spacing=12).padding()

def genre_display(vid):
    """类型展示：按主题分组的分类按钮（与原 JS 一致，单次抓取无翻页）。"""
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
    sections = []
    for group in v["pool"]:
        parts = [appui.Text(group["tag"]).font("headline").padding(top=10)]
        parts.append(appui.LazyVGrid(
            columns=[appui.adaptive(minimum=100)],
            spacing=8,
            content=[genre_cell(c) for c in group["cats"]],
        ))
        sections.append(appui.VStack(parts, spacing=8))
    return appui.VStack(sections, spacing=4).padding()

def display_page_view(vid):
    """把通用展示包装成可导航的页面（下拉刷新按附加设置决定）。"""
    v = VIEWS.get(vid)
    if not v:
        return appui.Text("")

    def refresh_view():
        reset_view(vid)

    content = genre_display(vid) if view_kind(vid) == "genre" else movie_display(vid)
    sv = appui.ScrollView(content)
    if v["extras"].get("refresh"):
        sv = sv.refreshable(action=refresh_view)
    return sv.navigation_title(view_title(vid))


# ============================================================
#  UI 层：路由目标（详情 / 大图 / 跳转列表）
# ============================================================


def detail_destination(data):
    """详情路由：所有入口统一走 detail_page_view()，展示完全一致。"""
    return detail_page_view().on_disappear(action=on_detail_closed)

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
    """详情加载中的占位视图：与加载完成后的布局骨架保持一致。"""
    code = d.get("code") or ""
    name = d.get("name") or ""
    cover = d.get("cover") or ""
    if not cover:
        return appui.VStack([
            appui.ProgressView(),
            appui.Text("加载中..." + name).foreground_color("secondaryLabel"),
        ], spacing=12).padding()

    top = appui.VStack([
        appui.Button(
            content=appui.Text(code).font("title2").bold().line_limit(1),
            action=copy_code,
        ).button_style("plain"),
        _cover_view(cover),
        appui.VStack([
            appui.Text(name).font("caption").foreground_color("secondaryLabel").line_limit(2),
            appui.HStack([
                appui.ProgressView().frame(height=14),
                appui.Text("正在加载详情...").font("caption").foreground_color("secondaryLabel"),
            ], spacing=6),
        ], spacing=4, alignment="leading"),
    ], spacing=12, alignment="leading")

    return appui.List([
        appui.Section([top.padding()]),
        appui.Section([appui.ProgressView()], header="详情"),
    ]).navigation_title("")

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
    action_btns = appui.HStack([
        eq_btn("预览", play_jable_preview, "预览"),
        eq_btn("预告", play_trailer, "预告"),
        eq_btn("视频", play_jable, "完整视频"),
        eq_btn(fav_title, toggle_fav, prominent=in_fav(d["code"])),
    ], spacing=8)

    top = appui.VStack([code_btn, cover, title_block, meta, action_btns],
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
            appui.VideoPlayer(player=get_player()).frame(height=220),
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

    def cat_chip(genre):
        def open():
            open_filter(genre["link"], genre["name"])

        return appui.Button(content=appui.Text(genre["name"]).line_limit(1),
                            action=open).button_style("bordered")

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

    sections = [appui.Section(detail_rows, header="详情")]
    if d["samples"]:
        sections.append(appui.Section([
            appui.LazyVGrid(
                columns=[appui.adaptive(minimum=118)],
                spacing=8,
                content=[sample_cell(s) for s in d["samples"]],
            )
        ], header="样片(点击看大图)"))
    if d["magnets"]:
        sections.append(appui.Section(
            [magnet_row(m) for m in d["magnets"]], header="磁链"))

    # 不再以番号作为导航标题：番号只在正文中展示（点击可复制）
    return appui.List([appui.Section([top.padding()])] + sections) \
        .navigation_title("")

def sample_preview_view():
    """样片大图浏览：左右滑动可依次查看其他样片，关闭按钮略微上移。"""
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
            appui.Button("关闭", action=close_sample).padding(bottom=24),
        ], spacing=12)
    index = max(0, min(int(state.sample_index), len(pages) - 1))
    return appui.VStack([
        appui.TabView(tabs=pages, selection=state.bind.sample_index)
            .tab_view_style("page")
            .frame(max_width=appui.infinity, max_height=appui.infinity),
        appui.HStack([
            appui.Text(str(index + 1) + " / " + str(len(pages)))
                .font("caption").foreground_color("secondaryLabel"),
            appui.Button("关闭", action=close_sample).padding(bottom=24),
        ], spacing=12),
    ], spacing=12)


# ============================================================
#  UI 层：影片 tab / 设置 tab
# ============================================================


def set_keyword(v):
    state.keyword = v

def do_search():
    """在影片首页发起搜索：把首页展示位的筛选条件换成关键词。"""
    kw = norm_keyword(state.keyword)
    state.keyword = kw
    if not kw:
        clear_search()
        return
    set_filter(HOME_VID, {"kind": "search", "keyword": kw, "title": "搜索 " + kw})

def clear_search():
    """退出搜索，回到最新影片。"""
    state.keyword = ""
    set_filter(HOME_VID, HOME_FILTER)

_LIST_DESTINATIONS = {"detail": detail_destination,
                      "sample": sample_destination,
                      "list": list_destination}

def movies_tab():
    return appui.NavigationStack(
        display_page_view(HOME_VID),
        path=PATH_MOVIES,
        destinations=_LIST_DESTINATIONS,
    ).id("movies")

def actress_tab():
    """女优 tab：头像网格 + 翻页，点击进入该女优的作品列表。"""
    return appui.NavigationStack(
        display_page_view(ACTRESS_VID),
        path=PATH_ACT,
        destinations=_LIST_DESTINATIONS,
    ).on_appear(action=load_actresses_once).id("actress")

def genre_tab():
    """类型 tab：按主题分组的分类按钮，点击进入该分类的影片列表。"""
    return appui.NavigationStack(
        display_page_view(GENRE_VID),
        path=PATH_GENRE,
        destinations=_LIST_DESTINATIONS,
    ).on_appear(action=load_genres_once).id("genre")

def fav_tab():
    """收藏 tab：封面网格 + 翻页，长按可从收藏移除。"""
    return appui.NavigationStack(
        display_page_view(FAV_VID),
        path=PATH_FAV,
        destinations=_LIST_DESTINATIONS,
    ).id("fav")

def set_page_size(v):
    try:
        size = int(v)
    except Exception:
        return
    if size not in PAGE_SIZE_OPTIONS:
        return
    SETTINGS["page_size"] = size
    save_settings()
    for vid in list(VIEWS):
        item = VIEWS[vid]
        item["page"] = 1
        if item["base"]:
            # 每页项数变了，旧的分页偏移失效，回到起点重新累积
            item["pool"] = []
            item["base"] = 0
            item["remote"] = 1
            item["exhausted"] = False
        _pump(vid)
    state.reload += 1

def set_player(name):
    if name not in EXTERNAL_PLAYERS:
        return
    SETTINGS["player"] = name
    save_settings()
    state.reload += 1

def settings_tab():
    return appui.NavigationStack(
        appui.Form([
            appui.Section([
                appui.Picker("每页显示",
                             selection=str(page_size()),
                             options=[str(x) for x in PAGE_SIZE_OPTIONS],
                             on_change=set_page_size),
            ], header="展示",
               footer="每页项数对所有影片列表生效；列表顺序固定为发布时间从新到旧。"),
            appui.Section([
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
        ]).navigation_title("设置"),
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
    state.status = ""
    state.sample_index = 0
    state.show_page_input = False
    state.name_text = ""
    state.title_trans = False
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

def make_body():
    return appui.TabView(
        tabs=[
            appui.Tab("影片", system_image="play.rectangle", content=movies_tab(), tag=0),
            appui.Tab("女优", system_image="person.2", content=actress_tab(), tag=1),
            appui.Tab("类型", system_image="tag", content=genre_tab(), tag=2),
            appui.Tab("收藏", system_image="star", content=fav_tab(), tag=3),
            appui.Tab("设置", system_image="gear", content=settings_tab(), tag=4),
        ],
        selection=state.bind.tab,
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
