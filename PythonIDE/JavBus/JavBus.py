# JavBus 简化版 - 只保留首页功能
# ================================================================
# 简化说明：
# 1. 只保留"首页"Tab，其他Tab设为空
# 2. 首页包含搜索框和影片网格布局
# 3. 参考JavBus.js的网络数据获取逻辑
# 4. 只使用javbus.com网站，不使用其他网站
# ================================================================

import appui
import ui
import os
import json
import re
import requests
import threading
import time
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# ================================================================
# 常量与配置
# ================================================================

CONFIG = {
    "BASE_URL": "https://www.javbus.com/",
    "DATA_FILE": "JavBusBackup.json",
    "COLUMNS": 3,
    "SPACING": 1,
    "GRID_HEIGHT": 200,
    "TIMEOUT": 10,
    "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# 颜色方案
COLORS = {
    "primary": "#007AFF",
    "success": "#34C759",
    "warning": "#FF9500",
    "danger": "#FF3B30",
    "light_gray": "#F3F3F3",
    "text_primary": "#000000",
    "text_secondary": "#666666",
    "hd_blue": "#7294B1",
    "subtitle_orange": "#F2B867",
    "recommend_pink": "#B20083",
}

# ================================================================
# 全局状态管理
# ================================================================

state = appui.State(
    # 搜索与主列表
    search_keyword="",
    search_mode="home",  # "home" / "search"
    current_page=0,
    movie_list=[],  # 影片数据列表
    
    # UI 状态
    loading=False,
    show_search_tips=True,
    active_tab=0,
    
    # 加载状态
    has_more=True,
    page_reached_bottom=False,
    
    # 配置状态
    uncensored=False,  # 是否为无码版本

    # 首页来源（对齐 JS 的 homepage / homeSearchPage）
    homepage="https://www.javbus.com/",
    home_search_page="https://www.javbus.com/search/",
    again=0,
)

# ================================================================
# 模型 / 数据结构
# ================================================================

class MovieData:
    """影片数据模型"""
    def __init__(self, code, title, cover_url, link="", hd=False, subtitle=False, recommend=False):
        self.code = code
        self.title = title
        self.cover_url = cover_url
        self.link = link  # 保存完整的影片链接
        self.hd = hd
        self.subtitle = subtitle
        self.recommend = recommend

# ================================================================
# 工具函数
# ================================================================

def normalize_code(raw_code):
    """规范化番号格式 - 参考JavBus.js"""
    code = raw_code.strip()
    if not code:
        return ""
    
    # 移除空格
    code = re.sub(r'\s+', '', code)
    
    # 在字母与数字之间插入-，如果没有-且不在fc后面
    code = re.sub(r'([a-zA-Z])(?=\d)(?!-)(?<!fc)', r'\1-', code)
    
    # 在数字与字母之间插入-，如果没有-
    code = re.sub(r'(\d)(?=[a-zA-Z])(?!-)', r'\1-', code)
    
    return code.upper()

def get_homepage():
    """获取当前首页URL - 参考JavBus.js"""
    if state.uncensored:
        return "https://www.javbus.com/uncensored/"
    else:
        return "https://www.javbus.com/"


def sync_home_source():
    """同步 JS 中 homepage/homeSearchPage 状态。"""
    state.homepage = get_homepage()
    state.home_search_page = state.homepage + "search/"

# ================================================================
# 网络请求模块 - 参考JavBus.js的实现
# ================================================================

_session = None
_age_verified = False
_webview_fetcher = None


def _run_on_main_thread_wait(fn):
    done = threading.Event()
    out = {"error": None}

    def _wrapped():
        try:
            fn()
        except Exception as e:
            out["error"] = e
        finally:
            done.set()

    try:
        ui.delay(0, _wrapped)
    except Exception:
        _wrapped()

    done.wait(timeout=2)
    if not done.is_set():
        raise RuntimeError("main-thread dispatch timeout")
    if out["error"]:
        raise out["error"]


class WebViewFetcher:
    def __init__(self):
        self._lock = threading.Lock()
        self._webview = None
        self._verify_max = 3
        self._build_webview()

    def _build_webview(self):
        def _create():
            if self._webview is not None:
                return
            self._webview = ui.WebView(frame=(0, 0, 1, 1))
            self._webview.hidden = True
            self._webview.delegate = self

        _run_on_main_thread_wait(_create)

    def _is_age_page(self, title="", url="", html=""):
        text = f"{title} {url} {html}".lower()
        markers = ["age verification", "driver-verify", "我已經成年", "是否已經成年"]
        return any(m in text for m in markers)

    def _auto_submit_age(self):
        js = """
        (function() {
          try {
            var cb = document.querySelector('#form1 input[type="checkbox"]') || document.querySelector('input[type="checkbox"]');
            if (cb && !cb.checked) {
              cb.checked = true;
              cb.dispatchEvent(new Event('change', {bubbles: true}));
            }
            var btn = document.querySelector('#submit') || document.querySelector('input[type="submit"],button[type="submit"],button.submit,input.submit');
            if (btn) {
              btn.disabled = false;
              btn.removeAttribute('disabled');
              btn.click();
              return 'submitted-button';
            }
            var form = document.querySelector('#form1') || document.querySelector('form');
            if (form) {
              form.submit();
              return 'submitted-form';
            }
            return 'no-form';
          } catch (e) {
            return 'error:' + e;
          }
        })();
        """
        return self._webview.eval_js(js)

    def fetch_html(self, url, timeout=12):
        with self._lock:
            def _load():
                self._webview.stop()
                self._webview.load_url(url)

            _run_on_main_thread_wait(_load)
            deadline = time.time() + timeout
            verify_tries = 0
            last = {"title": "", "url": url, "html": "", "ready": ""}

            while time.time() < deadline:
                snap = {}

                def _snapshot():
                    try:
                        snap["title"] = self._webview.eval_js("document.title") or ""
                    except Exception:
                        snap["title"] = ""
                    try:
                        snap["url"] = self._webview.eval_js("window.location.href") or ""
                    except Exception:
                        snap["url"] = ""
                    try:
                        snap["ready"] = self._webview.eval_js("document.readyState") or ""
                    except Exception:
                        snap["ready"] = ""
                    try:
                        snap["html"] = self._webview.eval_js("document.documentElement.outerHTML") or ""
                    except Exception:
                        snap["html"] = ""

                _run_on_main_thread_wait(_snapshot)

                if snap:
                    last.update(snap)

                if last["title"] or last["ready"]:
                    print(f"[WebView] 标题: {last['title']} | ready: {last['ready']}")
                    print(f"[WebView] URL: {last['url']}")

                if self._is_age_page(title=last["title"], url=last["url"], html=last["html"]):
                    if verify_tries < self._verify_max:
                        verify_tries += 1

                        submit_result = {"v": ""}

                        def _submit():
                            submit_result["v"] = self._auto_submit_age()

                        _run_on_main_thread_wait(_submit)
                        print(f"[WebView] 年龄验证自动提交: {submit_result['v']}, 第 {verify_tries} 次")
                        time.sleep(0.8)
                        continue

                    return {
                        "ok": False,
                        "html": last["html"],
                        "title": last["title"],
                        "url": last["url"],
                        "error": "age verification not passed",
                    }

                if last["ready"] in ("interactive", "complete") and len(last["html"]) > 500:
                    return {
                        "ok": True,
                        "html": last["html"],
                        "title": last["title"],
                        "url": last["url"],
                        "error": "",
                    }

                time.sleep(0.4)

            return {
                "ok": False,
                "html": last["html"],
                "title": last["title"],
                "url": last["url"],
                "error": "webview timeout",
            }


def _get_webview_fetcher():
    global _webview_fetcher
    if _webview_fetcher is None:
        _webview_fetcher = WebViewFetcher()
    return _webview_fetcher


def _is_age_verification_page(html):
    """判断页面是否为年龄验证页，避免误判 `page` 等普通文本。"""
    if not html:
        return False

    lowered = html.lower()
    markers = [
        "age verification",
        "age_verified",
        "over18",
        "jav_birth",
        "enter javbus",
        "i am 18",
    ]
    return any(marker in lowered for marker in markers)


def _set_age_cookies(session):
    """写入常见的年龄验证 Cookie。"""
    cookie_values = {
        "existmag": "all",
        "age_verified": "1",
        "over18": "1",
        "jav_birth": "1990-01-01",
    }
    # 先尽量清除服务端写入的 existmag=mag，避免冲突
    for c in list(session.cookies):
        if c.name == "existmag":
            try:
                session.cookies.clear(domain=c.domain, path=c.path, name=c.name)
            except Exception:
                pass

    # host-only cookie
    for name, value in cookie_values.items():
        try:
            session.cookies.set(name, value, path="/")
        except Exception:
            pass

    # domain cookie
    for domain in (".javbus.com", "www.javbus.com", "javbus.com"):
        for name, value in cookie_values.items():
            try:
                session.cookies.set(name, value, domain=domain, path="/")
            except Exception:
                pass


def _age_cookie_header():
    """与 JS 版本一致，显式发送 Cookie 请求头。"""
    return "existmag=all; age_verified=1; over18=1; jav_birth=1990-01-01"


def _request_with_age_cookie(session, url):
    """发送携带年龄 Cookie 的 GET 请求。"""
    return session.get(
        url,
        timeout=CONFIG["TIMEOUT"],
        headers={
            "Cookie": _age_cookie_header(),
            "Referer": "https://www.javbus.com/",
        },
    )


def _post_age_verification_form(session, html, current_url):
    """尝试按页面表单提交年龄验证。"""
    try:
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if not form:
            return False

        action = (form.get("action") or "").strip()
        if action.startswith("http"):
            post_url = action
        elif action.startswith("/"):
            post_url = "https://www.javbus.com" + action
        else:
            post_url = current_url

        payload = {}
        for field in form.find_all("input"):
            name = field.get("name")
            if not name:
                continue
            payload[name] = field.get("value", "")

        # 某些页面按钮字段在 button 里
        for button in form.find_all("button"):
            name = button.get("name")
            if not name:
                continue
            payload.setdefault(name, button.get("value", "1"))

        # 常见字段兜底
        payload.setdefault("over18", "1")
        payload.setdefault("age", "1")
        payload.setdefault("enter", "Enter")

        resp = session.post(
            post_url,
            data=payload,
            timeout=CONFIG["TIMEOUT"],
            headers={
                "Cookie": _age_cookie_header(),
                "Referer": "https://www.javbus.com/",
            },
        )
        resp.encoding = "utf-8"
        return resp.status_code == 200
    except Exception as e:
        print(f"提交年龄验证表单失败: {e}")
        return False

def get_session():
    """获取 HTTP Session - 参考JavBus.js"""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": CONFIG["USER_AGENT"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
    return _session

def verify_age():
    """年龄验证 - 处理javbus的年龄验证页面"""
    global _age_verified, _session
    
    if _age_verified:
        return True
    
    try:
        print("正在处理年龄验证...")
        session = get_session()

        # 先访问主页获取验证页面
        verify_url = "https://www.javbus.com/"
        _set_age_cookies(session)
        resp = _request_with_age_cookie(session, verify_url)
        resp.encoding = "utf-8"
        verify_url = resp.url or verify_url
        
        print(f"验证页面响应状态码: {resp.status_code}")
        
        # 打印当前Cookie（处理重复cookie的情况）
        try:
            print(f"当前Cookie: {dict(session.cookies)}")
        except:
            print("当前Cookie存在重复，使用迭代器")
            for name in session.cookies.list_domains():
                print(f"  Domain: {name}")
        
        # 解析验证页面
        verify_soup = BeautifulSoup(resp.text, "html.parser")
        print(f"验证页面标题: {verify_soup.title.text if verify_soup.title else '无标题'}")
        
        # 检查是否需要验证
        if _is_age_verification_page(resp.text):
            print("检测到年龄验证页面，尝试通过验证...")

            # 尝试查找验证表单
            forms = verify_soup.find_all("form")
            print(f"找到 {len(forms)} 个表单")

            for form in forms:
                action = form.get("action", "")
                print(f"表单action: {action}")
                # 查找表单中的按钮
                buttons = form.find_all("button")
                for btn in buttons:
                    print(f"  按钮: {btn.get_text(strip=True)}")

            # 直接按当前验证页提交表单（action 为空时应提交回当前 URL）
            if _post_age_verification_form(session, resp.text, verify_url):
                resp3 = _request_with_age_cookie(session, "https://www.javbus.com/page/1")
                resp3.encoding = "utf-8"
                if not _is_age_verification_page(resp3.text):
                    print("表单验证通过！")
                    _age_verified = True
                    return True

            print("无法通过年龄验证，继续尝试后续请求")

        _age_verified = True
        return True
        
    except Exception as e:
        print(f"年龄验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def build_url(mode, keyword, page=1):
    """构建请求URL - 参考JavBus.js"""
    sync_home_source()
    homepage = state.homepage
    
    if mode == "home":
        # 首页 - 尝试有码和无码版本
        if state.uncensored:
            return f"{homepage}page/{page}"
        else:
            # 先尝试有码，如果失败再切换到无码
            return f"{homepage}page/{page}"
    
    elif mode == "search":
        # 搜索 - 先规范化关键词
        keyword = normalize_code(keyword)
        return f"{state.home_search_page}{keyword}/{page}"
    
    return homepage

def parse_movie_list(html, homepage):
    """解析影片列表 HTML - 使用BeautifulSoup解析"""
    movies = []
    
    try:
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html, "html.parser")
        
        # 打印页面标题帮助调试
        if soup.title:
            print(f"页面标题: {soup.title.text}")
        
        # 查找所有movie-box元素
        movie_boxes = soup.find_all("a", class_="movie-box")
        print(f"找到 {len(movie_boxes)} 个 movie-box 元素")
        
        if not movie_boxes:
            print("未找到movie-box元素，尝试其他选择器...")
            # 尝试其他可能的选择器
            selectors = [
                ("div", "movie-box"),
                ("div", "item"),
                ("a", "video-item"),
            ]
            for tag, class_name in selectors:
                movie_boxes = soup.find_all(tag, class_=class_name)
                if movie_boxes:
                    print(f"找到 {len(movie_boxes)} 个 {tag}.{class_name} 元素")
                    break
        
        if not movie_boxes:
            # 如果还是没有，尝试查找包含日期的元素
            movie_boxes = soup.find_all("a", href=True)
            # 过滤出可能是影片的链接
            movie_boxes = [box for box in movie_boxes if box.get("href") and 
                         re.search(r'[A-Z]{2,}-?\d{3,}', box.get("href", ""))]
            print(f"通过链接过滤找到 {len(movie_boxes)} 个可能的影片")
        
        if not movie_boxes:
            print("未能找到任何影片元素")
            return []
        
        print(f"开始解析 {len(movie_boxes)} 个影片...")
        
        for box in movie_boxes:
            try:
                # 获取链接
                link = box.get("href", "").strip()
                if not link:
                    continue
                
                # 确保是完整URL
                if not link.startswith("http"):
                    if link.startswith("/"):
                        link = homepage + link.lstrip("/")
                    else:
                        link = homepage.rstrip("/") + "/" + link
                
                # 获取封面图片
                img = box.find("img")
                image_src = ""
                if img:
                    # 尝试多个可能的图片属性
                    for attr in ["src", "data-src", "data-original", "lazy-src", "original"]:
                        image_src = img.get(attr, "")
                        if image_src:
                            break
                
                # 调试：打印前3个影片的图片URL
                if len(movies) < 3 and image_src:
                    print(f"  影片 {len(movies)+1} 图片: {image_src[:100]}")
                
                # 确保图片是完整URL
                if image_src and not image_src.startswith("http"):
                    if image_src.startswith("/"):
                        image_src = homepage + image_src.lstrip("/")
                    else:
                        image_src = homepage.rstrip("/") + "/" + image_src
                
                # 获取番号 - 优先从日期元素获取
                code = ""
                date_elem = box.find("date")
                if date_elem:
                    code = date_elem.get_text(strip=True)
                    if "/" in code:
                        code = code.split("/")[0]
                
                # 如果没有日期，尝试从链接中提取
                if not code:
                    # 匹配常见番号格式
                    code_patterns = [
                        r'([A-Z]{2,}-\d{3,})',
                        r'([A-Z]+\d{3,})',
                    ]
                    for pattern in code_patterns:
                        match = re.search(pattern, link)
                        if match:
                            code = match.group(1)
                            break
                
                if not code:
                    # 使用链接最后一部分作为番号
                    code = link.split("/")[-1].strip()
                    if not re.match(r'[A-Z]{2,}-?\d{3,}', code, re.IGNORECASE):
                        continue  # 不是有效的番号格式，跳过
                
                # 检查HD和字幕
                box_html = str(box)
                hd = "高清" in box_html or "HD" in box_html
                subtitle = "字幕" in box_html
                
                # 创建电影对象
                movie = MovieData(
                    code=code.strip().upper(),
                    title=code.strip().upper(),
                    cover_url=image_src,
                    link=link,  # 保存完整的影片链接
                    hd=hd,
                    subtitle=subtitle,
                    recommend=False
                )
                movies.append(movie)
                
            except Exception as e:
                print(f"解析单个电影失败: {e}")
                continue
        
        print(f"成功解析 {len(movies)} 部影片")
        return movies
        
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        import traceback
        traceback.print_exc()
        return []


def fetch_movies_via_webview(page=1, keyword="", mode="home"):
    """优先用 WebView 获取 HTML（主方案），失败时回退 requests。"""
    try:
        state.search_mode = mode
        sync_home_source()
        url = build_url(mode, keyword, page)
        print(f"[WebView] 请求URL: {url}")

        fetcher = _get_webview_fetcher()
        result = fetcher.fetch_html(url, timeout=12)
        if not result.get("ok"):
            print(f"[WebView] 失败，回退 requests: {result.get('error', 'unknown')} ")
            return fetch_movies(page=page, keyword=keyword, mode=mode)

        print(f"[WebView] 最终标题: {result.get('title', '')}")
        print(f"[WebView] 最终URL: {result.get('url', '')}")
        print(f"[WebView] HTML长度: {len(result.get('html', ''))}")

        html = result.get("html", "")
        if not html:
            print("[WebView] HTML为空，回退 requests")
            return fetch_movies(page=page, keyword=keyword, mode=mode)

        if _is_age_verification_page(html):
            print("[WebView] 仍是年龄验证页，回退 requests")
            return fetch_movies(page=page, keyword=keyword, mode=mode)

        movies = parse_movie_list(html, get_homepage())
        if movies:
            print(f"[WebView] ✅ 获取到 {len(movies)} 部影片")
            return movies

        # 对齐 JS：搜索无结果时切换有/无码重试一次
        if "沒有您要的結果" in html and mode == "search" and page == 1:
            if state.again == 0:
                print("[WebView] 搜索无结果，尝试切换有码/无码")
                state.uncensored = not state.uncensored
                state.again = 1
                return fetch_movies_via_webview(page=page, keyword=keyword, mode=mode)
            state.again = 0

        print("[WebView] 未解析出影片，回退 requests")
        return fetch_movies(page=page, keyword=keyword, mode=mode)
    except Exception as e:
        print(f"[WebView] 异常，回退 requests: {e}")
        return fetch_movies(page=page, keyword=keyword, mode=mode)

def fetch_movies(page=1, keyword="", mode="home"):
    """获取影片列表 - 参考JavBus.js的getInitial实现"""
    try:
        state.search_mode = mode
        sync_home_source()
        
        # 先进行年龄验证（失败也继续按 JS 逻辑直接请求）
        verify_age()
        
        # 构建URL
        url = build_url(mode, keyword, page)
        print(f"请求URL: {url}")
        
        # 发起请求
        session = get_session()
        # 参照 JS：始终携带 existmag=all
        _set_age_cookies(session)
        resp = _request_with_age_cookie(session, url)
        resp.encoding = "utf-8"
        
        print(f"响应状态码: {resp.status_code}")
        print(f"响应内容长度: {len(resp.text)} 字符")
        
        if resp.status_code != 200:
            print(f"请求失败，状态码: {resp.status_code}")
            return []
        
        # 先尝试直接解析，避免误判导致空数据
        movies = parse_movie_list(resp.text, get_homepage())
        if movies:
            print(f"✅ 获取到 {len(movies)} 部影片")
            return movies

        # 检查是否仍然显示年龄验证页面
        if _is_age_verification_page(resp.text):
            print("仍然需要年龄验证，尝试其他方法...")
            # 方式1: 设置 cookie 重试
            _set_age_cookies(session)
            resp = _request_with_age_cookie(session, url)
            resp.encoding = "utf-8"

            movies = parse_movie_list(resp.text, get_homepage())
            if movies:
                print(f"✅ Cookie重试成功，获取到 {len(movies)} 部影片")
                return movies

            # 方式2: 表单提交后再请求
            if _post_age_verification_form(session, resp.text, url):
                resp = _request_with_age_cookie(session, url)
                resp.encoding = "utf-8"

                movies = parse_movie_list(resp.text, get_homepage())
                if movies:
                    print(f"✅ 表单验证成功，获取到 {len(movies)} 部影片")
                    return movies
            
            if _is_age_verification_page(resp.text):
                print("年龄验证仍然失败")
                return []
        
        # 检查是否到达末页 - 参考JavBus.js的404处理
        if "404 Page Not Found" in resp.text:
            print("已到达末页")
            return []
        
        # 检查是否没有结果 - 参考JavBus.js的沒有您要的結果处理
        if "沒有您要的結果" in resp.text:
            print("搜索无结果")
            # 对齐 JS：搜索无结果时自动切换有码/无码再次搜索（仅一次）
            if mode == "search" and page == 1:
                if state.again == 0:
                    print("尝试切换有码/无码版本")
                    state.uncensored = not state.uncensored
                    state.again = 1
                    return fetch_movies(page, keyword, mode)
                state.again = 0
            return []
        
        # 解析HTML
        movies = parse_movie_list(resp.text, get_homepage())
        
        if movies:
            print(f"✅ 获取到 {len(movies)} 部影片")
            return movies
        else:
            print("未能解析出影片数据")
            # 调试落盘，便于定位线上页面结构
            try:
                debug_file = "JavBus_debug_last_response.html"
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(resp.text)
                print(f"已保存调试页面: {debug_file}")
            except Exception as save_err:
                print(f"保存调试页面失败: {save_err}")
            # 打印部分HTML帮助调试
            print("页面HTML片段（前500字符）:")
            print(resp.text[:500])
            return []
            
    except Exception as e:
        print(f"Error fetching movies: {e}")
        import traceback
        traceback.print_exc()
        return []

# ================================================================
# UI 组件
# ================================================================

def home_view():
    """首页 - 搜索 + 影片网格"""
    return appui.VStack([
        # 标题栏
        appui.Text("JavBus").font("title").bold().padding(16),
        
        # 搜索框
        appui.HStack([
            appui.TextField(
                "输入番号或演员进行搜索",
                text=state.search_keyword,
                on_change=lambda v: setattr(state, 'search_keyword', v)
            )
            .padding(12)
            .background(COLORS["light_gray"], corner_radius=8)
            .frame(height=40),
            
            appui.Button("搜索", action=lambda: handle_search())
            .button_style("bordered_prominent")
            .padding(8),
        ], spacing=8).padding(16),
        
        # 提示信息（对齐 JS 的 bgInfo）
        appui.VStack([
            appui.Text("所有内容来自 javbus.com")
                .font("caption")
                .foreground_color(COLORS["text_secondary"])
                .padding(8)
                .frame(max_width=float('inf')),
        ]) if state.show_search_tips else None,
        
        # 切换模式按钮（对齐 JS 的 tabC: 有码 / 无码）
        appui.HStack([
            appui.Spacer(),
            appui.Button("有码", 
                       action=lambda: switch_source(False)
                       ).button_style("bordered_prominent" if not state.uncensored else "bordered"),
            appui.Button("无码", 
                       action=lambda: switch_source(True)
                       ).button_style("bordered_prominent" if state.uncensored else "bordered"),
            appui.Spacer(),
        ]).padding(8),
        
        # 刷新按钮
        appui.HStack([
            appui.Spacer(),
            appui.Button("刷新内容", action=lambda: handle_refresh())
            .button_style("bordered")
            .padding(8),
            appui.Spacer(),
        ]),
        
        # 影片网格（LazyVGrid）
        appui.LazyVGrid(
            columns=[appui.flexible()] * CONFIG["COLUMNS"],
            content=[
                movie_grid_cell(movie) 
                for movie in state.movie_list
            ],
            spacing=CONFIG["SPACING"],
        ).padding(16) if state.movie_list else appui.VStack([
            appui.Text("暂无数据")
                .font("headline")
                .foreground_color(COLORS["text_secondary"])
                .padding(32),
        ]).frame(max_height=float('inf')),
        
        # Loading 指示
        appui.VStack([
            appui.Text("加载中...").foreground_color(COLORS["primary"])
                if state.loading else None,
            appui.Text("没有更多内容了").foreground_color(COLORS["text_secondary"])
                if not state.has_more and not state.loading and state.movie_list else None,
        ]).padding(16),
    ], spacing=0)

def movie_grid_cell(movie):
    """影片网格单元"""
    return appui.VStack([
        # 封面图
        appui.Image(system_name="photo.fill")
            .resizable()
            .aspect_ratio(content_mode='fill')
            .frame(max_width=float('inf'), max_height=CONFIG["GRID_HEIGHT"])
            .background(COLORS["light_gray"], corner_radius=8)
            .overlay(
                appui.VStack([
                    # HD 标签
                    appui.HStack([
                        appui.Text("高清")
                            .font("caption2").bold()
                            .foreground_color("#FFFFFF")
                            .padding(4)
                            .background(COLORS["hd_blue"], corner_radius=4)
                            if movie.hd else None,
                        
                        appui.Text("字幕")
                            .font("caption2").bold()
                            .foreground_color("#FFFFFF")
                            .padding(4)
                            .background(COLORS["subtitle_orange"], corner_radius=4)
                            if movie.subtitle else None,
                    ], spacing=4).padding(4),
                    
                    appui.Spacer(),
                    
                    # 推荐角标
                    appui.Text("推荐")
                        .font("caption2").bold()
                        .foreground_color("#FFFFFF")
                        .padding(4)
                        .background(COLORS["recommend_pink"], corner_radius=4)
                        if movie.recommend else None,
                ]).padding(8)
                .frame(max_width=float('inf'), max_height=float('inf'), alignment='topLeading'),
                alignment='topLeading'
            ),
        
        # 番号标签
        appui.Text(movie.code)
            .font("caption").bold()
            .foreground_color("#FFFFFF")
            .padding(6)
            .frame(max_width=float('inf'))
            .background("#000000", corner_radius=4)
            .padding(8),
        
    ]).frame(max_width=float('inf')) \
     .on_tap(lambda: handle_movie_select(movie))

def empty_view(title="暂未开发"):
    """空的视图 - 用于其他tab"""
    return appui.VStack([
        appui.Text(title).font("title").bold().padding(16),
        appui.Text("此功能暂时未开发").font("headline").foreground_color(COLORS["text_secondary"]).padding(32),
    ])

# ================================================================
# 事件处理函数
# ================================================================

def handle_search():
    """处理搜索"""
    keyword = state.search_keyword.strip()
    if not keyword:
        return
    
    state.loading = True
    state.show_search_tips = False
    state.current_page = 1
    state.movie_list = []
    state.has_more = True
    state.again = 0
    
    # 获取搜索结果
    def load_search_results():
        try:
            movies = fetch_movies_via_webview(page=1, keyword=keyword, mode="search")
            state.movie_list = movies
            state.loading = False
            state.has_more = len(movies) >= 9  # 假设每页9个
            print(f"搜索: {keyword}, 找到 {len(movies)} 部影片")
        except Exception as e:
            state.loading = False
            print(f"搜索失败: {e}")
    
    # 启动后台线程加载数据
    load_thread = threading.Thread(target=load_search_results, daemon=True)
    load_thread.start()

def handle_refresh():
    """处理刷新"""
    if state.loading:
        return
    
    state.loading = True
    state.current_page = 1
    state.movie_list = []
    state.has_more = True
    state.again = 0
    
    # 获取刷新结果
    def load_refresh_results():
        try:
            movies = fetch_movies_via_webview(page=1, keyword=state.search_keyword, mode=state.search_mode)
            state.movie_list = movies
            state.loading = False
            state.has_more = len(movies) >= 9
            print(f"刷新: 找到 {len(movies)} 部影片")
        except Exception as e:
            state.loading = False
            print(f"刷新失败: {e}")
    
    # 启动后台线程加载数据
    load_thread = threading.Thread(target=load_refresh_results, daemon=True)
    load_thread.start()

def handle_movie_select(movie):
    """处理影片选择"""
    print(f"选择影片: {movie.code}")
    # 简化版不实现详情页面，只打印信息


def switch_source(uncensored):
    """切换有码/无码并按 JS 首页方式重载。"""
    if state.loading:
        return
    if state.uncensored == uncensored and state.movie_list:
        return

    state.uncensored = uncensored
    state.search_mode = "home"
    state.search_keyword = ""
    state.current_page = 1
    state.movie_list = []
    state.has_more = True
    state.loading = True
    state.again = 0

    def load_source_home():
        try:
            movies = fetch_movies_via_webview(page=1, mode="home")
            state.movie_list = movies
            state.has_more = len(movies) >= 9
        finally:
            state.loading = False

    threading.Thread(target=load_source_home, daemon=True).start()

# ================================================================
# 主应用入口
# ================================================================

def body():
    """应用主体 - TabView"""
    return appui.TabView([
        appui.Tab(
            title="首页",
            system_image="house.fill",
            content=home_view()
        ),
        appui.Tab(
            title="演员",
            system_image="person.fill",
            content=empty_view("演员")
        ),
        appui.Tab(
            title="收藏",
            system_image="heart.fill",
            content=empty_view("收藏")
        ),
        appui.Tab(
            title="设置",
            system_image="gearshape.fill",
            content=empty_view("设置")
        ),
    ])

def main():
    """应用启动入口"""
    # 预热隐藏 WebView，确保代理回调可用
    try:
        _get_webview_fetcher()
        print("[WebView] 初始化完成")
    except Exception as e:
        print(f"[WebView] 初始化失败，将使用 requests 兜底: {e}")

    # 在后台线程加载首页数据
    def load_initial_movies():
        state.loading = True
        try:
            print("开始加载首页数据...")
            movies = fetch_movies_via_webview(page=1, mode="home")
            state.movie_list = movies
            state.loading = False
            state.has_more = len(movies) >= 9  # 假设每页9个
            print(f"加载首页: {len(movies)} 部影片")
            
            # 如果没有数据，显示提示信息
            if not movies:
                print("警告：未能获取到任何影片数据")
        except Exception as e:
            state.loading = False
            print(f"加载首页失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 启动后台线程加载数据
    load_thread = threading.Thread(target=load_initial_movies, daemon=True)
    load_thread.start()
    
    # 运行应用
    appui.run(body, state=state, presentation="fullscreen")

# ================================================================
# 程序执行
# ================================================================

if __name__ == "__main__":
    main()
