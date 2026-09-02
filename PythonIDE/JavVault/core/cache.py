# -*- coding: utf-8 -*-
"""封面的后台下载与磁盘/内存缓存（JavBus/DMM 图防盗链需要 Referer 头）。

关键设计：AsyncImage 的 url 从第一次渲染到结束始终保持同一个 `file://` 路径
（AppUI 要求 file:// 指向已存在的正规文件）。首次请求时用占位小图同步落盘，
下载完成后原子替换成真实封面。这样：
  1. url 恒定 → SwiftUI 不会因为 http/file 跳变而强制重载 → 不闪烁；
  2. 文件始终存在 → AsyncImage 校验(must_exist)永不失败 → 不崩溃。
"""

import hashlib
import os
import struct
import tempfile
import threading
import time
import zlib
from collections import OrderedDict

import network

from core.config import BASE, HEADERS

# 已成功下载到磁盘的 url（有界，防止长时间运行持续占用内存）
_DOWNLOADED = OrderedDict()
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
# 并发下载线程数
WORKERS = 4
# 本次循环中是否有图片下载完成（主线程据此决定是否刷新列表）
_RELOAD_DIRTY = False
# 最近一次图片下载活动时刻（用于去抖：一段时间无新下载完成才刷新）
_LAST_ACTIVITY = 0.0
# worker 是否已启动
_started = False

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
    """
    if not src:
        return ""
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
    global _started
    if _started:
        return
    _started = True
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
