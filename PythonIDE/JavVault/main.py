# -*- coding: utf-8 -*-
# ============================================================
#  JavBus 播放器 · PythonIDE AppUI  
#  移植自 JSBox 版 (核心功能 + 多源预览)
#  数据来源: https://www.javbus.com
# ============================================================

import json
import os
import hashlib
import struct
import tempfile
import threading
import time
import zlib
from collections import OrderedDict
import datetime
import re
from urllib.parse import quote

import network
import appui
import clipboard
import shortcuts


# ============================================================
#  基础层：站点常量 / 请求头 / 应用版本
# ============================================================


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
            return str(json.load(f).get("version", "2.0"))
    except Exception:
        return "2.0"

# 各 tab 顶部导航栏标题
APP_TITLE = "JavVault"
# 应用版本号（来自 miniapp.json，作为副标题展示）
APP_VERSION = _app_version()


# ============================================================
#  基础层：应用内日志
# ============================================================


# 环形缓冲：最多保留 300 条，超出后丢弃最早 100 条
LOG = []

def log(msg):
    try:
        LOG.append(str(msg))
        if len(LOG) > 300:
            del LOG[:100]
    except Exception:
        pass


# ============================================================
#  基础层：通用 HTTP 网络
# ============================================================


def get(url, cookie_all=False):
    """GET 请求返回文本；失败返回空串。cookie_all 时带上 existmag=all 显示全量。"""
    headers = dict(HEADERS)
    if cookie_all:
        headers["Cookie"] = "existmag=all"
    try:
        resp = network.get(url, headers=headers, timeout=15)
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
#  基础层：封面后台下载与磁盘/内存缓存
# ============================================================


# 已成功下载到磁盘的 url（有界，防止长时间运行持续占用内存）
_DOWNLOADED = OrderedDict()
# img_src 结果缓存：src -> "file://" 本地路径。路径恒定、首建即存在，
# 缓存后可避免整树重建时为每个单元格重复做 md5 + 文件系统访问
# （iOS 低性能 Python 环境下列表重建收益明显）。
_SRC_CACHE = {}
_SRC_CACHE_MAX = 4096
# 待下载队列和成功记录的内存上限
MAX_QUEUE = 1024
MAX_DOWNLOADED = 2048
# 单张图片下载失败的最大重试次数（网络抖动/防盗链偶发 403 时避免封面永久空白）
MAX_DOWNLOAD_ATTEMPTS = 5
# 已入队/处理中的 url（去重，避免同一张图排队多次）
_SEEN = set()
# 各 url 已重试次数（线程安全，由锁保护）
_DOWNLOAD_ATTEMPTS = {}
# 待下载 url 队列（线程安全，由锁保护）
_QUEUED = []
# 队列锁
_LOCK = threading.Lock()
# 并发下载线程数：iOS 低配机降低并发，避免瞬时下载风暴抢占主线程/造成卡顿
WORKERS = 3
# 本次循环中是否有图片下载完成（主线程据此决定是否刷新列表）
_RELOAD_DIRTY = False
# 最近一次图片下载活动时刻（用于去抖：一段时间无新下载完成才刷新）
_LAST_ACTIVITY = 0.0
# worker 是否已启动
_CACHE_STARTED = False

# 占位图字节（纯色小 PNG，用 stdlib 生成，首次请求时落盘）
_PLACEHOLDER = None

def _placeholder_bytes():
    """生成一张纯色占位 PNG（8x12 浅灰），仅用 stdlib。"""
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        w, h = 8, 12
        rgb = (0xED, 0xED, 0xEF)   # systemGray6 近似
        sig = b"\x89PNG\r\n\x1a\n"

        def _chunk(typ, data):
            return (struct.pack(">I", len(data)) + typ + data +
                    struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))

        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8bit RGB
        raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
        idat = zlib.compress(raw, 9)
        _PLACEHOLDER = (sig + _chunk(b"IHDR", ihdr) +
                        _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))
    return _PLACEHOLDER

def _image_dir():
    """图片缓存目录（临时目录，重启后可重建）。"""
    d = os.path.join(tempfile.gettempdir(), "javbus_img")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d

def _to_abs(src):
    """把相对路径图源补全成完整 URL。"""
    if src.startswith("http") or src.startswith("file://"):
        return src
    return BASE + src

def _local_path(url):
    """由 URL 唯一确定本地缓存文件路径（供 AsyncImage 恒定引用）。"""
    key = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(_image_dir(), key + ".jpg")

def _is_image(data):
    """用 magic bytes 判断下载内容是否为真实图片（拦截 403/HTML 防盗链页）。"""
    if not data:
        return False
    head = data[:16]
    if head.startswith(b"\xff\xd8\xff"):
        return True                                       # JPEG
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True                                       # PNG
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return True                                       # GIF
    if head.startswith(b"RIFF"):
        return head[8:12] == b"WEBP"                       # WebP
    if head.startswith(b"BM"):
        return True                                       # BMP
    return False

def _download_one(url):
    """后台线程实际下载一张图，下载成功后原子替换占位文件。

    成功返回 True；失败返回 None（占位图保留，文件仍存在，由调用方重试）。
    失败包括：非 2xx、超时、内容为空、或内容不是图片（防盗链返回 HTML 页）。
    """
    try:
        path = _local_path(url)
        headers = dict(HEADERS)
        with network.stream("GET", url, headers=headers, timeout=12) as resp:
            if not resp.ok:
                return None
            # 限 1MB/图，控制 iOS 内存峰值
            data = resp.read(max_bytes=1 * 1024 * 1024)
            if not data:
                return None
            # 防盗链常返回 200+HTML，必须校验为真实图片，否则会写入坏封面
            if not _is_image(data):
                return None
            # 先写临时文件再替换，避免半途写坏被界面读到
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            return True
    except Exception:
        return None

def request_img(src, priority=False):
    """登记一张图到后台下载队列（触发后台下载）。

    priority=True 时插到队首（详情页、刚加载的新封面等关键图优先下载），
    不设队列数量上限；若已成功下载则直接跳过。
    """
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
    """返回该封面恒定不变的本地 file:// 路径（路径必已存在：首次写入占位图）。

    未下载完成时显示占位色块，下载完成后路径相同、文件被真实封面原子替换，
    由一次去抖 reload 触发 AsyncImage 重新读取；url 不变故不会闪烁。
    结果按 src 缓存，重复重建不再做 md5/stat/写盘。
    """
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
    """单个下载线程：从队列取一个下载，成功后记入已下载集合并标记刷新。

    失败时有限重试（每次失败随机退避），避免某张图偶发请求失败后永久空白，
    导致封面"加载几张就卡住"。重试耗尽时放弃该 url；再次 request_img 会重新入队。
    """
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
            # 失败：退避后回队重试，成功前保持 in _SEEN 防止重复入队
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
    """启动并发下载线程（只执行一次）。"""
    global _CACHE_STARTED
    if _CACHE_STARTED:
        return
    _CACHE_STARTED = True
    for _ in range(WORKERS):
        threading.Thread(target=_worker, daemon=True).start()

def is_dirty():
    """是否有图片下载完成待刷新。"""
    return _RELOAD_DIRTY

def mark_dirty():
    """标记图片来源已更新，等待主线程刷新。"""
    global _RELOAD_DIRTY, _LAST_ACTIVITY
    _RELOAD_DIRTY = True
    _LAST_ACTIVITY = time.time()

def clear_dirty():
    """清除图片下载完成标记。"""
    global _RELOAD_DIRTY
    _RELOAD_DIRTY = False

def last_activity():
    """最近一次图片下载完成的时刻。"""
    return _LAST_ACTIVITY


# ============================================================
#  基础层：全局 AppUI 状态与导航路径
# ============================================================


# Bound in-memory collections so repeated pagination cannot grow without limit.
MAX_LIST_ITEMS = 1000

# 全局界面状态（唯一实例，由 main.py 传入 appui.run）
state = appui.State(
    all_flag=False,
    mode="home",        # home 首页 / search 首页内搜索（共用 movies 列表）
    keyword="",
    cat_link="",
    movies=[],
    movies_page=1,
    sub_title="",
    sub_link="",
    sub_movies=[],
    sub_page=1,
    actresses=[],
    actress_page=1,
    genres=[],
    detail=None,
    detail_open=False,      # 详情页当前是否仍在导航栈顶（返回/关闭时由 on_disappear 置 False）
    detail_thumb="",        # 打开详情时列表项自带的缩略图（收藏封面用，详情抓取后保留）
    panel="",
    panel_title="",
    play="",            # 当前播放来源："" / 预览 / 预告 / 完整视频
    sample_preview="",
    tab=0,
    reload=0,
    status="",
    browse_loading=False,   # 影片 tab 列表后台抓取中
    sub_loading=False,      # 子作品列表后台抓取中
    actress_loading=False,  # 女优列表后台抓取中
)

# 每个 tab 独立的导航栈（详情 / 子列表用 NavigationPath 推送，避免 body 重建丢失路由）
PATH_BROWSE = appui.NavigationPath()
PATH_ACT = appui.NavigationPath()
PATH_CAT = appui.NavigationPath()
PATH_SHELF = appui.NavigationPath()

# 详情/大图当前所在的导航栈（跨模块共享，通过函数读写避免 stale 引用）
# 每个"可推入内容"记住自己所属的导航栈：push/pop 只操作自己的栈，
# 与当前活跃 tab 完全解耦，杜绝跨 tab 推错栈导致的乱跳。
DETAIL_PATH = PATH_BROWSE   # 当前详情页所属栈
DETAIL_OPEN_AT = 0.0        # 最近一次进入详情的时刻（详情提交避开返回转场用）
SUB_PATH = PATH_BROWSE      # 当前子列表所属栈


# ============================================================
#  数据层：收藏持久化
# ============================================================


# 收藏持久化文件（放在 MiniApp 包目录，便于同步与备份）
FAV_FILE = os.path.join(os.getcwd(), "favorites.json")
# 旧版备份文件名：首次运行时把已有收藏迁移到 favorites.json
_LEGACY_FAV_FILE = os.path.join(os.getcwd(), "JavVault_Backup.json")
def _fav_path():
    """返回收藏文件路径；若旧版文件仍存在则先迁移到新文件名。"""
    if not os.path.exists(FAV_FILE) and os.path.exists(_LEGACY_FAV_FILE):
        try:
            os.replace(_LEGACY_FAV_FILE, FAV_FILE)
        except Exception:
            pass
    return FAV_FILE


def load_shelf():
    """从收藏文件读取数据；文件缺失/损坏时返回空结构。"""
    try:
        path = _fav_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
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
    """原子写回收藏文件（先写临时文件再替换）。"""
    try:
        tmp = FAV_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(SHELF, f, ensure_ascii=False, indent=2)
        os.replace(tmp, FAV_FILE)
    except Exception as e:
        log("save_shelf err: " + str(e))

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

def toggle_bookmark(d, img=""):
    """切换收藏状态并保存；d 为当前详情 dict。img 为列表缩略图（零请求缓存封面）。"""
    code = d["code"]
    if in_fav(code):
        remove_fav(code)
    else:
        add_fav(code, img=img)
    save_shelf()


# ============================================================
#  解析层：列表页（影片 / 女优 / 分类）
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

def fetch_movie_page(url, all_flag=False):
    """抓取一页影片列表；无结果时返回 'empty'。all_flag 带上 existmag=all。"""
    html = get(url, all_flag)
    if not html or "404 Page Not Found" in html:
        return "empty"
    if "沒有您要的結果" in html:
        return "empty"
    return parse_movies(html)

def fetch_actresses(page, homepage):
    """抓取女优一页（homepage 为站点基础路径）。"""
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

# ============================================================
#  解析层：影片详情页
# ============================================================


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
    # 完整视频走 Jable m3u8，详情只需请求一页 HTML 即可返回。
    # Fanza 预告：原 JS 将第一个 "-" 替换为 "00" 后拼接
    code = d["code"].lower()
    fanza = code.replace("-", "00", 1)
    if fanza:
        d["trailer"] = (f"https://cc3001.dmm.co.jp/litevideo/freepv/{fanza[0]}/"
                        f"{fanza[:3]}/{fanza}/{fanza}_sm_w.mp4")
        # 第二预告来源：Missav 预览（对应原 JS preMissav）
        d["trailer2"] = "https://eightcha.com/" + d["code"].lower() + "/preview.mp4"
    return d


# ============================================================
#  解析层：Jable / Avgle 多源播放地址
# ============================================================


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

# ============================================================
#  调度层：后台任务（详情 / 列表抓取、图片刷新、播放提交）
# ============================================================


# 详情抓取请求/结果（由后台线程写入，主线程 _sync_dirty 提交）
_DETAIL_READY = None       # 已抓取的详情 dict
_DETAIL_ERROR = False
_DETAIL_SEQ = 0            # 使旧详情线程的结果失效

# 导航转场"静默期"：每次点击引起的导航（push/pop/面板动画）前开启，
# 期间所有后台驱动的整树刷新（图片去抖、详情提交、列表提交）暂缓，
# 使快速点击 / 跨 tab 点击也不会出现 reload 打断转场动画的乱跳。
_RELOAD_SILENT_UNTIL = 0.0
_NAV_SILENCE = 0.8         # 秒；iOS 转场动画比 macOS 略长，放宽静默窗避免撞上动画

# tab 切换宽限期：切 tab 后的一段时间内不整树刷新，
# 避免新 tab 大树刚挂载/动画期间被 reload 打断导致卡顿。
_LAST_TAB = -1
_LAST_TAB_SWITCH = 0.0
TAB_RELOAD_GRACE = 0.6

# 播放请求（后台抓取成功后由主线程提交给播放器）
_PLAY_REQUEST = None       # (url, title, source)
_PLAY_ERROR = ""           # 后台抓取失败时的提示

# 图片刷新：下载完成后需静默多久才整树重建（去抖，防止闪烁）。
# 数值偏大以压低 iOS 上整树重建频率（每次 reload 都会重建全部 tab）。
_LAST_IMG_RELOAD = 0.0
IMG_SILENCE_INTERVAL = 0.9
IMG_MAX_RELOAD_INTERVAL = 3.0
# 任意两次整树刷新之间的最小间隔（压住下载风暴期高频刷新，
# 大幅降低刷新撞上返回转场窗口的概率）
IMG_RELOAD_MIN_GAP = 2.0
# 详情页打开期间：overdue 触发刷新的最大等待，及两次刷新的最小间隔。
# 详情页大图/样图/头像成批下载，阅读期间用更长间隔，避免反复整树重建卡顿。
IMG_MAX_RELOAD_LONG = 6.0
IMG_RELOAD_MIN_GAP_DETAIL = 2.5

_BG_STARTED = False

def request_detail(link):
    """登记详情抓取请求并启动后台线程。"""
    global _DETAIL_READY, _DETAIL_ERROR, _DETAIL_SEQ
    _DETAIL_SEQ += 1
    seq = _DETAIL_SEQ
    _DETAIL_READY = None
    _DETAIL_ERROR = False
    threading.Thread(target=_detail_worker, args=(link, seq), daemon=True).start()

def take_ready(link):
    """取回后台已抓好的同链接详情（返回后重进同一番号时秒开，零请求）。

    失败结果的详情不返回：重进时走重新抓取。取走后清除，避免下次误复用。
    """
    global _DETAIL_READY
    if _DETAIL_READY and _DETAIL_READY.get("link") == link \
            and not _DETAIL_READY.get("error"):
        r = _DETAIL_READY
        _DETAIL_READY = None
        return r
    return None

def note_nav_action():
    """任何点击引起的导航/面板转场前调用：开启转场静默窗。

    期间所有后台驱动的整树刷新（图片去抖、详情提交、列表提交）全部暂缓，
    使快速连点 / 跨 tab 点击也不会出现 reload 打断转场导致的乱跳。
    """
    global _RELOAD_SILENT_UNTIL
    _RELOAD_SILENT_UNTIL = time.time() + _NAV_SILENCE

def reload_allowed():
    """当前是否允许整树刷新（避开 push/pop 转场动画窗口）。"""
    return time.time() >= _RELOAD_SILENT_UNTIL

# 详情提交专用门控：只避开"返回转场"。进入详情超过 _DETAIL_SAFE_AFTER 后，
# 顶部视图上整树刷新与转场动画不再冲突，抓取一完成即可立刻提交，
# 不再被进入时的静默窗拖慢。取值略大于 push 动画时长即可。
_DETAIL_SAFE_AFTER = 0.6

def detail_commit_allowed():
    """详情提交是否允许立即刷新（已避开所有转场窗口）。"""
    if reload_allowed():
        return True
    if state.detail_open and DETAIL_OPEN_AT > 0 \
            and time.time() - DETAIL_OPEN_AT >= _DETAIL_SAFE_AFTER:
        return True
    return False

def _detail_worker(link, seq):
    """后台详情抓取线程（不会阻塞主循环）."""
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

# 列表页抓取（影片 / 子列表 / 女优 / 分类共用后台通道）
_PAGE_READY = None         # (kind, append, result)
_PAGE_SEQ = 0

def request_page(url, kind, append=False, all_flag=False):
    """登记列表页抓取请求并启动后台线程（主线程不再同步阻塞网络）。"""
    global _PAGE_READY, _PAGE_SEQ
    _PAGE_SEQ += 1
    seq = _PAGE_SEQ
    _PAGE_READY = None
    threading.Thread(target=_page_worker, args=(url, kind, append, all_flag, seq), daemon=True).start()

def _page_worker(url, kind, append, all_flag, seq):
    """后台列表抓取线程（不阻塞主循环）。"""
    global _PAGE_READY
    if kind == "genre":
        fetcher = fetch_genres
        args = ()
    elif kind == "actress":
        fetcher = fetch_actresses
        page = url.rsplit("/", 1)[-1]
        try:
            page = int(page)
        except Exception:
            page = 0
        home = BASE + "/"
        args = (page, home)
    else:
        fetcher = fetch_movie_page
        args = (url, all_flag)
    try:
        result = fetcher(*args)
    except Exception:
        result = "empty" if kind in ("browse", "sub") else []
    if seq == _PAGE_SEQ:
        _PAGE_READY = (kind, append, result)

def _commit_page():
    """主线程 Timer：提交后台抓回的列表页数据（转场静默窗内暂缓）。"""
    global _PAGE_READY
    if _PAGE_READY is not None:
        kind, append, res = _PAGE_READY
        _PAGE_READY = None
        if not reload_allowed():
            _PAGE_READY = (kind, append, res)
            return
        if kind == "browse":
            items = (res if res != "empty" else [])[:MAX_LIST_ITEMS]
            if append:
                if items:
                    state.movies_page += 1
                    state.movies = (state.movies + items)[:MAX_LIST_ITEMS]
            else:
                state.movies_page = 1
                state.movies = items
            for m in items:
                request_img(m["img"], priority=append)
            state.browse_loading = False
        elif kind == "sub":
            items = (res if res != "empty" else [])[:MAX_LIST_ITEMS]
            if append:
                if items:
                    state.sub_page += 1
                    state.sub_movies = (state.sub_movies + items)[:MAX_LIST_ITEMS]
            else:
                state.sub_page = 1
                state.sub_movies = items
            for m in items:
                request_img(m["img"], priority=append)
            state.sub_loading = False
        elif kind == "actress":
            items = (res if isinstance(res, list) else [])[:MAX_LIST_ITEMS]
            if append:
                if items:
                    state.actress_page += 1
                    state.actresses = (state.actresses + items)[:MAX_LIST_ITEMS]
            else:
                state.actress_page = 1
                state.actresses = items
            for it in items:
                request_img(it["img"], priority=append)
            state.actress_loading = False
        elif kind == "genre":
            state.genres = res if isinstance(res, list) else []
        state.reload += 1

def set_play_request(url, title, source):
    """后台线程登记一条待播放链接（成功路径）。"""
    global _PLAY_REQUEST, _PLAY_ERROR
    _PLAY_REQUEST = (url, title, source)
    _PLAY_ERROR = ""

def set_play_error(message):
    """后台线程登记一条播放失败提示。"""
    global _PLAY_REQUEST, _PLAY_ERROR
    _PLAY_REQUEST = None
    _PLAY_ERROR = message

def play_url(url, title="", source=""):
    """直接播放 URL（与原始 JS play(url) 一致）。source 标记当前来源用于按键高亮。"""
    log("play: " + str(title) + " -> " + str(url)[:120])
    state.panel = url
    state.panel_title = title
    state.play = source
    state.status = ""
    state.reload += 1

def _sync_dirty():
    """主线程周期任务：图片刷新 + 播放请求 + 详情提交。"""
    global _PLAY_REQUEST, _PLAY_ERROR, _LAST_IMG_RELOAD
    global _LAST_TAB, _LAST_TAB_SWITCH
    now = time.time()
    # 记录 tab 切换时刻：切 tab 后的宽限期内不做整树刷新，
    # 避免新 tab 大树挂载/切换动画期间被 reload 打断造成卡顿。
    if state.tab != _LAST_TAB:
        _LAST_TAB = state.tab
        _LAST_TAB_SWITCH = now
    settled = reload_allowed() and (now - _LAST_TAB_SWITCH) >= TAB_RELOAD_GRACE
    # 图片刷新用"去抖"：下载高峰期间不刷新，等这一批全部下载完、静默一段
    # 时间后再整树重建一次，避免多张封面连续完成导致列表不停闪烁。
    if is_dirty():
        quiet = now - last_activity() >= IMG_SILENCE_INTERVAL
        detail = state.detail_open
        # 详情页打开期间：overdue / 两次刷新最小间隔都用更长值，
        # 大图/样图/头像成批下载时避免反复整树重建导致阅读卡顿
        max_wait = IMG_MAX_RELOAD_LONG if detail else IMG_MAX_RELOAD_INTERVAL
        min_gap = IMG_RELOAD_MIN_GAP_DETAIL if detail else IMG_RELOAD_MIN_GAP
        overdue = now - _LAST_IMG_RELOAD >= max_wait
        if (quiet or overdue) and settled and now - _LAST_IMG_RELOAD >= min_gap:
            clear_dirty()
            _LAST_IMG_RELOAD = now
            state.reload += 1
    # 提交后台线程抓到的待播放链接（转场静默窗内暂缓，避免撞上返回动画）
    if _PLAY_REQUEST and settled:
        url, title, source = _PLAY_REQUEST
        _PLAY_REQUEST = None
        state.status = ""
        play_url(url, title, source=source)
    elif _PLAY_ERROR and settled:
        state.status = _PLAY_ERROR
        _PLAY_ERROR = ""
        state.reload += 1
    if settled:
        _commit_page()
    # 详情提交不受 settled 门控：进入详情后只要过了转场安全窗就立刻提交，
    # 让详情内容尽快填上（抓取完成越早，进入体验越快）。
    _commit_detail()

def _commit_detail():
    """主线程 Timer：若后台详情已就绪则提交到 state。"""
    global _DETAIL_READY, _DETAIL_ERROR
    if _DETAIL_READY is not None:
        d = _DETAIL_READY
        _DETAIL_READY = None
        cur = state.detail
        # 用户已返回列表（详情被 pop）：静默保留同链接数据供重进秒开，
        # 不写 state、不请求图片、不触发整树刷新（避开返回转场窗口）。
        if not state.detail_open:
            if cur and cur.get("link") == d.get("link"):
                _DETAIL_READY = d
            return
        # 若用户已切换到别的详情，则不强制覆盖当前占位
        if cur and cur.get("link") != d.get("link"):
            return
        # 详情提交只避开"返回转场"；仍在详情阅读中则立即提交，不拖慢展示
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
        # 详情页解析不出番号时，用占位的番号兜底（保证收藏/按钮状态一致）
        if not d.get("code") and cur and cur.get("code"):
            d["code"] = cur["code"]
        if not d.get("cover") and cur and cur.get("cover"):
            d["cover"] = cur["cover"]
        # 就地合并到现有 dict：不换对象，避免 State 赋值自动刷新 + 显式
        # reload 造成两次连续整树重建（闪烁来源之一）
        if cur:
            for k, v in d.items():
                cur[k] = v
            cur.pop("_loading", None)
            cur.pop("error", None)
        else:
            state.detail = d
        # 详情图用 priority：插入队首，保证立刻下载，不被首页封面队列挤掉
        for a in d["actresses"]:
            request_img(a["img"], priority=True)
        for s in d["samples"]:
            request_img(s["img"], priority=True)
            request_img(s["link"], priority=True)   # 大图也缓存，供查看大图用
        request_img(d["cover"], priority=True)
        state.reload += 1
    elif _DETAIL_ERROR:
        _DETAIL_ERROR = False
        log("detail fetch error")
        # 用户已返回：静默丢弃错误（重进会重新抓取），不触发整树刷新
        if not state.detail_open:
            return
        cur = state.detail
        if cur and cur.get("_loading"):
            cur["_loading"] = False
            cur["error"] = True
        state.reload += 1

def reset_pending():
    """冷启动清空所有后台待办。"""
    global _DETAIL_READY, _DETAIL_ERROR, _DETAIL_SEQ, _PLAY_REQUEST, _PLAY_ERROR
    _DETAIL_SEQ += 1
    _DETAIL_READY = None
    _DETAIL_ERROR = False
    _PLAY_REQUEST = None
    _PLAY_ERROR = ""

def init_background():
    """启动图片下载线程与主线程刷新 Timer（只执行一次）。"""
    global _BG_STARTED
    if _BG_STARTED:
        return
    _BG_STARTED = True
    # 多线程并发下载 + 主线程周期刷新
    start_workers()
    appui.Timer(interval=0.5, action=_sync_dirty).start()


# ============================================================
#  UI 层：业务动作（打开详情 / 播放 / 复制 / 收藏）
# ============================================================


def open_detail(movie, path=None):
    """打开影片详情：登记后台抓取并在给定导航栈内 push 详情页。

    movie: 必含 code / img / link；path 缺省用影片 tab 的导航栈。
    上次已抓过同一番号、或后台已抓完但用户已返回的，直接复用数据秒开，
    不再发请求。
    """
    log("open_detail: " + movie["link"])
    global DETAIL_OPEN_AT, DETAIL_PATH
    thumb = movie.get("img") or ""
    if state.detail_thumb != thumb:
        state.detail_thumb = thumb
    # 避免点击详情时无条件写入多个 State 字段，减少 iOS 上的重复 body 重建。
    if state.panel or state.panel_title or state.play or state.status:
        state.panel = ""
        state.panel_title = ""
        state.play = ""
        state.status = ""

    link = movie["link"]
    ready = take_ready(link)
    cur = state.detail
    need_fetch = False
    if ready:
        state.detail = ready
    elif (cur and cur.get("link") == link
          and not cur.get("_loading") and not cur.get("error")):
        state.detail = cur
    else:
        state.detail = {
            "_loading": True,
            "code": movie["code"],
            "cover": movie["img"],
            "name": movie.get("title", ""),
            "link": link,
        }
        need_fetch = True
    # 详情页在栈中，后台提交可以放心触发刷新；返回后 on_disappear 会复位。
    state.detail_open = True
    DETAIL_OPEN_AT = time.time()
    if path is None:
        path = PATH_BROWSE
    # 记住详情属于哪个栈：之后详情内的筛选/大图 push/pop 都只操作这个栈，
    # 与全局 ACTIVE_PATH、当前 tab 完全解耦，避免跨 tab 乱跳
    DETAIL_PATH = path
    note_nav_action()
    path.append({"tag": "detail"})
    # 先完成 iOS 导航转场，再启动网络线程，避免点击时被请求初始化拖慢。
    if need_fetch:
        request_detail(link)

def on_detail_closed():
    """详情页被返回/关闭：复位标志 + 开启转场静默窗，后台提交转为静默。"""
    state.detail_open = False
    note_nav_action()

def clear_panel():
    """关闭当前播放器。"""
    state.panel = ""
    state.panel_title = ""
    state.play = ""

def open_senplayer():
    """完整视频链接交给 SenPlayer 播放。"""
    url = state.panel or ""
    if not url:
        state.status = "请先播放完整视频"
        state.reload += 1
        return
    code = (state.detail or {}).get("code", "")
    target = ("SenPlayer://x-callback-url/play?url=" + quote(url, safe="") +
              "&name=" + quote(code, safe="") + "&User-Agent=SenPlayer")
    ok = shortcuts.open_url(target)
    if ok:
        # 已交给外部 SenPlayer 播放，关闭本地播放面板以停止本地播放
        state.panel = ""
        state.panel_title = ""
        state.play = ""
        state.status = "已跳转 SenPlayer"
    else:
        state.status = "打开失败"
    state.reload += 1

def copy_video_link():
    """复制当前（完整视频）链接。"""
    if state.panel:
        clipboard.set(state.panel)
        state.status = "链接已复制"
        state.reload += 1
    else:
        state.status = "请先播放完整视频"
        state.reload += 1

def play_trailer():
    """播放 Fanza 预告。"""
    if state.detail and state.detail.get("trailer"):
        play_url(state.detail["trailer"], "Fanza 预告", source="预告")

def _spawn_play_fetch(task, fetching_msg, fail_msg):
    """启动后台抓取任务；成功后 set_play_request，失败 set_play_error。

    task: 无参函数，返回 (url, title, source) 或 None。
    """
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
    """播放 Jable 7 秒预览。"""
    code = state.detail.get("code") if state.detail else ""
    if not code:
        return

    def _fetch():
        preview, _ = fetch_jable(code)
        return (preview, "Jable 预览", "预览") if preview else None

    _spawn_play_fetch(_fetch, "正在获取 Jable 预览...", "Jable 无预览")

def play_jable():
    """播放 Jable 完整视频（m3u8）。"""
    code = state.detail.get("code") if state.detail else ""
    if not code:
        return

    def _fetch():
        _, full = fetch_jable(code)
        return (full, "Jable 完整视频", "完整视频") if full else None

    _spawn_play_fetch(_fetch, "正在获取 Jable 完整视频...", "Jable 未找到完整视频")

def show_sample(link, path=None):
    """点击样片查看大图（在详情所在 NavigationStack 内 push，保持详情滚动位置）。"""
    if path is None:
        path = DETAIL_PATH   # 样片只从详情进入：用它自己的栈，不依赖全局活跃栈
    state.sample_preview = link
    note_nav_action()
    path.append({"tag": "sample"})

def close_sample():
    """关闭大图视图并回到详情。"""
    ap = DETAIL_PATH
    if ap:
        note_nav_action()
        ap.pop(count=1)
    state.sample_preview = ""

def copy_code():
    """复制当前番号。"""
    if state.detail:
        code = state.detail["code"]
        clipboard.set(code)
        state.status = "番号 " + code + " 已复制"
        state.reload += 1

def toggle_fav():
    """切换当前详情的收藏状态并落盘。"""
    d = state.detail
    if not d:
        return
    # 传入打开详情时固化的列表缩略图，收藏记录即持久缓存封面，无需再解析
    toggle_bookmark(d, img=state.detail_thumb or "")
    state.reload += 1


# ============================================================
#  UI 层：通用单元格与网格
# ============================================================


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
        open_detail(m, path)

    return appui.Button(
        action=open,
        content=appui.VStack([
            appui.AsyncImage(url=img_src(m["img"]))
                .frame(height=165).clipped()
                .background("secondarySystemBackground", corner_radius=6),
            appui.Text(m["code"]).font("caption").line_limit(1),
            appui.Text(m["date"]).font("caption2").foreground_color("secondaryLabel"),
        ], spacing=3),
    ).button_style("plain").id(_cell_id(m))

def movie_grid(items, on_more, path=None):
    """统一的影片封面网格（各 tab / 子作品列表共用外观）。"""
    if path is None:
        path = PATH_BROWSE
    return appui.ScrollView(
        appui.VStack([
            appui.LazyVGrid(
                columns=[appui.adaptive(minimum=104)],
                spacing=10,
                content=[movie_cell(m, path) for m in items],
            ),
            appui.Button("加载更多", action=on_more),
        ], spacing=12).padding()
    )

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


# ============================================================
#  UI 层：子作品列表（女优作品 / 分类作品 / 详情筛选）
# ============================================================


def cur_base():
    """站点基础路径。"""
    return BASE + "/"

def sub_url(page):
    """子作品列表分页 URL。"""
    return fill_base(state.sub_link) + ("/" if not state.sub_link.endswith("/") else "") + str(page)

def load_sub_first():
    """重新加载子作品列表第一页（后台抓取，不阻塞点击）。"""
    state.sub_page = 1
    state.sub_loading = True
    request_page(sub_url(1), "sub", all_flag=state.all_flag)

def load_sub_more():
    """追加子作品列表下一页（后台抓取）。"""
    if len(state.sub_movies) >= MAX_LIST_ITEMS:
        return
    state.sub_loading = True
    request_page(sub_url(state.sub_page + 1), "sub", append=True,
                         all_flag=state.all_flag)

def open_sub(path, link, title):
    """在指定导航栈内 push 一个子作品列表。"""
    state.sub_title = title
    state.sub_link = link
    SUB_PATH = path
    note_nav_action()
    load_sub_first()
    path.append({"tag": "sub"})

def open_cat(link, title):
    """分类作品列表：在分类 tab 自己的栈内 push 子列表。"""
    open_sub(PATH_CAT, link, title)

def open_filter(link, title):
    """从详情页按发片商/制作商/系列/导演/类别进入筛选后的作品列表。"""
    if not link:
        state.status = "无该字段链接"
        state.reload += 1
        return
    # 只在详情自己的栈内 push，绝不依赖全局活跃栈（跨 tab 时会推错栈）
    open_sub(DETAIL_PATH, link, title)

def sub_destination(data):
    """子作品列表页（女优作品、分类作品共用外观）。"""
    return movie_grid(state.sub_movies, load_sub_more, SUB_PATH) \
        .navigation_title(state.sub_title) \
        .refreshable(action=load_sub_first)


# ============================================================
#  UI 层：详情视图与大图视图
# ============================================================


def detail_destination(data):
    """路由：详情页。挂 on_disappear 感知用户离开，防止后台提交撞上返回转场。"""
    return detail_view().on_disappear(action=on_detail_closed)

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
    d = state.detail
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

    fav_title = "已收藏" if in_fav(d["code"]) else "收藏"
    fav_style = "bordered_prominent" if in_fav(d["code"]) else "bordered"

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
        appui.Button(fav_title, action=toggle_fav)
            .button_style(fav_style)
            .frame(max_width=appui.infinity),
        appui.Button("复制番号", action=copy_code)
            .button_style("bordered")
            .frame(max_width=appui.infinity),
    ], spacing=8)

    def equal_btn(label, action, source=None, prominent_when_active=True):
        """等宽按钮：文字不折行（自动缩字号），同排均分宽度。"""
        style = "bordered"
        if source is not None and prominent_when_active and state.play == source:
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
        equal_btn("预览", play_jable_preview, "预览"),
        equal_btn("预告", play_trailer, "预告"),
        equal_btn("完整视频", play_jable, "完整视频"),
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

    if state.panel:
        # 完整视频下方显示 SenPlayer / 复制链接 / 关闭；预览、预告只显示关闭
        op_buttons = [eq_btn("关闭", clear_panel)]
        if state.play == "完整视频":
            op_buttons = [
                eq_btn("SenPlayer", open_senplayer),
                eq_btn("复制链接", copy_video_link),
                eq_btn("关闭", clear_panel),
            ]
        panel_rows = [
            appui.Text(state.panel_title).font("caption").foreground_color("secondaryLabel"),
            appui.VideoPlayer(url=state.panel, autoplay=True).frame(height=220),
            appui.HStack(op_buttons, spacing=8),
        ]
        top = appui.VStack([top, *panel_rows], spacing=8)
    if state.status:
        top = appui.VStack([
            top,
            appui.Text(state.status).font("caption").foreground_color("secondaryLabel"),
        ], spacing=4)

    def filter_row(value, link):
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
                content=[sample_cell(s) for s in d["samples"]],
            )
        ], header="样片(点击看大图)"))
    if d["magnets"]:
        sections.append(appui.Section(
            [magnet_row(m) for m in d["magnets"]], header="磁链"))

    return appui.List([
        appui.Section([top.padding()]),
        *sections,
    ]).navigation_title(d["code"])

def sample_preview_view():
    """大图查看页（已由详情所在 NavigationStack push，不再嵌套新的 NavigationStack）。"""
    return appui.VStack([
        appui.AsyncImage(url=img_src(state.sample_preview), content_mode="fit")
            .frame(max_height=appui.infinity)
            .padding(),
        appui.Button("关闭", action=close_sample),
    ], spacing=12).navigation_title("查看大图")


# ============================================================
#  UI 层：影片 tab（首页 + 搜索框，搜索与首页共用结果列表）
# ============================================================


def movie_url(page):
    """首页/搜索共用的分页地址组装。"""
    h = cur_base()
    if state.mode == "search":
        return h + "search/" + quote(state.keyword) + "/" + str(page)
    if state.mode == "cat":
        return fill_base(state.cat_link) + "/" + str(page)
    return h + "page/" + str(page)

def load_first():
    """加载第一页（后台抓取，不阻塞点击）。"""
    state.movies_page = 1
    state.browse_loading = True
    request_page(movie_url(1), "browse", all_flag=state.all_flag)

def load_more():
    """追加下一页（后台抓取）。"""
    if len(state.movies) >= MAX_LIST_ITEMS:
        return
    state.browse_loading = True
    request_page(movie_url(state.movies_page + 1), "browse",
                 append=True, all_flag=state.all_flag)

def set_home_kw(v):
    """首页搜索框输入回调：写入搜索关键词。"""
    state.keyword = v

def do_search():
    """在首页发起搜索：进入 search 模式并加载第一页（结果渲染在首页同一网格）。"""
    kw = norm_keyword(state.keyword)
    state.keyword = kw
    if not kw:
        clear_search()
        return
    state.mode = "search"
    state.movies = []
    state.reload += 1
    load_first()

def clear_search():
    """退出搜索，回到首页影片列表。"""
    state.keyword = ""
    state.mode = "home"
    state.movies = []
    state.reload += 1
    load_first()

def browse_page():
    """影片 tab 根页面：版本号下方放搜索框；搜索与首页共用下方影片网格。"""
    field = (appui.TextField("番号或演员", text=state.keyword, on_change=set_home_kw)
             .text_field_style("rounded_border")
             .on_submit(do_search))
    buttons = [appui.Button("搜索", action=do_search).button_style("bordered_prominent")]
    if state.mode == "search":
        buttons.append(appui.Button("取消", action=clear_search).button_style("bordered"))
    search_row = appui.HStack([field, *buttons], spacing=8)

    content = [app_header(), search_row]
    if state.mode == "search" and not state.movies and not state.browse_loading:
        content.append(appui.Text("未找到结果").foreground_color("secondaryLabel"))
    if state.movies:
        content.append(appui.LazyVGrid(
            columns=[appui.adaptive(minimum=104)],
            spacing=10,
            content=[movie_cell(m, PATH_BROWSE) for m in state.movies],
        ))
        content.append(appui.Button("加载更多", action=load_more))
    return appui.NavigationStack(
        appui.ScrollView(
            appui.VStack(content, spacing=12).padding()
        )
        .refreshable(action=load_first)
        .navigation_title(APP_TITLE),
        path=PATH_BROWSE,
        destinations={"detail": detail_destination,
                      "sample": sample_destination,
                      "sub": sub_destination},
    ).id("browse")


# ============================================================
#  UI 层：女优 tab
# ============================================================


# 首次进入 tab 才预加载（避免启动时重复请求）
ACTRESS_LOADED = False

def actress_cell(a):
    """女优头像单元格（点击进入作品列表）。"""
    def open():
        open_sub(PATH_ACT, a["link"], a["name"])

    return appui.Button(
        action=open,
        content=appui.VStack([
            appui.AsyncImage(url=img_src(a["img"]))
                .frame(height=130).clipped()
                .background("secondarySystemBackground", corner_radius=6),
            appui.Text(a["name"]).font("caption").line_limit(1),
        ], spacing=3),
    ).button_style("plain").id(a.get("link") or a.get("name") or "")

def actress_url(page):
    """女优列表分页 URL。"""
    return cur_base().rstrip("/") + "/actresses/" + str(page)

def load_actresses():
    """重新加载女优第一页（后台抓取，不阻塞点击）。"""
    state.actress_page = 1
    state.actress_loading = True
    request_page(actress_url(1), "actress")

def load_actresses_once():
    """女优 tab 首次出现时预加载第一页。"""
    global ACTRESS_LOADED
    if ACTRESS_LOADED:
        return
    ACTRESS_LOADED = True
    load_actresses()

def load_actresses_more():
    """追加女优下一页（后台抓取，不阻塞点击）。"""
    if len(state.actresses) >= MAX_LIST_ITEMS:
        return
    state.actress_loading = True
    request_page(actress_url(state.actress_page + 1), "actress", append=True)

def actress_page():
    """女优 tab 根页面。"""
    return appui.NavigationStack(
        appui.ScrollView(
            appui.VStack([
                app_header(),
                appui.LazyVGrid(
                    columns=[appui.adaptive(minimum=100)],
                    spacing=10,
                    content=[actress_cell(a) for a in state.actresses],
                ),
                appui.Button("加载更多", action=load_actresses_more),
            ], spacing=10).padding()
        ).refreshable(action=load_actresses)
        .navigation_title(APP_TITLE),
        path=PATH_ACT,
        destinations={"detail": detail_destination,
                      "sample": sample_destination,
                      "sub": sub_destination},
    ).on_appear(action=load_actresses_once)


# ============================================================
#  UI 层：分类 tab
# ============================================================


# 首次进入 tab 才预加载
GENRE_LOADED = False

def genre_cell(c):
    """单个分类按钮。"""
    def open():
        open_cat(c["link"], c["name"])

    return appui.Button(content=appui.Label(c["name"], system_image="tag"), action=open)

def load_genres():
    """重新加载全部分类（后台抓取，不阻塞点击）。"""
    request_page("", "genre")

def load_genres_once():
    """分类 tab 首次出现时预加载。"""
    global GENRE_LOADED
    if GENRE_LOADED:
        return
    GENRE_LOADED = True
    load_genres()

def genre_page():
    """分类 tab 根页面。"""
    # 按屏幕宽度自适应列数（每列最小宽度约 100pt，一行可多列显示）
    sections = [app_header()]
    for group in state.genres:
        parts = [appui.Text(group["tag"]).font("headline").padding(top=10)]
        parts.append(appui.LazyVGrid(
            columns=[appui.adaptive(minimum=100)],
            spacing=8,
            content=[genre_cell(c) for c in group["cats"]],
        ))
        sections.append(appui.VStack(parts, spacing=8))
    return appui.NavigationStack(
        appui.ScrollView(
            appui.VStack(sections, spacing=4).padding()
        ).refreshable(action=load_genres).navigation_title(APP_TITLE),
        path=PATH_CAT,
        destinations={"detail": detail_destination,
                      "sample": sample_destination,
                      "sub": sub_destination},
    ).on_appear(action=load_genres_once)


# ============================================================
#  UI 层：收藏 tab
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
_MOVIE_WORKERS = 2                # 低频补全：低并发，避免洪泛触发限流
_MOVIE_OK_SLEEP = 0.7           # 每次成功解析后稍作停顿，进一步限流
_MOVIE_RETRY_SLEEP = 0.6       # 解析失败重试前的退避，避免短时间内连发请求触发限流
_MOVIE_PAUSE_UNTIL = 0.0
_MOVIE_STARTED = False
_MOVIE_UNSAVED = 0
# 解析失败被放弃的番号 -> 放弃时刻。冷却期间进收藏 tab 不再重搜，
# 避免"每次进入都对一批搜不到的番号重复请求"导致限流/卡顿。
_MOVIE_GIVEUP = {}
_MOVIE_GIVEUP_COOL = 600   # 秒，冷却后允许再试一次

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
            log("shelf movie fetch err: " + str(e))
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
                log("shelf image cache err: " + str(e))
            time.sleep(_MOVIE_OK_SLEEP)   # 成功也限流，避免连续请求
        elif retry_sleep:
            time.sleep(retry_sleep)   # 失败退避，缓解并发触发站点限流

def _start_movie_workers():
    global _MOVIE_STARTED
    if _MOVIE_STARTED:
        return
    _MOVIE_STARTED = True
    for _ in range(_MOVIE_WORKERS):
        threading.Thread(target=_movie_worker, daemon=True).start()

def pause_shelf_movies():
    global _MOVIE_PAUSE_UNTIL
    with _MOVIE_LOCK:
        _MOVIE_PAUSE_UNTIL = time.time() + 3.0

def load_shelf_movies():
    global _MOVIE_PAUSE_UNTIL
    _start_movie_workers()
    cached_images = []
    with _MOVIE_LOCK:
        _MOVIE_PAUSE_UNTIL = 0.0
        for item in SHELF["fav"][:MAX_LIST_ITEMS]:
            code = str(item.get("code") or "").strip().upper()
            # 已固化在收藏记录里的封面（新收藏，零请求）优先直接下载
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

def shelf_cell_item(item):
    """收藏封面单元格：与其他 tab 完全一致的封面外观（movie_cell），
    额外提供长按/右键菜单移除。"""
    code = str(item.get("code") or "").strip().upper()
    with _MOVIE_LOCK:
        resolved = _MOVIES.get(code, {})
    movie = {
        "code": code,
        "img": item.get("img") or resolved.get("img", ""),
        "date": item.get("fav_time") or "",
        "link": resolved.get("link") or BASE + "/" + quote(code),
    }

    def unfav():
        remove_fav(item.get("code"))
        save_shelf()
        state.reload += 1

    # 复用统一封面单元格，再叠加移除菜单与稳定身份
    return movie_cell(
        movie, PATH_SHELF, before_open=pause_shelf_movies).context_menu(content=[
        appui.Button("从收藏移除", action=unfav, role="destructive"),
    ]).id(item.get("code") or "")

def shelf_page():
    """收藏 tab 根页面。"""
    def fav_rows():
        # 按收藏时间从新到旧展示
        items = sorted(SHELF["fav"],
                       key=lambda x: x.get("fav_time", ""),
                       reverse=True)[:MAX_LIST_ITEMS]
        return [shelf_cell_item(item) for item in items]

    return appui.NavigationStack(
        appui.ScrollView(
            appui.VStack([
                app_header(),
                appui.Text("收藏 " + str(fav_count())).font("footnote").foreground_color("secondaryLabel"),
                appui.LazyVGrid(
                    columns=[appui.adaptive(minimum=104)],
                    spacing=10,
                    content=fav_rows(),
                ),
            ], spacing=10).padding()
        )
        .navigation_title(APP_TITLE),
        path=PATH_SHELF,
        destinations={"detail": detail_destination,
                      "sample": sample_destination},
    ).on_appear(action=load_shelf_movies)


def start():
    """冷启动：初始化后台线程并复位到主页。"""
    init_background()
    reset_pending()
    # 清掉上次会话的搜索/分类/详情/播放状态
    state.tab = 0
    state.mode = "home"
    state.keyword = ""
    state.cat_link = ""
    state.detail = None
    state.detail_open = False
    state.panel = ""
    state.panel_title = ""
    state.play = ""
    state.status = ""
    state.sample_preview = ""
    state.movies_page = 1
    state.actress_page = 1
    state.sub_movies = []
    state.browse_loading = False
    state.sub_loading = False
    state.actress_loading = False
    # 各 tab 导航栈回到根
    PATH_BROWSE.pop_to_root()
    PATH_ACT.pop_to_root()
    PATH_CAT.pop_to_root()
    PATH_SHELF.pop_to_root()
    load_first()

def make_body():
    """组装四个 tab。"""
    return appui.TabView(
        tabs=[
            appui.Tab("影片", system_image="play.rectangle", content=browse_page(), tag=0),
            appui.Tab("女优", system_image="person.2", content=actress_page(), tag=1),
            appui.Tab("分类", system_image="tag", content=genre_page(), tag=2),
            appui.Tab("收藏", system_image="star", content=shelf_page(), tag=3),
        ],
        selection=state.bind.tab,
    )

start()

def body():
    return make_body()

appui.run(body, state=state, presentation="fullscreen_with_close")
