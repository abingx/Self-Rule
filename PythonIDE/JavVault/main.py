# -*- coding: utf-8 -*-
# ============================================================
#  JavVault · PythonIDE AppUI
#  数据来源: https://www.javbus.com
#
#  结构
#   ├─ 影片 tab：通用展示函数（封面网格 + 翻页），筛选条件随位置变化
#   ├─ 女优 / 类型 / 收藏 tab：同一套通用展示，只是数据源与筛选条件不同
#   ├─ 设置 tab：播放设置与关于
#   └─ 播放：TabView 底部常驻条 + 系统 sheet 展开完整面板（不占独立 tab）
#
#  数据
#   ├─ 设置：storage.get_json / set_json
#   ├─ 收藏：database.collection（按记录增删，顺序号 seq 保证跨启动稳定）
#   └─ 图片：自建磁盘缓存 + 后台下载队列
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
import database
import network
import shortcuts
import storage


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
    """从 miniapp.json 读取版本号（清单是唯一版本来源，设置页与之一致）。"""
    try:
        p = os.path.join(os.getcwd(), "miniapp.json")
        with open(p, "r", encoding="utf-8") as f:
            return str(json.load(f).get("version", "1.0"))
    except Exception:
        return "1.0"

APP_TITLE = "JavVault"
APP_VERSION = _app_version()

# 详情页封面宽高比（JavBus 封面标准比例 400x560）。
# 配合 content_mode="fill" 让封面撑满整个容器，上下不留空白。
COVER_RATIO = 5 / 7
# 女优头像宽高比（比封面矮：人脸裁切更自然，且 4 行头像可铺满可视高度）。
ACTRESS_RATIO = 5 / 6

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
    if not ensure_image_dir():
        return
    d = _image_dir()
    entries = []
    total = 0
    try:
        # scandir：一次遍历即可拿到 dir entry（含 stat），比 listdir+stat 少一轮系统调用
        with os.scandir(d) as it:
            for entry in it:
                try:
                    info = entry.stat()
                except Exception:
                    continue        # 扫描期间被删 / 无权限：跳过
                entries.append((info.st_mtime, info.st_size, entry.path))
                total += info.st_size
    except Exception as e:
        log("cache scan err: " + str(e))
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
def _build_placeholder():
    """生成一张纯色占位 PNG（8x12 浅灰），仅用 stdlib。"""
    w, h = 8, 12
    rgb = (0xED, 0xED, 0xEF)
    sig = b"\x89PNG\r\n\x1a\n"

    def _chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data +
                struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    idat = zlib.compress(raw, 9)
    return (sig + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))

# 模块加载时直接构造一次：结果是确定性的常量，
# 不再懒加载（避免多个下载 worker 同时判空重复构造）
_PLACEHOLDER = _build_placeholder()

def _placeholder_bytes():
    return _PLACEHOLDER

_IMAGE_DIR = os.path.join(tempfile.gettempdir(), "javbus_img")
_IMAGE_DIR_READY = False

def _image_dir():
    """图片缓存目录（纯路径拼接，不做任何系统调用）。

    本函数位于 _local_path 热路径上：渲染路径与下载 worker 每张图都会调用
    多次，之前每次调用都执行 os.makedirs（冗余 syscall）。目录创建收敛到
    ensure_image_dir()，只在真正写文件前调用一次。
    """
    return _IMAGE_DIR

def ensure_image_dir():
    """确保缓存目录存在；返回是否可用（写文件前调用）。"""
    global _IMAGE_DIR_READY
    if _IMAGE_DIR_READY and os.path.isdir(_IMAGE_DIR):
        return True
    try:
        os.makedirs(_IMAGE_DIR, exist_ok=True)
        _IMAGE_DIR_READY = True
    except Exception as e:
        log("image dir err: " + str(e))
    return _IMAGE_DIR_READY

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
            if not ensure_image_dir():
                return None
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            return True
    except Exception as e:
        log("download err " + url[:80] + " : " + str(e))
        return None

def request_img(src, priority=False):
    """登记一张图到后台下载队列。priority=True 插到队首。

    先查内存索引 _DOWNLOADED（零磁盘 I/O），未命中才做一次磁盘 stat——
    周期任务会对同一批图反复调用本函数（如收藏页可视窗口），
    stat 全部落在主线程会随浏览积累成卡顿。
    """
    if not src:
        return ""
    url = _to_abs(src)
    path = _local_path(url)
    with _LOCK:
        if url in _DOWNLOADED:
            _DOWNLOADED.move_to_end(url)
            return "file://" + path
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

_PREPARE_PENDING = set()   # 渲染期发现未准备的 src：登记后由主线程周期任务补准备
_PREPARE_FAILED = {}       # 写占位失败的 src -> 时刻：冷却期内不反复重试磁盘写入
_PREPARE_FAIL_COOLDOWN = 60.0

def _prepare_src(src):
    """数据层把一张图解析为本地 file:// 路径：文件缺失时写占位图并登记 LRU。

    只允许在渲染路径之外调用（worker 提交 / 主线程周期任务）——
    body() 内的 img_src 只查内存缓存，不再做任何磁盘 I/O。
    """
    if not src:
        return
    failed = _PREPARE_FAILED.get(src)
    if failed and time.time() - failed < _PREPARE_FAIL_COOLDOWN:
        return
    with _LOCK:
        hit = _SRC_CACHE.get(src)
        if hit:
            _SRC_CACHE.move_to_end(src)
            return
    url = _to_abs(src)
    path = _local_path(url)
    if not os.path.exists(path):
        try:
            if not ensure_image_dir():
                raise OSError("image dir unavailable")
            with open(path, "wb") as f:
                f.write(_placeholder_bytes())
        except Exception as e:
            log("prepare src err " + str(src)[:80] + " : " + str(e))
            _PREPARE_FAILED[src] = time.time()
            return
    _PREPARE_FAILED.pop(src, None)
    with _LOCK:
        if len(_SRC_CACHE) >= _SRC_CACHE_MAX:
            _SRC_CACHE.popitem(last=False)      # 逐出最旧一条，而不是整表清空
        _SRC_CACHE[src] = "file://" + path

def prepare_images(srcs):
    """批量预准备图片路径（worker 线程 / 数据提交阶段调用）。"""
    for src in srcs:
        _prepare_src(src or "")

def consume_prepare_pending():
    """主线程：补准备渲染期登记的图片；有新可用路径时安排一次重建。

    转场静默期内（快速切 tab / 导航推送）不做磁盘写入，等稳定后再补，
    避免主线程在动画过程中做文件 I/O。
    """
    if not _PREPARE_PENDING:
        return
    if not reload_allowed():
        return
    pending = list(_PREPARE_PENDING)
    _PREPARE_PENDING.clear()
    for src in pending:
        _prepare_src(src)
    if any(_SRC_CACHE.get(s) for s in pending):
        mark_views_dirty()      # 占位框 -> 真图需要一次重建

def img_src(src):
    """渲染路径专用：只查内存缓存（零磁盘 I/O）。

    未预准备的图返回空串，由调用方用同比例占位框渲染保持布局稳定；
    src 同时登记进 _PREPARE_PENDING，由主线程补准备后再重建填充。
    """
    if not src:
        return ""
    with _LOCK:
        hit = _SRC_CACHE.get(src)
        if hit:
            _SRC_CACHE.move_to_end(src)     # LRU：命中即续期
            return hit
    _PREPARE_PENDING.add(src)
    return ""

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


_STATE_FIELDS = dict(
    tab=0,
    keyword="",             # 搜索框内容（原生 .searchable 的绑定值）
    status="",
    detail=None,
    detail_open=False,      # 详情页是否仍在导航栈顶
    detail_thumb="",        # 打开详情时列表项自带的缩略图（收藏封面用）
    panel="",
    panel_title="",
    play="",                # 当前播放来源："" / 预览 / 预告 / 完整视频
    panel_open=False,       # 播放面板（sheet）是否展开
    src_preview="",         # 详情页预览链接（进入详情即并行预取，空表示还没取到）
    src_trailer="",         # 详情页预告链接
    src_video="",           # 详情页完整视频链接
    sample_index=0,         # 样片大图当前页（可左右滑动翻看）
    name_text="",           # 详情页标题的中文译文（空表示尚未翻译完成）
    title_trans=False,      # 标题是否已翻译成中文
    rating_text="",         # 详情页评分文本（JavDB）
    genre_group="全部",     # 类型 tab 当前选中的一级分类
    page_input="",          # 页码输入框内容（空 = 未在输入，显示当前页码）
    page_input_vid="",      # 页码输入当前归属的展示位
    page_editing=False,     # 页码输入框是否获得焦点（编辑中隐藏左右翻页按钮）
    reload=0,
)

# 官方 State 会把 JSON 兼容字段自动持久化并在冷启动时恢复：
# 运行期字段必须声明 transient——否则冷启动可能恢复出「半截详情 /
# 残留播放面板」，而且每次重建都会附带一次持久化写入。
# 只让 genre_group 跨启动保留（tab 由 start() 固定复位到影片页）。
_TRANSIENT_FIELDS = [k for k in _STATE_FIELDS if k != "genre_group"]

try:
    state = appui.State(transient=_TRANSIENT_FIELDS, **_STATE_FIELDS)
except TypeError as e:      # 运行时无 transient 参数：退化为默认构造
    log("state transient unsupported: " + str(e))
    state = appui.State(**_STATE_FIELDS)

def _batch_state(**updates):
    """一次动作改多个字段只触发一次重建（官方 batch_update）。

    逐字段赋值会各自触发一次整树重建——例如打开详情原来要连写约
    十个字段（≈十次全量重建），是点击卡顿的主因之一。运行时若无
    该 API 则退化为逐字段写入（行为不变，仅少了合并优化）。
    """
    if hasattr(state, "batch_update"):
        state.batch_update(**updates)
    else:
        for key, value in updates.items():
            setattr(state, key, value)

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


SETTINGS_KEY = "javvault.settings"
# 旧版本地设置文件（一次性迁移用，迁移后由 storage 托管）
LEGACY_SET_FILE = os.path.join(os.getcwd(), "settings.json")

# 每页项数不再提供设置项：按界面实际尺寸动态计算
# （在不超出「上一页 / 第X页 / 下一页」分页条的前提下取最大条目数，
#   图片尺寸不变，见 compute_page_size / make_grid_observer）。
DEFAULT_SETTINGS = {
    "player": "SenPlayer",    # 外部播放器
    "mute": True,             # 视频播放是否默认静音
}

def _load_legacy_settings():
    """读取旧版本地 settings.json（一次性迁移用）；缺失/损坏返回 None。"""
    try:
        if os.path.exists(LEGACY_SET_FILE):
            with open(LEGACY_SET_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                return saved
    except Exception as e:
        log("legacy settings err: " + str(e))
    return None

def load_settings():
    """读取设置；缺失/损坏时回退默认值（storage 内部已处理解析兜底）。"""
    data = dict(DEFAULT_SETTINGS)
    saved = None
    try:
        saved = storage.get_json(SETTINGS_KEY, None)
        if saved is None:
            # 首次运行新版本：把旧版本地文件迁移进 storage
            saved = _load_legacy_settings()
            if saved is not None:
                storage.set_json(SETTINGS_KEY, saved)
    except Exception as e:
        log("load_settings err: " + str(e))
        saved = None
    if isinstance(saved, dict):
        for k in data:
            if k in saved:
                data[k] = saved[k]
    if data["player"] not in EXTERNAL_PLAYERS:
        data["player"] = DEFAULT_SETTINGS["player"]
    data["mute"] = bool(data["mute"])
    return data

def save_settings():
    try:
        storage.set_json(SETTINGS_KEY, SETTINGS)
    except Exception as e:
        log("save_settings err: " + str(e))

SETTINGS = load_settings()

# ------------------------------------------------------------------
#  底部固定分页条：GeometryReader 实测可用高度（按 tab 隔离）
# ------------------------------------------------------------------
# 影片 / 女优 / 收藏三个 tab 根页各包一层 GeometryReader。
# 测量值必须按 tab 分别记录：不同 tab 的内容高度不同（搜索栏 / 网格行数
# 差异），共用一个全局值会让「切 tab」触发别的 tab 重算 → 整树重建反复
# 发生、页码被连锁重置（即「切 tab 闪烁 + 页码回第一页」的根因）。
_GRID_GEOMETRY_BY_KIND = {"movie": {"w": 0.0, "h": 0.0},
                          "actress": {"w": 0.0, "h": 0.0},
                          "fav": {"w": 0.0, "h": 0.0}}
PAGE_H_PAD = 16              # 展示内容左右内边距（VStack .padding()）

# ------------------------------------------------------------------
#  动态每页项数：GeometryReader 实测可用区域，按 tab 分别计算
# ------------------------------------------------------------------
# 规则：在不超出「上一页 / 第X页 / 下一页」分页条的前提下，
# 按各 tab 的可视高度取可容纳的最大行数（行数向下取整），
# 图片尺寸保持不变（列数与 adaptive(minimum=GRID_MIN_COLUMN) 一致）。
_GRID_PAGE_SIZE = {"movie": 0, "actress": 0, "fav": 0}   # 各 tab 生效的每页项数
# GeometryReader 回调防抖：tab 首次出现时 iOS 往往连续回调多次（安全区 /
# Tab 栏高度未稳定的过渡尺寸 → 最终尺寸），行数每次变化都立即重建会让
# 网格连续抖动（先按兜底值撑满、被砍掉一行、又补回来）。回调只登记待
# 应用值，尺寸停止变化该时长后由 _sync_dirty 统一应用一次。
_GEOM_STABLE_DELAY = 0.3
_PENDING_GEOM = {}       # kind -> {"size": n, "at": 登记时刻}
PAGE_V_PAD = 16              # 展示内容上下内边距（VStack .padding()）
PAGER_ROW_H = 56             # 分页条自身高度（按钮 min_height 44 + 上下 padding 12）
# 分页条以底部安全区插肩（safeAreaInset）钉在底部：SwiftUI 原生键盘
# 避让自动让它贴紧键盘，无需跟踪键盘状态或手动重建；网格可用高度的
# 计算只需扣除插肩条自身高度（PAGER_ROW_H）。
# 各 tab 顶部工具行高度（含与网格的间距）：影片=0（搜索栏已改为原生
# searchable 上移导航栏，不再占据滚动内容顶部），收藏=「共X部」，女优=无
TOP_TOOL_H_BY_KIND = {"movie": 0, "actress": 0, "fav": 48}
# 未完成首次测量时的兜底每页项数（与旧设置默认一致）
FALLBACK_PAGE_SIZE = {"movie": 9, "actress": 12, "fav": 9}
RATIO_BY_KIND = {"movie": COVER_RATIO, "actress": ACTRESS_RATIO, "fav": COVER_RATIO}

def make_grid_observer(kind):
    """生成某个 tab 的 GeometryReader 回调：只记录并重算本 tab 的测量值。

    回调契约（官方 stub）：回调收到 {'width': float, 'height': float} 字典；
    同时兼容旧的「单参数 "宽度,高度" 字符串」与「两个浮点位置参数」两种形态，
    避免运行时形态差异导致测量静默失效（失效时每页项数永远停在兜底值）。

    各 tab 的测量相互隔离：切换 tab / 某个 tab 内容变化，都不会触发其他
    tab 的重算与整树重建（全局单值会在 tab 之间来回乒乓，导致切换标签
    时反复重建、页码被连锁重置回第一页）。

    每页项数变化时不清空数据池、不重置页码：数据池是连续流，切片长度
    变化不影响已翻到的位置；只有当前页起点落到已回收区时才把页码收敛
    到仍能覆盖的页（而不是第 1 页）。

    行数变化也不立即重建：tab 首次出现时 iOS 常连续回调多次（过渡尺寸
    → 最终尺寸），回调只登记待应用值，由 _sync_dirty 在测量停止变化
    _GEOM_STABLE_DELAY 后统一应用一次，中间过渡尺寸不产生中间渲染。

    键盘避让守卫：宽度不变而高度变小是页码输入框弹出键盘挤压容器
    （键盘安全区）所致——分页条由底部安全区插肩原生避让，自动贴紧
    键盘，这里保持测量值与每页项数不动即可，整个键盘周期零重建。
    """
    def remember(geometry, height=None):
        try:
            if isinstance(geometry, dict):
                # 官方契约：{'width': float, 'height': float}
                w = float(geometry.get("width", 0.0))
                h = float(geometry.get("height", 0.0))
            elif height is None:
                w_str, h_str = str(geometry).split(",")
                w, h = float(w_str), float(h_str)
            else:
                w, h = float(geometry), float(height)
        except Exception:
            return
        if w <= 0 or h <= 0:
            return
        g = _GRID_GEOMETRY_BY_KIND[kind]
        same_w = abs(w - g["w"]) < 1
        if same_w and abs(h - g["h"]) < 1:
            return               # 同一帧重复回调：忽略
        # 键盘避让守卫：宽度不变而高度变小，是页码输入框弹出键盘后
        # 键盘安全区挤压容器所致。分页条已改用底部安全区插肩，原生
        # 键盘避让自动让它贴紧键盘——这里保持测量值与每页项数不动
        # （网格内容不被裁剪），整个键盘弹出/收起周期零重建。
        if same_w and h < g["h"]:
            # 例外：tab 内容仅选中时挂载，GeometryReader 重新挂载时
            # iOS 常先回调一个偏大的过渡尺寸、再回调最终尺寸；最终
            # 尺寸若被键盘守卫吞掉，测量会停在过渡值——每页按偏大的
            # 高度多算一行，内容越过分页条出现滚动。判定：最近接受
            # 过一次「增长」，且回落值与增长前的稳定高度一致（或此
            # 前从未测量过）→ 属过渡回落而非键盘，按真实尺寸修正并
            # 撤销待应用值；否则维持键盘守卫（忽略）。
            if time.time() - g.get("grown_at", 0.0) < 2.0:
                prev = g.get("prev_h", None)
                if prev is None or abs(h - prev) < 10:
                    g["h"] = h
                    g["grown_at"] = 0.0
                    size = compute_page_size(kind)
                    effective = (_GRID_PAGE_SIZE.get(kind, 0)
                                 or FALLBACK_PAGE_SIZE.get(kind, 9))
                    if size == effective:
                        _GRID_PAGE_SIZE[kind] = size
                        _PENDING_GEOM.pop(kind, None)
                    elif size > 0:
                        _PENDING_GEOM[kind] = {"size": size, "at": time.time()}
            return
        # 接受新尺寸。宽度不变而高度变大（重挂载的过渡尺寸）时记录
        # 「增长前的稳定高度」，供上面的过渡回落判定；宽度变化（旋转
        # /首次测量）时重置或清空基准。
        if same_w:
            g["prev_h"] = g["h"]
            g["grown_at"] = time.time()
        elif g["w"] > 0:
            g["grown_at"] = 0.0        # 真实宽度变化：旧基准失效
        else:
            g["prev_h"] = None         # 首次测量：无基准，回落即采信
            g["grown_at"] = time.time()
        g["w"] = w
        g["h"] = h
        size = compute_page_size(kind)
        if size <= 0:
            return
        # 与当前生效的每页项数比较（未测量时生效的是兜底值）：一致说明
        # 网格行数与当前渲染一致——首次测量结果与兜底一致时同样适用——
        # 只记录尺寸，不重建。
        effective = _GRID_PAGE_SIZE.get(kind, 0) or FALLBACK_PAGE_SIZE.get(kind, 9)
        if size == effective:
            _GRID_PAGE_SIZE[kind] = size
            _PENDING_GEOM.pop(kind, None)   # 抖回原值：撤销待应用值
            return
        # 行数变化：不立即重建。iOS 在 tab 首次出现时往往连续回调多次
        # （过渡尺寸 → 最终尺寸），立即重建会让网格行数连续抖动（先按
        # 兜底值撑满、被砍掉一行、又补回来）。这里只登记待应用值，由
        # _sync_dirty 在尺寸停止变化 _GEOM_STABLE_DELAY 后统一应用一次。
        _PENDING_GEOM[kind] = {"size": size, "at": time.time()}
    return remember

def _apply_pending_geometry(kind):
    """应用某 tab 稳定后的实测每页项数（页码收敛 + 预加载窗口补足）。"""
    size = _PENDING_GEOM[kind]["size"]
    _GRID_PAGE_SIZE[kind] = size
    for vid in list(VIEWS):
        if view_kind(vid) == "genre":
            continue           # 类型页无网格翻页，不受影响
        if page_size_key(view_kind(vid)) != kind:
            continue
        item = VIEWS[vid]
        with _VIEWS_LOCK:
            if item["pool"] and (item["page"] - 1) * size < item["base"]:
                item["page"] = max(1, item["base"] // size + 1)
        _pump(vid)             # 补足变长后的预加载窗口（缺失数据增量抓）

def page_size_key(kind):
    """展示位的 filter.kind -> 计算键（女优 / 收藏 / 其余都用影片）。"""
    if kind == "actress":
        return "actress"
    if kind == "fav":
        return "fav"
    return "movie"

def grid_column_count(kind="movie"):
    """按实测可用宽度算列数：与 adaptive(minimum=GRID_MIN_COLUMN) 的
    实际渲染一致（图片尺寸由此保持不变，计算只用于确定每页行数）。"""
    w = _GRID_GEOMETRY_BY_KIND.get(kind, {}).get("w", 0.0)
    if w <= 0:
        return 3                            # 未测量时的兜底
    grid_w = max(0.0, w - PAGE_H_PAD * 2)
    cols = int((grid_w + GRID_SPACING) // (GRID_MIN_COLUMN + GRID_SPACING))
    return max(2, cols)

def compute_page_size(kind):
    """某个 tab 的每页项数：在不超出分页条的前提下取最大值（列数 × 行数）。

    可用高度 = 本 tab 实测高 - 该 tab 顶部工具行(搜索栏 / 「共X部」)
               - 分页条区块 - 页面上下留白
    单元格高度按各 tab 的封面比例换算：影片 / 收藏 5:7，女优 5:6。
    行数向下取整，保证整页不越过分页条、无需滚动。
    """
    g = _GRID_GEOMETRY_BY_KIND.get(kind, {})
    w = g.get("w", 0.0)
    h = g.get("h", 0.0)
    if w <= 0 or h <= 0:
        return 0
    cols = grid_column_count(kind)
    grid_w = max(0.0, w - PAGE_H_PAD * 2)
    col_w = (grid_w - (cols - 1) * GRID_SPACING) / cols
    cell_h = col_w / RATIO_BY_KIND[kind]
    avail_h = (h - TOP_TOOL_H_BY_KIND.get(kind, 48)
               - PAGER_ROW_H - PAGE_V_PAD * 2)
    rows = int(avail_h // cell_h)
    return cols * max(1, rows)

def page_size(vid=None, kind=None):
    """每页项数：按所属 tab 的可视高度动态取可容纳的最大值。"""
    key = page_size_key(kind if kind else (view_kind(vid) if vid else "home"))
    size = _GRID_PAGE_SIZE.get(key, 0)
    if size > 0:
        return size
    return FALLBACK_PAGE_SIZE.get(key, 9)


# ============================================================
#  数据层：收藏持久化
# ============================================================


# 收藏按记录存储在官方 database 的 Collection 里（key = 番号）：
# 收藏/取消只 upsert/delete 单条记录，不再整份 JSON 重写磁盘，
# I/O 成本不随收藏总量增长。SHELF 是启动时载入的内存镜像，
# 列表渲染 / 排序 / 计数仍走内存，不写盘。
FAV_COL = database.collection("favorites")
# 旧版本地收藏文件（一次性迁移用，迁移后由 database 托管）
LEGACY_FAV_FILE = os.path.join(os.getcwd(), "favorites.json")

_FAV_SEQ = 0        # 收藏顺序号：单调递增，越大越新（同一天内的排序依据）

def _fav_sort_key(item):
    """排序键：(收藏日期, 收藏顺序号) 倒序。

    日期新的在前；同一天内顺序号大的在前——即新增的收藏始终在最上方，
    与旧 favorites.json「从上到下 = 从新到旧」的顺序完全一致。
    """
    return (str(item.get("fav_time") or item.get("date") or ""),
            int(item.get("seq") or 0))

def _norm_fav(item, seq=None):
    """规整一条收藏记录；缺番号的返回 None（无法成为收藏项）。"""
    if not isinstance(item, dict):
        return None
    code = str(item.get("code") or "").strip().upper()
    if not code:
        return None
    rec = {"code": code,
           "img": item.get("img") or "",
           # 去掉日期前后空格，避免字符串排序时被排到所有人后面
           "fav_time": str(item.get("fav_time") or "").strip()}
    order = item.get("seq", seq)
    if order is not None:
        try:
            rec["seq"] = int(order)
        except (TypeError, ValueError):
            pass
    return rec

def _load_legacy_favs():
    """读取旧版本地 favorites.json（一次性迁移用）；缺失/损坏返回 None。"""
    try:
        if os.path.exists(LEGACY_FAV_FILE):
            with open(LEGACY_FAV_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.pop("arc", None)
                data = data.get("fav")
            if isinstance(data, list):
                return data
    except Exception as e:
        log("legacy favorites err: " + str(e))
    return None

def load_shelf():
    """从 Collection 载入收藏（内存镜像 SHELF），并保证跨启动顺序稳定。

    顺序号 seq 的来源（按优先级）：
      1. 记录自身带的 seq（新版本写入的）；
      2. 旧版 favorites.json 的行号——旧文件「从上到下 = 从新到旧」，
         迁移时按行号赋 seq（顶部最大），与展示顺序一致；
      3. 都没有时退回数据库行序（updated_at desc，近期写入在前）。
    历史记录在首次载入时补写一次 seq，之后不再需要推断。
    """
    global _FAV_SEQ
    favs = []
    legacy = _load_legacy_favs() or []
    legacy_rank = {}
    for i, item in enumerate(legacy):
        rec = _norm_fav(item)
        if rec:
            legacy_rank.setdefault(rec["code"], i)   # 行号越小越新
    legacy_total = len(legacy)
    try:
        rows = FAV_COL.list(order_by="updated_at desc")
        if not rows:
            # 首次运行新版本：把旧版本地文件按「从上到下 = 从新到旧」写进 Collection
            rows = []
            for i, item in enumerate(legacy):
                rec = _norm_fav(item)
                if rec:
                    rec["seq"] = legacy_total - i
                    FAV_COL.upsert(rec["code"], rec)
                    rows.append(rec)
        for i, raw in enumerate(rows):      # updated_at desc：近期写入的在前
            rec = _norm_fav(raw)
            if not rec:
                continue
            if "seq" not in rec:
                rank = legacy_rank.get(rec["code"])
                rec["seq"] = (legacy_total - rank) if rank is not None \
                    else (len(rows) - i)
                try:
                    FAV_COL.upsert(rec["code"], rec)   # 补写一次，修正历史顺序
                except Exception as e:
                    log("fav reorder write err: " + str(e))
            favs.append(rec)
    except Exception as e:
        log("load_shelf err: " + str(e))
    favs.sort(key=_fav_sort_key, reverse=True)
    _FAV_SEQ = max([int(x.get("seq") or 0) for x in favs] or [0])
    return {"fav": favs}

SHELF = load_shelf()

# 收藏番号索引：in_fav 由「每个单元格线性扫描全部收藏」降为 O(1) 集合查询
_FAV_CODES = set()

# 收藏列表缓存：翻页窗口 / 周期任务 / 数据池重建都会调用 fav_items，
# 收藏记录未变动时直接复用，mark_fav_dirty 时失效
_FAV_ITEMS_CACHE = None

def _rebuild_fav_codes():
    _FAV_CODES.clear()
    for x in SHELF["fav"]:
        code = x.get("code")
        if code:
            _FAV_CODES.add(code)

_rebuild_fav_codes()

def in_fav(code):
    return code in _FAV_CODES

def now_time():
    return datetime.date.today().strftime("%Y-%m-%d")

_FAV_DIRTY = False

def mark_fav_dirty():
    """收藏有变动：收藏 tab 已加载的数据池需要重建。"""
    global _FAV_DIRTY, _FAV_ITEMS_CACHE
    _FAV_DIRTY = True
    _FAV_ITEMS_CACHE = None    # 收藏列表缓存同步失效

def add_fav(code, img=""):
    global _FAV_SEQ
    code = str(code or "").strip().upper()   # 与 _norm_fav 的键规整保持一致
    _FAV_SEQ += 1                            # 新收藏的顺序号最大 → 始终排最上方
    rec = {"code": code, "img": img, "fav_time": now_time(), "seq": _FAV_SEQ}
    SHELF["fav"].insert(0, rec)
    _FAV_CODES.add(code)
    try:
        FAV_COL.upsert(code, rec)      # 按记录写入，不整表重写
    except Exception as e:
        log("fav upsert err: " + str(e))
    mark_fav_dirty()

def remove_fav(code):
    code = str(code or "").strip().upper()   # 与 _norm_fav 的键规整保持一致
    SHELF["fav"] = [x for x in SHELF["fav"] if x.get("code") != code]
    _FAV_CODES.discard(code)
    try:
        FAV_COL.delete(code)           # 按记录删除，不整表重写
    except Exception as e:
        log("fav delete err: " + str(e))
    mark_fav_dirty()

def toggle_bookmark(d, img=""):
    code = d["code"]
    if in_fav(code):
        remove_fav(code)
    else:
        add_fav(code, img=img)


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
        if not ensure_image_dir():
            return      # 缓存文件与图片同目录
        tmp = _MOVIE_CACHE_FILE + "." + str(threading.get_ident()) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(movies, f, ensure_ascii=False)
        os.replace(tmp, _MOVIE_CACHE_FILE)
    except Exception as e:
        log("save movie cache err: " + str(e))

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
                _prepare_src(match.get("img") or "")
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
    prepare_images(cached_images)
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
_LINK_INFLIGHT_AT = {}  # 番号 -> 预取开始时刻（用于回收卡死/丢结果的任务）
_LINK_INFLIGHT_TTL = 120.0
_LINK_LEFT = {}         # seq -> 还差几路结果
# 计数必须与 _LINK_PENDING 分开：主线程每轮会把 _LINK_PENDING 取走清空并
# 提交已有结果，若把计数放在里面，第二路结果到达时会重新建档、永远收不了口，
# 导致该番号一直被认为「在途」而无法重新预取
_LINK_PENDING = {}      # seq -> {"code":..., "values":{...}}
_LINK_INFLIGHT_MAX = 3  # 预取并发上限：快速连点多个单元格时不再无限堆积任务
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
        now = time.time()
        rec["ts"] = now
        _LINK_CACHE[code] = rec
        # 顺手清掉过期条目（条数上限 64，成本可忽略）
        for stale in [c for c, r in _LINK_CACHE.items()
                      if now - r.get("ts", 0) > _LINK_TTL]:
            _LINK_CACHE.pop(stale, None)
        while len(_LINK_CACHE) > _LINK_CACHE_MAX:
            _LINK_CACHE.pop(next(iter(_LINK_CACHE)))
        item = _LINK_PENDING.get(seq)
        if item is None:
            item = {"code": code, "values": {}}
            _LINK_PENDING[seq] = item
        item["values"].update(values)
        left = _LINK_LEFT.get(seq, SOURCE_TASK_COUNT) - 1
        if left <= 0:
            _LINK_LEFT.pop(seq, None)
            _LINK_INFLIGHT.pop(code, None)
            _LINK_INFLIGHT_AT.pop(code, None)
        else:
            _LINK_LEFT[seq] = left

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

def prefetch_play_sources(code, updates=None):
    """进入详情页时并行预取三条播放链接；取不到的保持空串（按钮置灰）。

    updates: 调用方（open_detail）传入的 batch_update 字段字典——src_*
    的复位值 / 缓存值直接合并进去，由调用方一次性提交，本函数不单独
    写 State（避免一次点击触发多次整树重建）。
    """
    global _LINK_SEQ
    code = str(code or "").strip().upper()
    src = {"src_preview": "", "src_trailer": "", "src_video": ""}
    submit = None
    if code:
        with _LINK_LOCK:
            cached = _LINK_CACHE.get(code)
            # 缓存里至少有一条链接且未过期才复用，否则重新去取（避免一次失败就长期置灰）
            if cached and time.time() - cached.get("ts", 0) <= _LINK_TTL \
                    and (cached.get("preview") or cached.get("trailer") or cached.get("video")):
                src["src_preview"] = cached.get("preview", "")
                src["src_trailer"] = cached.get("trailer", "")
                src["src_video"] = cached.get("video", "")
            else:
                # 在途任务超时未收口（worker 异常 / 结果丢失）：作废并允许重新预取，
                # 否则该番号会在整个 TTL 内一直置灰
                if code in _LINK_INFLIGHT \
                        and time.time() - _LINK_INFLIGHT_AT.get(code, 0.0) \
                        > _LINK_INFLIGHT_TTL:
                    dead = _LINK_INFLIGHT.pop(code, None)
                    _LINK_INFLIGHT_AT.pop(code, None)
                    _LINK_LEFT.pop(dead, None)
                    _LINK_PENDING.pop(dead, None)
                if not _LINK_INFLIGHT.get(code) \
                        and len(_LINK_INFLIGHT) < _LINK_INFLIGHT_MAX:
                    _LINK_SEQ += 1
                    seq = _LINK_SEQ
                    _LINK_INFLIGHT[code] = seq
                    _LINK_INFLIGHT_AT[code] = time.time()
                    _LINK_LEFT[seq] = SOURCE_TASK_COUNT
                    submit = seq
    if updates is None:
        _batch_state(**src)
    else:
        updates.update(src)
    if submit is not None:
        _TASK_POOL.submit(_jable_sources_worker, code, submit)
        _TASK_POOL.submit(_trailer_source_worker, code, submit)

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
    updates = {}
    for item in items:
        if str(item.get("code") or "") != code:
            continue
        for key, value in (item.get("values") or {}).items():
            field = SOURCE_FIELDS.get(key)
            if not field or not value:
                continue
            if state.get(field) != value:
                updates[field] = value
    if updates:
        updates["reload"] = state.reload + 1
        _batch_state(**updates)


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
        "fail_streak": 0,   # 连续网络失败次数：决定重试退避时长
        "next_retry": 0.0,  # 失败退避截止时刻：期内 _pump 不再重试
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
    if len(_PUSHED_VIDS) > 8:
        del _PUSHED_VIDS[:4]    # 只留最近的兜底引用：过多会把旧展示位 pin 住不回收
    path.append({"tag": "list", "data": {"vid": vid}})


# ------------------------------------------------------------------
#  导航 push 防重：连点同一个条目只放行一次
# ------------------------------------------------------------------
# 问题：连续快速点击同一格子 / 同一个筛选项，会连续 push 同一页面
# （详情 / 大图 / 跳转列表），导航栈里压入多份相同页面——返回时要按同样
# 多的次数才能回到列表。
# 方案：push 前做「同一目标 + 时间窗」防抖；详情另加结构性守卫（同一链接
# 已在栈顶且仍在导航链上就直接忽略）。两者都不写 State，因此连点不会
# 产生额外重建，栈里也始终只有一份，返回永远只退一层。
_PUSH_GUARD = {}
_PUSH_GUARD_GAP = 0.5          # 同一目标的最小 push 间隔（秒）
_PUSH_GUARD_TTL = 60.0         # 记录保留时长（仅用于清理，不影响判定）
_PUSH_GUARD_LOCK = threading.Lock()

def push_allowed(key, gap=_PUSH_GUARD_GAP):
    """同一目标在 gap 秒内只放行一次 push；key 需含页面类型与目标标识。"""
    if not key:
        return True
    now = time.time()
    with _PUSH_GUARD_LOCK:
        if now - _PUSH_GUARD.get(key, 0.0) < gap:
            log("push ignored (debounce): " + str(key))
            return False
        _PUSH_GUARD[key] = now
        if len(_PUSH_GUARD) > 64:       # 顺手清理过期记录，避免无界增长
            for k, t in list(_PUSH_GUARD.items()):
                if now - t > _PUSH_GUARD_TTL:
                    _PUSH_GUARD.pop(k, None)
        return True

def clear_push_guard(key):
    """返回后清除防抖记录：允许立刻重新进入同一目标。"""
    with _PUSH_GUARD_LOCK:
        _PUSH_GUARD.pop(key, None)

def clear_push_guard_prefix(prefix):
    """按前缀清除防抖记录（如关闭大图浏览后清空全部 sample 记录）。"""
    with _PUSH_GUARD_LOCK:
        for k in [k for k in _PUSH_GUARD if k.startswith(prefix)]:
            _PUSH_GUARD.pop(k, None)

def detail_push_blocked(host, link):
    """结构性守卫：该详情已是本 tab 详情栈顶、且仍在导航链上 → 忽略重复点击。

    与时间无关：只要这个详情还显示在屏幕上，就不会再压入一层，
    因此返回永远只需一次。
    """
    stack = DETAIL_STACKS.get(host)
    v = VIEWS.get(host)
    if not stack or not v:
        return False
    top = stack[-1]
    return (top.get("detail") or {}).get("link") == link \
        and v["path"].count >= top["depth"]

# 根展示位永不回收；动态展示位（详情内跳转的筛选列表）超过上限时回收最旧的
ROOT_VIDS = {HOME_VID, ACTRESS_VID, GENRE_VID, FAV_VID}
MAX_DYNAMIC_VIEWS = 12

def _purge_stale_detail_stacks():
    """清理滞留的详情状态栈。

    on_disappear 在部分场景（展示位被回收、异常导航路径等）不会触发，
    DETAIL_STACKS 条目滞留会让 gc_views 的保留集把死展示位永久 pin 住：
    VIEWS 缓慢泄漏，pump_all_views / 整树重建的扫描成本随之增长
    （表现为浏览一段时间后越用越卡）。
    """
    for host, stack in list(DETAIL_STACKS.items()):
        v = VIEWS.get(host)
        if v is None or v["path"].count < stack[-1]["depth"]:
            DETAIL_STACKS.pop(host, None)
    if not DETAIL_STACKS and state.detail_open:
        state.detail_open = False

def gc_views():
    """动态展示位生命周期回收（简单上限法，不做 LRU）。

    只删除同时满足以下条件的展示位：
      - 非根展示位；
      - 已不在导航链上（不在 _PUSHED_VIDS / DETAIL_STACKS / DETAIL_HOST）；
      - 没有在途 worker（loading=False）。
    回收顺序从最旧开始，保留最新的 MAX_DYNAMIC_VIEWS 个。
    """
    _purge_stale_detail_stacks()    # 先清掉滞留详情栈，保留集才准确
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
    """收藏列表的数据源：由收藏记录构造，按收藏时间（date）从新到旧。

    结果缓存：收藏记录未变动时直接复用，mark_fav_dirty 时失效。
    """
    global _FAV_ITEMS_CACHE
    if _FAV_ITEMS_CACHE is None:
        out = []
        for item in SHELF["fav"]:
            code = str(item.get("code") or "").strip().upper()
            if not code:
                continue
            out.append({"code": code,
                        "img": item.get("img") or "",
                        "date": str(item.get("fav_time") or "").strip(),
                        "seq": int(item.get("seq") or 0),
                        "link": BASE + "/" + quote(code)})
        # 日期新的在前；同一天内按顺序号从新到旧（与 SHELF 顺序一致）
        _FAV_ITEMS_CACHE = sorted(out, key=_fav_sort_key, reverse=True)
    return _FAV_ITEMS_CACHE

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
    """是否还能往后翻（展示位已被回收时按「不能翻」处理，不再直接索引）。"""
    v = VIEWS.get(vid)
    if not v:
        return False
    with _VIEWS_LOCK:
        if pool_end(v) > v["page"] * page_size(vid):
            return True
        return not v["exhausted"]


# ============================================================
#  展示层：数据抓取（增量追加 + 预加载窗口）
# ============================================================


# 一轮后台任务最多抓几个远程页（避免一次性加载过多造成内存与限流压力）
MAX_FETCH_PER_ROUND = 2
# 同一轮内两次远程请求之间的间隔（秒）
FETCH_GAP = 0.3
# 数据池最多保留的页数，超出后只回收「当前页之前」的旧数据。
# 取较大值：回收会让「跳回前面已翻过的页」越界，从而被回退并重新抓取
# （表现为闪动 + 页码重置）。单条数据很小，120 页仅约 1MB 量级。
POOL_LIMIT_PAGES = 120

_VIEWS_DIRTY = False
# 按展示位隔离的脏标记：不可见展示位的数据变化不触发整树重建，
# 标记保留到该展示位可见时（翻回该 tab / 关闭详情）再消费
_DIRTY_VIDS = set()
# 已显示过数据的展示位：用于「首屏豁免」——切入 tab 后第一批数据
# 到达（占位格 → 真实内容）不等切换宽限窗，立即重建给出首帧反馈
_SHOWN_VIDS = set()

def _pool_has_data(vid):
    """展示位的数据池是否已有内容（首屏豁免判定用）。"""
    v = VIEWS.get(vid)
    return bool(v and v["pool"])

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

def _drop_stale_dirty():
    """作废当前可见展示位的滞留脏标记。

    tab 切换本身已按最新数据整树重建了新 tab，这些标记再被消费只会
    触发一次内容不变的重建（表现为切入 tab 后整页闪一下），因此作废；
    不可见展示位的标记保留，等翻回该 tab / 关闭详情后再消费。
    """
    global _VIEWS_DIRTY, _LAST_IMG_RELOAD
    _VIEWS_DIRTY = False
    clear_dirty()                    # 挂起的图片刷新一并消费（切换重建已重读文件）
    _LAST_IMG_RELOAD = time.time()   # 拉开与下一次图片刷新的最小间隔
    for d in [d for d in _DIRTY_VIDS if _view_visible(d)]:
        _DIRTY_VIDS.discard(d)
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
    return 1 if page_size(kind=v["filter"]["kind"]) >= 12 else 2

def load_window_end(v):
    """预加载窗口末尾（全局序号，不含）。"""
    return (v["page"] + preload_ahead(v)) * page_size(kind=v["filter"]["kind"])

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
        changed = False
        with _VIEWS_LOCK:
            if not (v["exhausted"] and not force):
                v["pool"] = list(fav_items())   # 拷贝：头部回收不会动到缓存
                v["base"] = 0
                v["remote"] = 1
                v["exhausted"] = True
                v["loading"] = False
                changed = True    # 数据池真的重建了才需要刷新
        # 可视窗口的封面检查 / 解析 / 下载：数据池未重建（仅翻页）时也要滑动窗口
        load_fav_movies()
        if changed:
            mark_views_dirty(vid)
        return
    if kind == "genre":
        # 分类：单次抓取全部分组，无翻页
        with _VIEWS_LOCK:
            if v["exhausted"] and not force:
                return
            if v["loading"]:
                return
            if time.time() < v.get("next_retry", 0.0):
                return      # 失败退避期内：不再每个 tick 重试
            v["loading"] = True
            gen = v["generation"]
        _FETCH_POOL.submit(_genre_worker, vid, gen)
        return
    with _VIEWS_LOCK:
        if v["loading"] or v["exhausted"]:
            return
        if time.time() < v.get("next_retry", 0.0):
            return          # 失败退避期内：不再每个 tick 重试（否则网络失败
                            # 的展示位会每 0.5s 拉起一个线程重发请求，越点越多）
        if pool_end(v) >= load_window_end(v):
            return
        v["loading"] = True
        gen = v["generation"]
    _FETCH_POOL.submit(_pump_worker, vid, gen)

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
        # 失败不置 exhausted：退避后由下轮 _pump 重试
        with _VIEWS_LOCK:
            if VIEWS.get(vid) is v:
                v["fail_streak"] = v.get("fail_streak", 0) + 1
                v["next_retry"] = time.time() + min(
                    60.0, 2.0 ** min(v["fail_streak"], 5))
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
                # 网络失败 ≠ 没有更多数据：不置 exhausted，但按连败指数退避，
                # 避免周期任务每 tick 重试形成线程 + 请求风暴
                log("pump net err: page " + str(v["remote"]))
                with _VIEWS_LOCK:
                    if VIEWS.get(vid) is v:
                        v["fail_streak"] = v.get("fail_streak", 0) + 1
                        v["next_retry"] = time.time() + min(
                            60.0, 2.0 ** min(v["fail_streak"], 5))
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
                v["fail_streak"] = 0
                v["next_retry"] = 0.0
                _trim(v, page_size(vid))
            fetched += 1
            prepare_images([m.get("img") or "" for m in res])
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
    """补足「可见展示位」的预加载窗口（每轮只抓少量，逐步填充）。

    只 pump 当前 tab 导航栈上的展示位；不可见展示位由切入该 tab 时
    （set_tab）按需补足。对全部展示位轮询会让浏览过的每个列表
    （尤其是网络失败的）每 tick 都被重试，线程与请求越积越多。
    """
    for vid in list(VIEWS):
        if _view_visible(vid):
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
        v["fail_streak"] = 0    # 新筛选视为全新任务：清掉旧退避
        v["next_retry"] = 0.0
        v["generation"] += 1    # 旧筛选的在途 worker 结果全部作废
    reset_page_inputs()         # 页码重置回 1：未提交的页码输入一并作废
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
            # 该页已被回收：退到数据池仍能覆盖的第一页即可，
            # 数据池 / 远程游标 / 在途任务保持不动（不重置、不重新抓取）
            page = max(1, v["base"] // size + 1)
        elif v["exhausted"]:
            # 已知列表总长时，不允许跳过最后一页
            page = min(page, max(1, (pool_end(v) + size - 1) // size))
        if page != v["page"]:
            v["page"] = page
    _pump(vid)
    return True

def goto_page(vid, page):
    """翻页：页码立即生效，缺失的数据由后台增量补足。"""
    reset_page_inputs(vid)         # 点了翻页按钮：未提交的输入作废
    if apply_page(vid, page):
        state.reload += 1

# 页码输入框绑定 State（page_input / page_input_vid / page_editing）：
# 之前用普通 dict 存输入，网格图片刷新等重建会把已键入内容顶掉；
# 绑定后输入值即 State 真源，重建不会覆盖用户输入。
def pager_editing(vid):
    """该分页条是否处于「输入页码」状态（焦点在输入框上）。

    唯一作用：编辑中把左右翻页按钮隐藏起来。输入框内容、提交与复位
    行为都保持原样。

    page_input_vid 为空表示刚聚焦、还没键入；此时当前分页条进入编辑态，
    被覆盖在导航栈后面的分页条会在首次键入后退出编辑态。
    """
    if not state.page_editing:
        return False
    return state.page_input_vid in ("", vid)

def page_field_text(vid, page):
    """输入框显示值：输入中显示键入内容，其余时候显示当前页码。"""
    if state.page_input_vid == vid and state.page_input:
        return state.page_input
    return str(page)

def set_page_input_value(vid, v):
    """输入校验：只保留数字后写回 State（同值不重复写，避免多余重建）。"""
    digits = "".join(ch for ch in str(v) if ch.isdigit())
    if state.page_input == digits and state.page_input_vid == vid:
        return
    _batch_state(page_input=digits, page_input_vid=vid)

def reset_page_inputs(vid=None):
    """放弃未提交的页码输入（翻页、打开详情、切 tab、换筛选……），
    之后的重建会让输入框回到当前页码显示，并收起编辑态。"""
    if vid is not None and state.page_input_vid not in ("", vid):
        return          # 该 vid 不是当前输入会话：不动
    if state.page_input or state.page_input_vid or state.page_editing:
        _batch_state(page_input="", page_input_vid="", page_editing=False)

def submit_page_input(vid):
    """回车跳页：输入有效则跳转，无效则放弃输入回到当前页码显示。"""
    try:
        page = int(state.page_input or "0")
    except ValueError:
        page = 0
    reset_page_inputs(vid)
    if page >= 1:
        apply_page(vid, page)
    state.reload += 1   # 跳页或恢复页码显示，都需要一次重建


# ============================================================
#  调度层：详情 / 播放 / 刷新的后台任务与主线程提交
# ============================================================


_DETAIL_READY = None
_DETAIL_ERROR = False
_DETAIL_SEQ = 0
_BG_STARTED = False
# 短任务线程池：详情抓取 / 翻译 / 评分 / 播放源共用。
# 以前打开一次详情要起约 5 个短生命周期线程，快速进出详情会反复创建；
# 统一入池（图片下载 ×3、收藏解析 ×2 仍为常驻消费者，不走此池）
_TASK_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="task")
# 列表抓取池：目录页预加载与详情首屏分开排队——共用一个大池时，
# 「一轮预加载多个展示位」会把详情请求挤到队尾。以前每次抓页都新建
# 裸线程，快速翻页 / 切 tab 会短时间堆起大量线程，这里统一收敛。
_FETCH_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fetch")

# 导航转场静默期：push/pop 期间的后台刷新暂缓，避免打断转场动画
_RELOAD_SILENT_UNTIL = 0.0
_NAV_SILENCE = 0.8
_DETAIL_SAFE_AFTER = 0.6
_LAST_TAB = -1
_LAST_TAB_SWITCH = 0.0
TAB_RELOAD_GRACE = 0.35   # 切换宽限窗：原 0.6 —— 首屏豁免兜底后可更短

# 图片刷新去抖
_LAST_IMG_RELOAD = 0.0
# 本次 tab 停留期间是否已刷过一次图片：首刷豁免用（切入后封面尽快出现）
_TAB_IMG_FLUSHED = True
IMG_SILENCE_INTERVAL = 0.9
IMG_MAX_RELOAD_INTERVAL = 3.0
IMG_RELOAD_MIN_GAP = 2.0
IMG_MAX_RELOAD_LONG = 6.0
IMG_RELOAD_MIN_GAP_DETAIL = 2.5

def note_nav_action():
    """导航/转场前调用：开启静默窗，并收起页码输入的编辑态。"""
    global _RELOAD_SILENT_UNTIL
    _RELOAD_SILENT_UNTIL = time.time() + _NAV_SILENCE
    if state.page_editing:
        # 任何 push / pop 都结束页码编辑：避免返回后分页条停在编辑态
        # （翻页按钮不显示）
        state.page_editing = False

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

def _sync_dirty():
    """主线程周期任务：图片刷新 + 列表提交 + 播放请求 + 详情提交。"""
    global _VIEWS_DIRTY, _LAST_IMG_RELOAD
    global _LAST_TAB, _LAST_TAB_SWITCH, _FAV_DIRTY
    global _TAB_IMG_FLUSHED
    now = time.time()
    # 本 tick 的界面变更合并成一个标志：几何测量 / 图片刷新 / 列表数据
    # 各自 state.reload += 1 会让同一个 tick 触发多达 4 次整树重建
    need_reload = False
    if state.tab != _LAST_TAB:
        # 兜底复位：若 on_change 回调未触发（纯绑定同步），这里也能
        # 检测到切换并把停在详情页的旧 tab 退回主页面
        leave_tab_reset(_LAST_TAB)
        _LAST_TAB = state.tab
        _LAST_TAB_SWITCH = now
    settled = reload_allowed() and (now - _LAST_TAB_SWITCH) >= TAB_RELOAD_GRACE

    # 渲染期发现未准备的图片：主线程补数据层路径解析（写占位文件），
    # 有新可用路径时安排一次重建填充真图
    consume_prepare_pending()
    # 清理滞留详情栈：防止 VIEWS 随浏览缓慢泄漏、扫描成本逐 tick 增长
    _purge_stale_detail_stacks()

    # 应用已稳定的几何测量：tab 首次出现时的连续回调只对应一次重建，
    # 且直接以最终尺寸应用，中间的过渡尺寸不产生任何中间渲染
    if _PENDING_GEOM and settled:
        stable = [k for k, p in _PENDING_GEOM.items()
                  if now - p["at"] >= _GEOM_STABLE_DELAY]
        if stable:
            for k in stable:
                _apply_pending_geometry(k)
                del _PENDING_GEOM[k]
            need_reload = True

    # 收藏变动后重建收藏 tab 的数据池（保持当前页码不变）
    if _FAV_DIRTY:
        _FAV_DIRTY = False
        fv = VIEWS.get(FAV_VID)
        if fv and fv["exhausted"]:
            fv["pool"] = list(fav_items())
            fv["base"] = 0
            load_fav_movies()
            mark_views_dirty(FAV_VID)

    if is_dirty():
        quiet = now - last_activity() >= IMG_SILENCE_INTERVAL
        detail = state.detail_open
        max_wait = IMG_MAX_RELOAD_LONG if detail else IMG_MAX_RELOAD_INTERVAL
        min_gap = IMG_RELOAD_MIN_GAP_DETAIL if detail else IMG_RELOAD_MIN_GAP
        overdue = now - _LAST_IMG_RELOAD >= max_wait
        # 切换后首刷：只要有已完成的下载就立即显示（is_dirty 保证 ≥1 张），
        # 不等下载静默 / 节流，让切入 tab 后封面尽快出现；
        # 后续刷新仍走原节流，避免下载高峰期频繁重建
        first_flush = not _TAB_IMG_FLUSHED
        if ((quiet or overdue or first_flush) and settled
                and (first_flush or now - _LAST_IMG_RELOAD >= min_gap)):
            clear_dirty()
            _LAST_IMG_RELOAD = now
            _TAB_IMG_FLUSHED = True
            need_reload = True

    if _VIEWS_DIRTY or _DIRTY_VIDS:
        # 可见性隔离：只在本轮有「屏幕上可能显示的」脏展示位时才重建。
        # 一次重建刷新整棵树，因此可见脏位存在时顺带消费全部标记；
        # 全部不可见时保留标记，等翻回对应 tab / 关闭详情后再刷新。
        visible = [vid for vid in _DIRTY_VIDS if _view_visible(vid)]
        # 首屏豁免：切入 tab 后第一批数据到达（占位格 → 真实内容），
        # 不等切换宽限窗立即重建；转场静默（settled 内含）仍遵守
        first_screen = any(vid not in _SHOWN_VIDS and _pool_has_data(vid)
                           for vid in visible)
        if (settled or first_screen) and (_VIEWS_DIRTY or visible):
            need_reload = True
            _VIEWS_DIRTY = False
            _DIRTY_VIDS.clear()
            _SHOWN_VIDS.update(visible)

    # 本 tick 合并后的唯一一次重建
    if need_reload:
        state.reload += 1

    # 翻到已加载内容的末尾后，继续把预加载窗口填满（每轮只抓少量）
    if settled:
        pump_all_views()

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
            if cur:
                # 整体重赋值：State 对 dict 的原地修改不可见（见下方说明）
                err = dict(cur)
                err["_loading"] = False
                err["error"] = True
                state.detail = err
            state.reload += 1
            return
        if not d.get("code") and cur and cur.get("code"):
            d["code"] = cur["code"]
        if not d.get("cover") and cur and cur.get("cover"):
            d["cover"] = cur["cover"]
        # 整体重赋值，不做原地修改：State 的 dict getter 可能返回副本/代理，
        # cur[k]=v 的原地写法对后续读取不可见，详情会永远停在 _loading
        d.pop("_loading", None)
        d.pop("error", None)
        state.detail = d
        st = DETAIL_STACKS.get(DETAIL_HOST)
        if st:
            st[-1]["detail"] = d      # 栈内快照同步为已提交版本（返回上层时恢复用）
        prepare_images([d["cover"]] + [a["img"] for a in d["actresses"]]
                       + [s["img"] for s in d["samples"]])
        for a in d["actresses"]:
            request_img(a["img"], priority=True)
        request_img(d["cover"], priority=True)
        # 缩略图进入详情即加载；大图不预取，点击查看大图时才加载（见 show_sample）
        for s in d["samples"]:
            request_img(s["img"], priority=True)
        # 标题/评分的初始显示值与本轮 reload 合并成一次提交
        # （逐字段写会各自触发一次整树重建）
        name_text, title_trans, rating_text = _initial_title_display(d)
        updates = {"name_text": name_text, "title_trans": title_trans,
                   "rating_text": rating_text, "reload": state.reload + 1}
        _batch_state(**updates)
        # 后台翻译 / 评分（初始显示值已在上面提交，defer_state 不再写）
        translate_title_async(d, defer_state=True)
        rating_async(d, defer_state=True)
    elif _DETAIL_ERROR:
        _DETAIL_ERROR = False
        if not state.detail_open:
            return
        cur = state.detail
        if cur and cur.get("_loading"):
            # 整体重赋值：State 对 dict 的原地修改不可见（见 _commit_detail）
            err = dict(cur)
            err["_loading"] = False
            err["error"] = True
            state.detail = err
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

_TRANS_CACHE = OrderedDict()   # 日文原文 -> 中文译文（LRU：满时逐出最旧，不整表清空）
_TRANS_CACHE_MAX = 200
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

def translate_title_async(d, defer_state=False):
    """发起标题翻译：命中缓存直接显示，否则后台请求（结果由主线程提交）。

    defer_state=True：初始显示值已由调用方随 batch_update 提交，
    这里只负责提交后台任务，不再写 State（省一次整树重建）。
    """
    global _TRANS_SEQ
    text = str(d.get("name") or "").strip()
    if not text:
        return
    cached = _TRANS_CACHE.get(text)
    if cached:
        _TRANS_CACHE.move_to_end(text)      # LRU：命中即续期
        if not defer_state:
            _batch_state(name_text=cached, title_trans=True)
        return
    if not defer_state:
        _batch_state(name_text="翻译中...", title_trans=False)
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
            key = str(cur.get("name") or "").strip()
            _TRANS_CACHE[key] = r["text"]
            _TRANS_CACHE.move_to_end(key)
            while len(_TRANS_CACHE) > _TRANS_CACHE_MAX:
                _TRANS_CACHE.popitem(last=False)    # LRU 逐出，不再整表清空
            _batch_state(name_text=r["text"], title_trans=True)
        else:
            # 翻译失败：恢复日文原标题
            _batch_state(name_text=str(cur.get("name") or ""),
                         title_trans=False)


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

def rating_async(d, defer_state=False):
    """发起评分抓取（后台线程，结果由主线程提交）。defer_state 同翻译。"""
    global _RATING_SEQ
    code = str(d.get("code") or "").strip()
    if not code:
        return
    if not defer_state:
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

def _initial_title_display(d, want_rating=True):
    """详情标题/评分的初始显示值：(name_text, title_trans, rating_text)。

    供 open_detail / _commit_detail 与 batch_update 合并成一次提交。
    want_rating=False 用于「详情还在加载中」的场景（此时不显示评分行）。
    """
    text = str(d.get("name") or "").strip()
    cached = None
    if text:
        cached = _TRANS_CACHE.get(text)
        if cached:
            _TRANS_CACHE.move_to_end(text)      # LRU：命中即续期
    if cached:
        name_text, title_trans = cached, True
    elif text:
        name_text, title_trans = "翻译中...", False
    else:
        name_text, title_trans = "", False
    if want_rating and str(d.get("code") or "").strip():
        rating_text = "评分：获取中..."
    else:
        rating_text = ""
    return name_text, title_trans, rating_text

def reset_pending():
    global _DETAIL_READY, _DETAIL_ERROR, _DETAIL_SEQ
    _DETAIL_SEQ += 1
    _DETAIL_READY = None
    _DETAIL_ERROR = False

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

def _halt_player():
    """暂停并停止本地播放器（含画中画）。不写 State：由调用方按需合并提交。"""
    try:
        player = get_player()
        player.pause()
        player.stop()
    except Exception as e:
        log("stop player err: " + str(e))

def stop_local_playback():
    """暂停并停止本地播放、关闭画中画，避免与外部播放器同时播放。"""
    _halt_player()
    _batch_state(panel="", panel_title="", panel_open=False)

def play_url(url, title="", source=""):
    log("play: " + str(title) + " -> " + str(url)[:120])
    try:
        start_playback(url)      # 自动播放 + 默认静音
    except Exception as e:
        log("player load err: " + str(e))
    # 播放面板交给系统 sheet：点播放即展开，同时 TabView 底部出现常驻条
    _batch_state(panel=url, panel_title=title, play=source, panel_open=True,
                 status="", reload=state.reload + 1)

def open_detail(movie, vid):
    """打开影片详情：在展示位 vid 所属的导航栈内 push 详情页。"""
    log("open_detail: " + str(movie.get("link")))
    global DETAIL_OPEN_AT, DETAIL_HOST, DETAIL_PATH, _DETAIL_PATH_DEPTH
    host = vid if vid in VIEWS else HOME_VID
    link = movie.get("link") or ""
    if not link:
        return
    # 连点防重复入栈：① 同一详情已在栈顶且仍在导航链上 → 忽略；
    # ② 同一链接在防抖窗口内被重复触发 → 忽略。命中时直接返回，
    #    不写 State、不 push，返回因此永远只退一层
    if detail_push_blocked(host, link) or not push_allowed("detail:" + link):
        return
    reset_page_inputs()         # 点了列表项：未提交的页码输入作废
    if vid in VIEWS and VIEWS[vid]["filter"]["kind"] == "fav":
        # 暂停收藏封面补全线程，避免与详情请求竞争
        pause_fav_movies()
    thumb = movie.get("img") or ""
    ready = take_ready(link)
    cur = state.detail
    need_fetch = False
    if ready:
        new_detail = ready
    elif (cur and cur.get("link") == link
          and not cur.get("_loading") and not cur.get("error")):
        new_detail = cur
    else:
        # 加载期间不展示列表封面：留空，等详情抓到后再整体渲染
        new_detail = {"_loading": True,
                      "code": movie.get("code", ""),
                      "cover": "",
                      "name": movie.get("title", ""),
                      "link": link}
        need_fetch = True
    # 本函数原来逐字段写 State（约十次整树重建），是打开详情卡顿的
    # 主因之一：全部字段（含播放源复位值）合并成一次批量提交。
    name_text, title_trans, _rating = _initial_title_display(
        new_detail, want_rating=False)
    rating_text = ""
    if not need_fetch and name_text \
            and str(new_detail.get("code") or "").strip():
        rating_text = "评分：获取中..."
    updates = {"detail_open": True,
               "name_text": name_text, "title_trans": title_trans,
               "rating_text": rating_text}
    if state.detail_thumb != thumb:
        updates["detail_thumb"] = thumb
    if state.panel or state.panel_title or state.play or state.status:
        updates.update(panel="", panel_title="", play="", status="")
    # 播放源复位值 / 缓存值也合并进同一次提交
    prefetch_play_sources(new_detail.get("code"), updates=updates)
    # detail 必须直写，不能走 batch_update：批量提交不保留 dict 值的对象
    # 身份（会拷贝/重序列化），而 DETAIL_STACKS 存的是同一个原始 dict——
    # 身份一旦失效，detail_destination 每次重建都会把还带 _loading 的
    # 原始快照写回 State，详情页永远停在加载中
    state.detail = new_detail
    _batch_state(**updates)
    DETAIL_OPEN_AT = time.time()
    if not need_fetch and name_text:
        # 初始显示值已随批量提交，这里只发起后台翻译 / 评分
        translate_title_async(new_detail, defer_state=True)
        rating_async(new_detail, defer_state=True)
    # 详情与它内部的跳转列表都推入「打开它的那个展示位」的导航栈
    DETAIL_HOST = host
    DETAIL_PATH = VIEWS[DETAIL_HOST]["path"]
    note_nav_action()
    DETAIL_PATH.append({"tag": "detail", "host": DETAIL_HOST})
    _DETAIL_PATH_DEPTH = DETAIL_PATH.count
    # 记入该 tab 自己的详情栈（含栈深基准），切回这个 tab 时恢复显示它的详情
    DETAIL_STACKS.setdefault(DETAIL_HOST, []).append(
        {"detail": new_detail, "depth": _DETAIL_PATH_DEPTH})
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
    closed_link = (stack[-1].get("detail") or {}).get("link") or ""
    stack.pop()
    if closed_link:
        clear_push_guard("detail:" + closed_link)   # 返回后允许立刻重进同一详情
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
    # 连点同一筛选项只入栈一次（否则返回要按多次）
    if not push_allowed("list:" + str(link)):
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
    """关闭播放：停止本地播放（含画中画）并收起播放面板。"""
    _halt_player()
    _batch_state(panel="", panel_title="", play="", panel_open=False)

def open_external_player():
    """把当前播放链接交给设置里选定的外部播放器（URL Scheme 可配置）。"""
    url = state.panel or ""
    if not url:
        _batch_state(status="请先播放视频", reload=state.reload + 1)
        return
    name = SETTINGS["player"]
    scheme = EXTERNAL_PLAYERS.get(name, name)
    code = (state.detail or {}).get("code", "")
    target = (scheme + "://x-callback-url/play?url=" + quote(url, safe="") +
              "&name=" + quote(code, safe="") + "&User-Agent=" + scheme)
    # 先暂停并停止本地播放、关闭画中画，避免与外部播放器同时播放/冲突
    _halt_player()
    if shortcuts.open_url(target):
        _batch_state(panel="", panel_title="", play="", panel_open=False,
                     status="已跳转 " + name, reload=state.reload + 1)
    else:
        _batch_state(panel="", panel_title="", panel_open=False,
                     status="打开失败", reload=state.reload + 1)

def copy_video_link():
    if state.panel:
        clipboard.set(state.panel)
        status = "链接已复制"
    else:
        status = "请先播放视频"
    _batch_state(status=status, reload=state.reload + 1)

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

def _load_sample_window():
    """只加载当前样片 ±1 的大图，翻页时增量补足。

    避免进入大图浏览就把全部样片大图排入下载队列造成内存峰值。
    """
    samples = (state.detail or {}).get("samples") or []
    idx = max(0, min(int(state.sample_index or 0), len(samples) - 1))
    window = [s.get("link") or "" for s in samples[max(0, idx - 1):idx + 2]]
    window = [u for u in window if u]
    prepare_images(window)
    for link in window:
        request_img(link, priority=True)

def on_sample_page_change(_value=None):
    """样片大图翻页：加载新当前页 ±1 的大图。"""
    _load_sample_window()

def show_sample(link):
    """查看样片大图：加载当前 ±1 后推入浏览（可左右滑动翻看）。"""
    if not push_allowed("sample:" + str(link)):
        return      # 连点同一张样片只入栈一次
    samples = (state.detail or {}).get("samples") or []
    idx = 0
    for i, s in enumerate(samples):
        if s.get("link") == link:
            idx = i
            break
    state.sample_index = idx
    _load_sample_window()
    note_nav_action()
    DETAIL_PATH.append({"tag": "sample"})

def close_sample():
    note_nav_action()
    DETAIL_PATH.pop(count=1)
    state.sample_index = 0
    clear_push_guard_prefix("sample:")   # 关闭后允许立刻再进大图浏览

def copy_code():
    if state.detail:
        code = state.detail["code"]
        clipboard.set(code)
        _batch_state(status="番号 " + code + " 已复制",
                     reload=state.reload + 1)

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

def grid_cover(url, ratio=None):
    """网格封面：与详情页封面同一套已验证的填充模式。

    aspect_ratio + content_mode="fill" 让图片按比例撑满自身框，
    clipped 裁掉多余部分——图片严格贴合框内，不会溢出盖住相邻单元格
    之间的空隙。ratio 缺省用影片封面比例 5:7；女优头像传 5:6（更矮，
    人脸裁切更自然，且 4 行头像可正好铺满可视高度）。

    源为空、或本地路径尚未准备（img_src 返回空串）时，渲染同比例灰底
    占位框：AsyncImage 收到空地址不会渲染任何内容，格子会塌陷成 0 高，
    真图填入时整行跳动；固定比例的占位框保证布局稳定，图片就绪后填入。
    """
    ratio = ratio or COVER_RATIO
    src = img_src(url) if url else ""
    if not src:
        return appui.Rectangle() \
            .foreground_color("secondarySystemBackground") \
            .aspect_ratio(ratio, content_mode="fill") \
            .frame(max_width=appui.infinity) \
            .clipped() \
            .background("secondarySystemBackground", corner_radius=COVER_CELL_RADIUS) \
            .z_index(0)
    return appui.AsyncImage(url=src) \
        .aspect_ratio(ratio, content_mode="fill") \
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
    """叠在封面上的一行文字（番号 / 发布日期 / 女优名共用同一样式）。

    统一的小字号 + 高透明度样式：弱化对封面内容的遮挡（影片 / 收藏 /
    女优三处一致）。
    """
    return appui.Text(text) \
        .font(size=10) \
        .foreground_color("white") \
        .opacity(0.85) \
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
        .background("black", corner_radius=4, opacity=0.4) \
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
        .font(size=10) \
        .foreground_color("white") \
        .opacity(0.85) \
        .line_limit(1) \
        .minimum_scale_factor(0.6) \
        .padding(horizontal=4, vertical=3) \
        .frame(max_width=GRID_CAPTION_WIDTH) \
        .background("black", corner_radius=4, opacity=0.4) \
        .padding(bottom=6) \
        .z_index(1)
    # 女优头像用独立比例 5:6（比封面矮）：人脸裁切更自然，
    # 且 4 行头像可正好铺满可视高度
    cover = grid_cover(a["img"], ratio=ACTRESS_RATIO)
    return appui.Button(
        action=open,
        content=appui.ZStack([cover, caption], alignment="bottom"),
    ).button_style("plain").id(a.get("link") or a.get("name") or "")

def genre_cell(c):
    """二级分类按钮：等宽 + 背景色，点击按该分类筛选影片。"""

    def open():
        open_genre(c["link"], c["name"])

    return     appui.Button(
        action=open,
        content=appui.Label(c["name"], system_image="tag")
            .font("caption")
            .line_limit(1)
            .minimum_scale_factor(0.7)
            .frame(max_width=appui.infinity, min_height=44)
            .padding(vertical=12)
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

    # id 由 movie_cell 统一设置，这里不再重复覆盖
    return movie_cell(item, FAV_VID).context_menu(content=[
        appui.Button("从收藏移除", action=unfav, role="destructive"),
    ])

def grid_cell(item, vid):
    """按展示位类型选择单元格：影片/收藏用封面，女优用头像。"""
    kind = view_kind(vid)
    if kind == "actress":
        return actress_cell(item)
    if kind == "fav":
        return fav_cell(item)
    return movie_cell(item, vid)

def placeholder_cell(vid):
    """未加载数据的占位格：与真实单元格同一比例 / 圆角 / 底色的空框。

    网格按测量尺寸先铺满整页，数据到达后由重建逐格填充，
    未加载期间不出现空行或加载指示行。
    Rectangle 是 Shape，默认以黑色填充——必须显式给柔和的灰色，
    否则占位格是一块纯黑，与界面反差强烈。
    """
    ratio = ACTRESS_RATIO if view_kind(vid) == "actress" else COVER_RATIO
    return appui.Rectangle() \
        .foreground_color("secondarySystemBackground") \
        .aspect_ratio(ratio, content_mode="fill") \
        .frame(max_width=appui.infinity) \
        .clipped() \
        .background("secondarySystemBackground", corner_radius=COVER_CELL_RADIUS)

def sample_cell(s):
    """详情页样图格：缩略图随详情加载，点击查看大图（大图此时才加载）。"""

    def open():
        show_sample(s["link"])

    src = img_src(s["img"])
    if src:
        content = appui.AsyncImage(url=src) \
            .frame(height=110).clipped() \
            .background("secondarySystemBackground", corner_radius=6)
    else:
        # 未就绪的缩略图：同高占位框，避免样图网格高度跳动
        content = appui.Rectangle() \
            .foreground_color("secondarySystemBackground") \
            .frame(max_width=appui.infinity, min_height=110, max_height=110) \
            .background("secondarySystemBackground", corner_radius=6)
    return appui.Button(action=open, content=content).button_style("plain")

def magnet_row(m):
    """磁链行（左滑可复制）。"""

    def copy():
        clipboard.set(m["info"])

    return appui.Label(m["name"], system_image="link").swipe_actions(actions=[
        appui.Button("复制", action=copy, role="destructive"),
    ])

# 搜索框直接绑定 State.keyword（原生 .searchable 的 text）：
# 之前用普通 dict 存输入，任何一次重建都会把用户正在输入的内容顶掉。
def set_search_input(v):
    """on_change 回调：写回 State（重建频率由 State 的 debounce 收敛）。

    系统「取消」清空输入时（v 为空）同步退回最新影片列表。
    """
    state.keyword = v
    if not v and view_kind(HOME_VID) == "search":
        clear_search()

def pager_row(vid):
    """翻页条：左上翻、右下翻、中间页码即输入框（未输入时显示当前页码）。"""

    def prev():
        goto_page(vid, VIEWS[vid]["page"] - 1)

    def next_page():
        goto_page(vid, VIEWS[vid]["page"] + 1)

    page = VIEWS[vid]["page"]

    def on_change(v):
        set_page_input_value(vid, v)

    def on_submit():
        submit_page_input(vid)

    # 翻页按钮做到 44pt 触控高度（PAGER_ROW_H 已同步为 44+12=56，
    # compute_page_size 依此扣减可用高度，保证内容不会越过分页条）
    editing = pager_editing(vid)
    prev_btn = appui.Button(
        content=appui.Label("上一页", system_image="chevron.left"),
        action=prev,
    ).button_style("bordered") \
        .frame(min_height=44).disabled(page <= 1 or editing)
    next_btn = appui.Button(
        content=appui.Label("下一页", system_image="chevron.right"),
        action=next_page,
    ).button_style("bordered") \
        .frame(min_height=44).disabled((not can_next(vid)) or editing)
    # 中间：页码本身就是输入框——未输入时显示当前页码，
    # 输入数字 + 回车即跳转；点其他区域未提交则回到当前页码显示
    center = appui.HStack([
        appui.Text("第").font("subheadline"),
        appui.TextField("", text=page_field_text(vid, page),
                        on_change=on_change, keyboard_type="number",
                        submit_label="go")
            .text_field_style("plain")
            .multiline_text_alignment("center")
            .on_submit(on_submit)
            .font("subheadline").bold()
            .focused(state.bind.page_editing)
            .frame(min_width=20, max_width=56),
        appui.Text("页").font("subheadline"),
    ], spacing=0)
    if editing:
        # 输入页码时隐藏左右翻页按钮：用 hidden() 只隐藏、保留占位，
        # 视图层级完全不变——若换成另一套结构，输入框会被重建而失去焦点
        prev_btn = prev_btn.hidden()
        next_btn = next_btn.hidden()
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

    if view_kind(vid) == "fav":
        # 收藏 tab 顶部：已收藏总数（占位与搜索栏一致）
        parts.append(fav_count_row())

    loading = page_loading(vid)
    items = page_items(vid)
    # 按测量尺寸铺满整页格子：已到的数据立即渲染，未到的用同尺寸占位格
    # 补齐，数据到达后随重建逐格填充（加载管线不变，仅展示层变化）
    cells = [grid_cell(m, vid) for m in items]
    missing = page_size(vid) - len(items)
    if missing > 0 and loading:
        cells.extend(placeholder_cell(vid) for _ in range(missing))
    if cells:
        parts.append(appui.LazyVGrid(
            columns=grid_columns(),
            spacing=GRID_SPACING,
            content=cells,
        ))
    elif not loading:
        # 无内容且不在加载中才提示；加载中显示整页占位格
        parts.append(appui.ContentUnavailableView(
            "没有找到影片", system_image="film",
            description="换个筛选条件或下拉刷新再试"))

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
        return appui.ContentUnavailableView(
            "没有找到分类", system_image="tag",
            description="下拉刷新再试").padding()

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
    _batch_state(genre_group=v, reload=state.reload + 1)

def display_page_view(vid, titled=True):
    """把通用展示包装成可导航的页面（下拉刷新按附加设置决定）。

    titled=False 用于影片 / 女优 / 收藏三个 tab 根页：
      - 分页条以底部安全区插肩（safeAreaInset）钉在底部，不随内容
        滚动，无需滚动页面即可点击；原生键盘避让自动让它贴紧键盘；
      - 滚动区铺满 GeometryReader 实测的整个可用区域（不对其内容限高），
        每页项数按「实测高度 - 分页条插肩高度」计算，内容不会越过分页条，
        测量与布局完全解耦，无反馈回路。
    推入的跳转列表仍保留标题，分页条随内容滚动。
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

    if titled:
        # 推入的跳转列表：分页条随内容滚动（保持原结构）
        sv = appui.ScrollView(movie_display(vid, with_pager=True))
        if v["extras"].get("refresh"):
            sv = sv.refreshable(action=refresh_view)
        return sv.navigation_title(view_title(vid))

    # 三个 tab 根页：分页条以底部安全区插肩（safeAreaInset）钉在底部，
    # 原生键盘避让自动把它抬到键盘上方并紧贴键盘——弹出/收起全程
    # 无需跟踪键盘状态或手动重建；滚动内容自动为插肩条让位
    pager = pager_row(vid) \
        .padding(horizontal=PAGE_H_PAD) \
        .padding(vertical=6) \
        .background("systemBackground", opacity=0.92)
    sv = appui.ScrollView(movie_display(vid, with_pager=False))
    if v["extras"].get("refresh"):
        sv = sv.refreshable(action=refresh_view)
    if v["extras"].get("search"):
        # 原生搜索栏挂在导航栏（只影片首页有），搜索/取消交互全部交给系统；
        # text 绑定 State.keyword，重建不会顶掉用户正在输入的内容
        sv = sv.searchable(text=state.keyword, prompt="番号或演员",
                           on_change=set_search_input, on_submit=do_search)
    return appui.GeometryReader(
        content=sv.safe_area_inset(edge="bottom", content=pager),
        on_change=make_grid_observer(page_size_key(view_kind(vid))),
    )


# ============================================================
#  UI 层：路由目标（详情 / 大图 / 跳转列表）
# ============================================================


def _restore_detail_host(host):
    """生成 on_appear 回调：切回该 tab 时恢复它自己的详情。

    构建期（body() 内）只读不写 State——官方硬规则：body() 不得修改状态。
    以前这里直接赋值，构成「构建 -> 写 State -> 重建 -> 再写」的风暴，
    并且会把栈里的旧快照写回、覆盖已提交的详情。恢复动作改由
    on_appear 触发（切回该 tab 时执行一次）。
    """
    def restore():
        stack = DETAIL_STACKS.get(host)
        if not stack:
            return
        entry = stack[-1]
        cur = state.detail
        if (cur or {}).get("link") != (entry["detail"] or {}).get("link"):
            state.detail = entry["detail"]
        if not state.detail_open:
            state.detail_open = True
    return restore

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
        # 这里只做模块级导航簿记（点按回调需要），不写 State
        DETAIL_HOST = host
        DETAIL_PATH = VIEWS[host]["path"]
        _DETAIL_PATH_DEPTH = stack[-1]["depth"]

    def on_closed():
        on_detail_closed(host)

    return detail_page_view() \
        .on_appear(action=_restore_detail_host(host)) \
        .on_disappear(action=on_closed)

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
        return appui.ContentUnavailableView(
            "列表已失效", system_image="questionmark.folder",
            description="请返回后重试").navigation_title("影片")
    return display_page_view(vid)


# ============================================================
#  UI 层：详情页
# ============================================================


# 详情页封面：按标准比例撑满宽度，上下不留空白
def _cover_view(url):
    src = img_src(url)
    if not src:
        # 未准备好的封面：同比例占位框保持布局，路径补准备后由重建填充
        return appui.Rectangle() \
            .foreground_color("secondarySystemBackground") \
            .aspect_ratio(COVER_RATIO, content_mode="fill") \
            .frame(max_width=appui.infinity)
    return appui.AsyncImage(url=src) \
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
        return appui.ContentUnavailableView(
            "加载失败", system_image="exclamationmark.triangle",
            description="请返回列表后重试").padding()

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
        """等宽按钮：当前播放来源自动高亮（样式与触控高度见 wide_button）。"""
        if source is not None and state.play == source:
            prominent = True
        return wide_button(label, action, prominent=prominent)

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
        # 播放状态由 TabView 底部常驻条 + 系统 sheet 承载（官方模式）：
        # 详情页不再内嵌播放器——重型媒体视图不放可滚动区域，
        # 这里只留一个入口，把完整的播放控制交给 sheet
        top = appui.VStack([
            top,
            appui.HStack([
                appui.Text("正在播放：" + (state.panel_title or state.play))
                    .font("caption").foreground_color("secondaryLabel").line_limit(1),
                appui.Spacer(min_length=8),
                appui.Button("播放面板", action=open_player_panel),
            ], spacing=8),
        ], spacing=8)
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

        src = img_src(a["img"])
        if src:
            thumb = appui.AsyncImage(url=src) \
                .frame(width=58, height=58).clipped() \
                .background("secondarySystemBackground", corner_radius=8)
        else:
            # 未就绪的头像：同尺寸占位框，避免女优网格跳动
            thumb = appui.Rectangle() \
                .foreground_color("secondarySystemBackground") \
                .frame(width=58, height=58) \
                .background("secondarySystemBackground", corner_radius=8)
        return appui.Button(
            action=open,
            content=appui.VStack([
                thumb,
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
        url = img_src(s["link"])
        if url:
            content = appui.AsyncImage(url=url, content_mode="fit") \
                .frame(max_width=appui.infinity, max_height=appui.infinity)
        else:
            # 未准备好的大图：占位加载指示，路径补准备后由重建填充
            content = appui.ProgressView() \
                .frame(max_width=appui.infinity, max_height=appui.infinity)
        pages.append(appui.Tab(content=content, tag=i))
    if not pages:
        return appui.VStack([
            appui.ContentUnavailableView(
                "没有样片", system_image="photo.on.rectangle"),
            appui.Button("关闭", action=close_sample),
        ], spacing=12).padding(bottom=24)
    index = max(0, min(int(state.sample_index), len(pages) - 1))
    gallery = appui.VStack([
        appui.TabView(tabs=pages, selection=state.bind.sample_index,
                      on_change=on_sample_page_change)
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

    输入内容由 State.keyword 承载（searchable 绑定），提交时规整番号格式。
    """
    kw = norm_keyword(state.keyword or "")
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
        display_page_view(HOME_VID, titled=False),
        path=PATH_MOVIES,
        destinations=_LIST_DESTINATIONS,
    ).on_appear(action=load_home_once).id("movies")

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
    ).on_appear(action=load_fav_once).id("fav")

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
                appui.Toggle("视频默认静音", is_on=SETTINGS["mute"],
                             on_change=set_mute),
                appui.Picker("外部播放器",
                             selection=SETTINGS["player"],
                             options=list(EXTERNAL_PLAYERS.keys()),
                             on_change=set_player),
            ], header="播放"),
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


def _prewarm_tabs():
    """延迟预热女优/类型 tab 的数据（后台线程，错开启动网络高峰）。"""
    time.sleep(2.0)
    _pump(ACTRESS_VID)
    _pump(GENRE_VID)

def start():
    """冷启动：初始化后台线程并复位到影片 tab。"""
    init_background()
    reset_pending()
    # 15 个复位字段合并成一次重建（原来是 15 次）
    _batch_state(tab=0, keyword="", detail=None, detail_open=False,
                 detail_thumb="", panel="", panel_title="", play="",
                 panel_open=False, page_input="", page_input_vid="",
                 page_editing=False,
                 src_preview="", src_trailer="", src_video="", status="",
                 sample_index=0, name_text="", title_trans=False)
    DETAIL_STACKS.clear()      # 全部栈复位：各 tab 的详情状态一并清空
    PATH_MOVIES.pop_to_root()
    PATH_ACT.pop_to_root()
    PATH_GENRE.pop_to_root()
    PATH_FAV.pop_to_root()
    PATH_SETTINGS.pop_to_root()
    # 首页 / 收藏的首次拉取不在这里做：统一挂在各自 tab 的 .on_appear 上
    # （load_home_once / load_fav_once），四个 tab 的加载时机模型一致，
    # 不依赖「脚本只会被执行一次」的隐含时序
    # 冷启动 2 秒后预热女优/类型数据：首次切 tab 时数据已在/在路上，
    # 显著缩短切入等待；延迟错开启动时首页/收藏的网络高峰。
    # 放列表抓取池：休眠 2 秒期间不占用详情/翻译的池位
    _FETCH_POOL.submit(_prewarm_tabs)

# 首次进入 tab 才预加载（避免启动时并发请求过多）
_HOME_LOADED = False
_FAV_LOADED = False
_ACTRESS_LOADED = False
_GENRE_LOADED = False

def load_home_once():
    global _HOME_LOADED
    if _HOME_LOADED:
        return
    _HOME_LOADED = True
    _pump(HOME_VID)

def load_fav_once():
    global _FAV_LOADED
    if _FAV_LOADED:
        return
    _FAV_LOADED = True
    _pump(FAV_VID)

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
    clear_push_guard_prefix("detail:")   # 切 tab 已退回列表：允许重新进入同一详情
    state.detail_open = False
    note_nav_action()
    path.pop_to_root()      # 整条导航链（含多层详情）回到主页面

def set_tab(v):
    """记录当前标签页：确保 State 与界面选择一致，重建时停留在最后切换的标签页。"""
    global _LAST_TAB, _LAST_TAB_SWITCH, _TAB_IMG_FLUSHED
    try:
        v = int(v)
    except Exception:
        pass
    switched = v != _LAST_TAB
    leave_tab_reset(_LAST_TAB)
    reset_page_inputs()         # 切了 tab：未提交的页码输入作废
    _LAST_TAB = v
    if state.tab != v:
        state.tab = v       # 双向绑定通常已写入：同值再写会触发多余重建
    if switched:
        # 打开切换宽限窗：转场期间及其后的挂起重建推迟到窗口之外
        # （此前只有 _sync_dirty 兜底分支会更新 _LAST_TAB_SWITCH，正常
        #   on_change 路径漏更新，TAB_RELOAD_GRACE 形同虚设）
        _LAST_TAB_SWITCH = time.time()
        _TAB_IMG_FLUSHED = False     # 新 tab 首刷豁免重新生效
        # 切换重建已按当前数据渲染新 tab：滞留脏标记随之作废，
        # 避免切入后再来一次内容不变的重建（表现为整页闪一下）
        _drop_stale_dirty()
        # 新 tab 的预加载由切入时按需补足（后台轮询只覆盖可见展示位）
        root = TAB_ROOT_VIDS.get(v)
        if root in VIEWS:
            _pump(root)

def _tab_content(tag, builder):
    """只构建当前选中 tab 的真实内容，其余 tab 用轻量占位。

    AppUI 每次状态变化都会重新执行 body()，若 5 个 tab 全量构建，
    网格单元格 / 类型页上百个分类按钮 / 设置页表单每轮都要重造一遍。
    非选中 tab 本次重建不可见，返回空占位即可；切回时按 state.tab
    构建真实内容，导航位置由 NavigationPath 保留。

    构建期只读 State（不写状态、不做副作用）。
    """
    if state.tab != tag:
        return appui.Text("")
    return builder()

def wide_button(label, action, prominent=False):
    """等宽操作按钮（详情页 / 播放面板共用）。

    文字不折行（自动缩字号）、同排均分宽度；min_height=44 保证触控目标
    达到 iOS 建议的最小尺寸（原来 34pt 偏小）。
    """
    return appui.Button(
            content=appui.Text(label).line_limit(1).minimum_scale_factor(0.5),
            action=action,
        ) \
        .button_style("bordered_prominent" if prominent else "bordered") \
        .frame(min_height=44, max_width=appui.infinity)

def open_player_panel():
    state.panel_open = True

def close_player_panel():
    state.panel_open = False

def player_accessory_view():
    """TabView 底部常驻播放条（官方底部附件模式）：显示在播内容，点击展开面板。"""
    return appui.HStack([
        appui.VStack([
            appui.Label(state.panel_title or "正在播放",
                        system_image="play.circle.fill")
                .font("subheadline").bold().line_limit(1),
            appui.Text((state.play or "播放中") + " · 点击展开")
                .font("caption").foreground_color("secondaryLabel"),
        ], alignment="leading", spacing=2)
            .frame(max_width=appui.infinity, alignment="leading"),
        appui.Label("", system_image="chevron.up")
            .foreground_color("secondaryLabel"),
    ], spacing=10).padding(horizontal=14, vertical=10)

def player_panel_view():
    """播放面板（系统 sheet）：播放器 + 操作按钮。

    圆角、拖拽条、下拉关闭与 detents 全部交给系统 sheet 处理，
    不再把 VideoPlayer 塞进详情页的可滚动列表（重型媒体视图放稳定区域）。
    """
    rows = [appui.Text(state.panel_title or "播放").font("subheadline").bold().line_limit(2),
            appui.VideoPlayer(player=get_player(), autoplay=True,
                              pause_on_disappear=False).frame(height=220)]
    if state.play == "完整视频":
        rows.append(appui.HStack([
            wide_button("外部播放", open_external_player),
            wide_button("复制链接", copy_video_link),
        ], spacing=8))
    rows.append(appui.HStack([
        wide_button("关闭播放", clear_panel),
        wide_button("收起面板", close_player_panel),
    ], spacing=8))
    return appui.NavigationStack(
        appui.Form([appui.Section(rows, header="播放中")]).navigation_title("播放")
    )

def make_body():
    tabs = appui.TabView(
        tabs=[
            appui.Tab("影片", system_image="play.rectangle",
                      content=_tab_content(0, movies_tab), tag=0),
            appui.Tab("女优", system_image="person.2",
                      content=_tab_content(1, actress_tab), tag=1),
            appui.Tab("收藏", system_image="star",
                      content=_tab_content(2, fav_tab), tag=2),
            appui.Tab("类型", system_image="tag",
                      content=_tab_content(3, genre_tab), tag=3),
            appui.Tab("设置", system_image="gear",
                      content=_tab_content(4, settings_tab), tag=4),
        ],
        selection=state.bind.tab,
        on_change=set_tab,
    )
    if state.panel:
        # 有播放会话时才挂底部常驻条；展开面板由系统 sheet 呈现
        tabs = tabs.tab_view_bottom_accessory(
            content=player_accessory_view().content_shape("rect")
                .on_tap(open_player_panel))
    return tabs.sheet(
        is_presented=state.panel_open,
        on_dismiss=close_player_panel,
        content=player_panel_view,
        detents="medium_large",
        drag_indicator="visible",
    )

start()

def body():
    return make_body()

appui.run(body, state=state, presentation="fullscreen_with_close")
