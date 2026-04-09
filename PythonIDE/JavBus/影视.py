import html
import json
import queue
import re
import threading
from urllib.parse import parse_qs, unquote, urlparse

import dialogs
import requests
import ui

try:
    from objc_util import on_main_thread
except Exception:
    def on_main_thread(func):
        return func


# ===== 配置 =====
BASE_URL = "https://naixxzy.com"
API_URL = BASE_URL + "/api.php/provide/vod/"

session = requests.Session()
session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
            "Mobile/15E148 Safari/604.1"
        )
    }
)


# ===== 图片缓存 =====
image_cache = {}
_image_job_queue = queue.Queue()
_image_worker_started = False
_image_worker_lock = threading.Lock()


@on_main_thread
def _apply_image(image_view, image):
    try:
        image_view.image = image
    except Exception:
        pass


@on_main_thread
def _apply_image_placeholder(image_view):
    try:
        image_view.background_color = "#f0f0f0"
        if getattr(image_view, "_placeholder_added", False):
            return
        label = ui.Label(frame=(0, 0, image_view.width, image_view.height))
        label.text = "▶"
        label.font = ("System", 24)
        label.text_color = "#007AFF"
        label.alignment = ui.ALIGN_CENTER
        try:
            label.touch_enabled = False
        except Exception:
            pass
        image_view.add_subview(label)
        image_view._placeholder_added = True
    except Exception:
        pass


def _image_worker_loop():
    while True:
        job = _image_job_queue.get()
        try:
            if job is None:
                return

            url, image_view = job
            if url in image_cache:
                _apply_image(image_view, image_cache[url])
                continue

            try:
                response = session.get(url, timeout=8)
                response.raise_for_status()
                image = ui.Image.from_data(response.content)
                image_cache[url] = image
                _apply_image(image_view, image)
            except Exception:
                _apply_image_placeholder(image_view)
        finally:
            _image_job_queue.task_done()


def _ensure_image_worker():
    global _image_worker_started
    with _image_worker_lock:
        if _image_worker_started:
            return
        worker = threading.Thread(target=_image_worker_loop, daemon=True)
        worker.start()
        _image_worker_started = True


def load_image_async(url, image_view):
    if not url or not url.startswith("http"):
        return

    if url in image_cache:
        _apply_image(image_view, image_cache[url])
        return

    _ensure_image_worker()
    _image_job_queue.put((url, image_view))


# ===== 状态 =====
state = {
    "pg": 1,
    "type": None,
    "tabs": [],
    "searching": False,
    "keyword": "",
}


# ===== 播放地址解析 =====
HTTP_URL_RE = re.compile(r'https?://[^\s<>"\']+|//[^\s<>"\']+|www\.[^\s<>"\']+')
MEDIA_HINTS = (".m3u8", ".mp4", ".m4v", ".mov", ".webm", ".flv", ".avi", ".mkv")


def normalize_url(url):
    if not url:
        return ""

    value = str(url).strip()
    value = value.replace("\\/", "/").replace("&amp;", "&")
    value = value.strip(" '\"\t\r\n")

    if value.startswith("//"):
        value = "https:" + value
    elif value.startswith("/"):
        value = BASE_URL.rstrip("/") + value
    elif value.startswith("www."):
        value = "https://" + value

    return value


def split_candidate_urls(text):
    if not text:
        return []

    matches = HTTP_URL_RE.findall(text)
    if matches:
        return matches

    compact = text.strip()
    if compact.startswith("/"):
        return [compact]
    if " " not in compact and "\n" not in compact and "/" in compact:
        return [compact]
    return []


def score_play_url(url):
    lower = url.lower()
    score = 0

    if lower.startswith("https://"):
        score += 40
    elif lower.startswith("http://"):
        score += 30

    if ".m3u8" in lower:
        score += 500
    elif any(ext in lower for ext in (".mp4", ".m4v", ".mov", ".webm")):
        score += 450
    elif any(ext in lower for ext in (".flv", ".avi", ".mkv")):
        score += 350

    if "m3u8" in lower:
        score += 60
    if "index" in lower:
        score += 10

    if "?url=" in lower or "jiexi" in lower or "parser" in lower:
        score -= 80
    if "player/" in lower and not any(ext in lower for ext in MEDIA_HINTS):
        score -= 40

    return score


def extract_nested_media_url(url):
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
    except Exception:
        return ""

    for key in ("url", "vid", "play", "source"):
        for value in query.get(key, []):
            nested = normalize_url(unquote(value))
            if nested.startswith("http") and nested != url:
                return nested

    return ""


def extract_play_urls(play_url_raw):
    if not play_url_raw:
        return []

    raw = str(play_url_raw).strip()
    groups = [part.strip() for part in raw.split("$$$") if part.strip()] or [raw]

    urls = []
    seen = set()

    for group in groups:
        episodes = [part.strip() for part in group.split("#") if part.strip()] or [group]

        for episode in episodes:
            candidates = episode.split("$")[1:] if "$" in episode else [episode]

            for candidate in candidates:
                for url in split_candidate_urls(candidate):
                    final_url = normalize_url(url)
                    nested_url = extract_nested_media_url(final_url)

                    for picked_url in (nested_url, final_url):
                        if not picked_url or picked_url in seen:
                            continue
                        seen.add(picked_url)
                        urls.append(picked_url)

    urls.sort(key=score_play_url, reverse=True)
    return urls


def extract_best_play_url(play_url_raw):
    urls = extract_play_urls(play_url_raw)
    return urls[0] if urls else ""


# ===== 数据请求 =====
def get_config():
    try:
        response = session.get(API_URL, params={"ids": "recommend"}, timeout=10)
        response.raise_for_status()
        data = response.json()

        tabs = []
        for index, item in enumerate(data.get("class", [])):
            type_name = item.get("type_name", "")
            if "精" in type_name or index >= 12:
                continue
            tabs.append(
                {
                    "name": type_name[:6] + "..." if len(type_name) > 6 else type_name,
                    "id": str(item.get("type_id", "")),
                    "full_name": type_name or "未命名分类",
                }
            )

        if tabs:
            state["tabs"] = tabs
            state["type"] = tabs[0]["id"]
            return True
    except Exception:
        pass

    state["tabs"] = [
        {"name": "电影", "id": "1", "full_name": "电影"},
        {"name": "电视剧", "id": "2", "full_name": "电视剧"},
        {"name": "动漫", "id": "3", "full_name": "动漫"},
    ]
    state["type"] = "1"
    return False


def get_videos(page=1):
    params = {"ac": "videolist", "pg": page}
    if state["searching"]:
        params["wd"] = state["keyword"]
    else:
        params["t"] = state["type"]

    response = session.get(API_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    videos = []
    for item in data.get("list", []):
        raw_play_url = item.get("vod_play_url", "") or ""
        play_urls = extract_play_urls(raw_play_url)

        pic = item.get("vod_pic", "") or ""
        if "?" in pic:
            pic = pic.split("?", 1)[0]

        videos.append(
            {
                "title": item.get("vod_name", "无标题"),
                "img": normalize_url(pic) if pic else "",
                "url": play_urls[0] if play_urls else "",
                "play_urls": play_urls,
                "duration": item.get("vod_duration", "") or "",
                "raw_url": raw_play_url,
            }
        )

    return videos


def build_player_html(video_url, title):
    safe_title = html.escape(title or "视频", quote=False)
    js_url = json.dumps(video_url)

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      background: #000;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    .wrap {{
      position: fixed;
      inset: 0;
      background: #000;
    }}
    video {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #000;
    }}
    .hint {{
      position: fixed;
      left: 16px;
      right: 16px;
      bottom: 26px;
      z-index: 10;
      text-align: center;
      color: #fff;
      font-size: 15px;
      line-height: 1.5;
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(0, 0, 0, 0.56);
      backdrop-filter: blur(8px);
    }}
    .title {{
      position: fixed;
      top: 18px;
      left: 16px;
      right: 16px;
      z-index: 10;
      color: rgba(255, 255, 255, 0.9);
      font-size: 14px;
      text-align: center;
      pointer-events: none;
    }}
  </style>
</head>
<body>
  <div class="title">{safe_title}</div>
  <div class="wrap">
    <video id="player" controls playsinline webkit-playsinline preload="auto"></video>
  </div>
  <div class="hint" id="hint">正在加载视频，如果没有自动播放，请轻点画面开始播放</div>

  <script>
    const url = {js_url};
    const player = document.getElementById('player');
    const hint = document.getElementById('hint');

    function setHint(text) {{
      hint.innerHTML = text;
      hint.style.display = 'block';
    }}

    function hideHint() {{
      hint.style.display = 'none';
    }}

    player.src = url;

    player.addEventListener('loadedmetadata', function() {{
      setHint('视频已加载，轻点画面开始播放');
    }});

    player.addEventListener('canplay', function() {{
      setHint('轻点画面开始播放');
    }});

    player.addEventListener('play', function() {{
      hideHint();
    }});

    player.addEventListener('pause', function() {{
      setHint('已暂停，轻点画面继续播放');
    }});

    player.addEventListener('waiting', function() {{
      setHint('正在缓冲...');
    }});

    player.addEventListener('error', function() {{
      const code = player.error ? player.error.code : 'unknown';
      setHint('播放失败（错误码: ' + code + '）<br>轻点画面重试');
    }});

    function tryPlay() {{
      player.play().then(function() {{
        hideHint();
      }}).catch(function() {{
        setHint('当前源未自动播放，请再轻点一次画面');
      }});
    }}

    document.body.addEventListener('click', function() {{
      tryPlay();
    }});

    window.addEventListener('load', function() {{
      player.load();
      tryPlay();
    }});
  </script>
</body>
</html>"""


# ===== 主应用 =====
class VideoApp(ui.View):
    def __init__(self):
        super().__init__()
        self.background_color = "white"
        self.name = "视频播放"
        self.videos = []
        self.current_page = 1
        self._loading_more = False
        self._started = False
        self._hide_loading_token = 0
        self._load_generation = 0
        self._active_request_token = 0
        self._has_more_videos = True
        self._selected_tab_index = 0
        self._active_player_view = None

        self.search_container = ui.View()
        self.search_container.background_color = "#f8f8f8"
        self.add_subview(self.search_container)

        self.search_field = ui.TextField()
        self.search_field.placeholder = "搜索视频..."
        self.search_field.border_width = 1
        self.search_field.border_color = "#ddd"
        self.search_field.corner_radius = 15
        self.search_field.action = self.on_search
        self.search_container.add_subview(self.search_field)

        self.search_btn = ui.Button()
        self.search_btn.title = "搜索"
        self.search_btn.background_color = "#007AFF"
        self.search_btn.tint_color = "white"
        self.search_btn.corner_radius = 15
        self.search_btn.action = self.on_search
        self.search_container.add_subview(self.search_btn)

        self.tabs_scroll = ui.ScrollView()
        self.tabs_scroll.shows_horizontal_scroll_indicator = True
        self.tabs_scroll.bounces = True
        self.add_subview(self.tabs_scroll)

        self.video_scroll = ui.ScrollView()
        self.video_scroll.background_color = "#f5f5f5"
        self.video_scroll.delegate = self
        self.add_subview(self.video_scroll)

        self.loading_label = ui.Label()
        self.loading_label.text = "加载中..."
        self.loading_label.text_color = "#666"
        self.loading_label.alignment = ui.ALIGN_CENTER
        self.loading_label.hidden = True
        self.add_subview(self.loading_label)

    def did_load(self):
        super().did_load()
        self.start_if_needed()

    def start_if_needed(self):
        if self._started:
            return
        self._started = True
        self.show_loading(True)
        self.create_tabs()
        self.load_videos()

    def layout(self):
        width, height = self.width, self.height
        if width <= 0 or height <= 0:
            return

        self.search_container.frame = (0, 0, width, 70)
        self.search_field.frame = (15, 15, width - 130, 40)
        self.search_btn.frame = (width - 110, 15, 95, 40)

        self.tabs_scroll.frame = (0, 70, width, 50)
        self.video_scroll.frame = (0, 120, width, height - 120)
        self.loading_label.frame = (0, height - 50, width, 30)
        if self._active_player_view is not None:
            self._active_player_view.frame = (0, 0, width, height)

    def create_tabs(self):
        for subview in list(self.tabs_scroll.subviews):
            subview.remove_from_superview()

        x = 10
        for index, tab in enumerate(state["tabs"]):
            button = ui.Button(frame=(x, 10, 80, 30))
            button.title = tab["name"]
            button.tag = index
            button.background_color = "#007AFF" if index == 0 else "#e8e8e8"
            button.tint_color = "white" if index == 0 else "#333"
            button.corner_radius = 15
            button.border_width = 1 if index == 0 else 0
            button.border_color = "#0055CC"
            button.action = self.on_tab_click
            self.tabs_scroll.add_subview(button)
            x += 90

        self.tabs_scroll.content_size = (x, 50)
        self._apply_tab_selection(self._selected_tab_index)

    def _apply_tab_selection(self, selected_index=None):
        self._selected_tab_index = selected_index
        for subview in self.tabs_scroll.subviews:
            if not isinstance(subview, ui.Button):
                continue
            is_selected = selected_index is not None and subview.tag == selected_index
            subview.background_color = "#007AFF" if is_selected else "#e8e8e8"
            subview.tint_color = "white" if is_selected else "#333"
            subview.border_width = 1 if is_selected else 0
            subview.border_color = "#0055CC"

    def _close_active_player(self):
        if self._active_player_view is None:
            return
        try:
            self._active_player_view.remove_from_superview()
        except Exception:
            pass
        self._active_player_view = None

    def _invalidate_pending_requests(self):
        self._load_generation += 1
        self._active_request_token += 1
        self._loading_more = False

    def _reset_content_state(self):
        self._close_active_player()
        self._invalidate_pending_requests()
        self._has_more_videos = True
        state["pg"] = 1
        self.current_page = 1

    def on_tab_click(self, sender):
        self._apply_tab_selection(sender.tag)

        state["type"] = state["tabs"][sender.tag]["id"]
        state["searching"] = False
        state["keyword"] = ""
        self._reset_content_state()
        self.show_loading(True)
        self.load_videos()

    def on_search(self, sender):
        keyword = (self.search_field.text or "").strip()
        if not keyword:
            dialogs.hud_alert("请输入关键词", duration=1.0)
            return

        state["keyword"] = keyword
        state["searching"] = True
        self._apply_tab_selection(None)
        self._reset_content_state()
        self.show_loading(True)
        self.load_videos()

    @on_main_thread
    def show_loading(self, show):
        self.loading_label.hidden = not show
        if show:
            self.loading_label.text = "加载中..."

    def _schedule_hide_loading(self, seconds=1.2):
        self._hide_loading_token += 1
        token = self._hide_loading_token

        def hide():
            if token != self._hide_loading_token:
                return
            self.loading_label.hidden = True

        try:
            ui.delay(seconds, hide)
        except Exception:
            hide()

    def load_videos(self):
        if self._loading_more or not self._has_more_videos:
            return

        self._loading_more = True
        page = state["pg"]
        generation = self._load_generation
        request_token = self._active_request_token + 1
        self._active_request_token = request_token

        def load_task():
            try:
                videos = get_videos(page)
                self._apply_video_page(page, videos, generation, request_token)
            except Exception as exc:
                self._show_load_error(f"加载失败: {exc}", generation, request_token)

        threading.Thread(target=load_task, daemon=True).start()

    @on_main_thread
    def _apply_video_page(self, page, videos, generation, request_token):
        try:
            if generation != self._load_generation or request_token != self._active_request_token:
                return

            if page == 1:
                self.videos = videos
                for subview in list(self.video_scroll.subviews):
                    subview.remove_from_superview()
            else:
                self.videos.extend(videos)

            self.render_videos(videos, clear=(page == 1))

            if videos:
                state["pg"] = page + 1
                self.current_page = state["pg"]
                self._has_more_videos = True
                self.loading_label.text = f"已加载 {len(self.videos)} 个视频"
            else:
                self._has_more_videos = False
                self.loading_label.text = (
                    "没有找到相关视频" if page == 1 and state["searching"] else "没有更多视频"
                )

            self._schedule_hide_loading(1.2)
        finally:
            if request_token == self._active_request_token:
                self._loading_more = False

    @on_main_thread
    def _show_load_error(self, message, generation, request_token):
        if generation != self._load_generation or request_token != self._active_request_token:
            return
        self.loading_label.text = message or "加载失败"
        self._schedule_hide_loading(2.0)
        self._loading_more = False

    def _disable_touch_on_subviews(self, root):
        try:
            root.touch_enabled = False
        except Exception:
            pass
        for child in getattr(root, "subviews", []) or []:
            self._disable_touch_on_subviews(child)

    def _make_video_tap_handler(self, video_index):
        def _handler(sender):
            self.play_video_by_index(video_index)

        return _handler

    def render_videos(self, videos, clear=False):
        if clear:
            y = 10
        else:
            current_height = self.video_scroll.content_size[1]
            y = current_height if current_height > 10 else 10

        card_width = (self.width - 30) / 2
        card_height = 200
        x = 10

        for index, video in enumerate(videos):
            video_index = len(self.videos) - len(videos) + index

            card = ui.View(frame=(x, y, card_width, card_height))
            card.background_color = "white"
            card.corner_radius = 10
            card.border_width = 1
            card.border_color = "#eee"

            img_view = ui.ImageView(frame=(5, 5, card_width - 10, 120))
            img_view.background_color = "#f0f0f0"
            img_view.content_mode = ui.CONTENT_SCALE_ASPECT_FILL
            img_view.corner_radius = 6

            play_overlay = ui.View(frame=(0, 0, img_view.width, img_view.height))
            play_overlay.background_color = "#00000033"
            play_overlay.corner_radius = 6

            play_icon = ui.Label(frame=(0, 0, img_view.width, img_view.height))
            play_icon.text = "▶"
            play_icon.font = ("System", 28)
            play_icon.text_color = "white"
            play_icon.alignment = ui.ALIGN_CENTER
            play_overlay.add_subview(play_icon)
            img_view.add_subview(play_overlay)

            if video.get("img") and video["img"].startswith("http"):
                load_image_async(video["img"], img_view)

            if video.get("duration"):
                duration_label = ui.Label(
                    frame=(img_view.width - 55, img_view.height - 30, 50, 20)
                )
                duration_label.text = video["duration"]
                duration_label.background_color = "#000000AA"
                duration_label.text_color = "white"
                duration_label.font = ("System", 10)
                duration_label.alignment = ui.ALIGN_CENTER
                duration_label.corner_radius = 4
                img_view.add_subview(duration_label)

            card.add_subview(img_view)

            title_label = ui.Label(frame=(5, 130, card_width - 10, 40))
            title_text = video["title"]
            if len(title_text) > 30:
                title_text = title_text[:30] + "..."
            title_label.text = title_text
            title_label.number_of_lines = 2
            title_label.font = ("System", 13)
            title_label.text_color = "#333"
            card.add_subview(title_label)

            play_label = ui.Label(frame=(0, 175, card_width, 20))
            play_label.text = "点击播放"
            play_label.text_color = "#007AFF"
            play_label.font = ("System-Bold", 12)
            play_label.alignment = ui.ALIGN_CENTER
            card.add_subview(play_label)

            hit_button = ui.Button(frame=(0, 0, card_width, card_height))
            hit_button.background_color = (1, 1, 1, 0.01)
            hit_button.tint_color = (1, 1, 1, 0.01)
            hit_button.border_width = 0
            hit_button.corner_radius = 10
            hit_button.action = self._make_video_tap_handler(video_index)
            card.add_subview(hit_button)

            self._disable_touch_on_subviews(img_view)
            self._disable_touch_on_subviews(title_label)
            self._disable_touch_on_subviews(play_label)

            self.video_scroll.add_subview(card)

            x += card_width + 10
            if x > self.width - card_width:
                x = 10
                y += card_height + 10

        new_height = y + card_height + 10
        self.video_scroll.content_size = (self.width, new_height)

    @on_main_thread
    def play_video_by_index(self, video_index):
        if not (0 <= video_index < len(self.videos)):
            dialogs.hud_alert("视频数据错误", duration=1.0)
            return

        video = self.videos[video_index]
        url = (video.get("url") or "").strip()
        if not url:
            raw_preview = (video.get("raw_url") or "").strip()
            if len(raw_preview) > 160:
                raw_preview = raw_preview[:160] + "..."
            dialogs.alert(
                "无法播放",
                "没有解析到可播放地址。\n\n原始播放字段：\n%s" % (raw_preview or "空"),
                "确定",
                hide_cancel_button=True,
            )
            return

        self.loading_label.hidden = False
        self.loading_label.text = "正在打开播放器..."
        self.create_video_player(url, video["title"])

    def play_video(self, sender):
        video_index = getattr(sender, "tag", -1)
        self.play_video_by_index(video_index)

    @on_main_thread
    def create_video_player(self, video_url, title):
        self._close_active_player()

        player_view = ui.View()
        player_view.background_color = "black"
        player_view.name = title[:30] + "..." if len(title) > 30 else title

        width = self.width or ui.get_screen_size()[0]
        height = self.height or ui.get_screen_size()[1]
        player_view.frame = (0, 0, width, height)
        player_view.flex = "WH"

        webview = ui.WebView(frame=player_view.bounds)
        webview.flex = "WH"
        player_view.add_subview(webview)

        close_btn = ui.Button(frame=(12, 52, 72, 36))
        close_btn.title = "关闭"
        close_btn.background_color = "#CC0000"
        close_btn.tint_color = "white"
        close_btn.corner_radius = 8

        def close_player(sender):
            self._close_active_player()

        close_btn.action = close_player
        player_view.add_subview(close_btn)

        html_content = build_player_html(video_url, title)
        webview.load_html(html_content, base_url=BASE_URL)

        self.add_subview(player_view)
        self.bring_subview_to_front(player_view)
        self._active_player_view = player_view
        dialogs.hud_alert("正在加载视频...", duration=1.0)
        self.loading_label.hidden = True

    def scrollview_did_scroll(self, scrollview):
        if not self._has_more_videos:
            return
        if scrollview.content_offset[1] + scrollview.height > scrollview.content_size[1] - 120:
            if self._loading_more or not self.loading_label.hidden:
                return
            self.show_loading(True)
            self.load_videos()


if __name__ == "__main__":
    get_config()

    app = VideoApp()
    screen_width, screen_height = ui.get_screen_size()
    app.frame = (0, 0, screen_width, screen_height)
    app.present("sheet", hide_title_bar=True)
    app.start_if_needed()
