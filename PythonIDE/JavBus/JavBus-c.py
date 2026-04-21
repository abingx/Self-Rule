# JavBus - 使用 appui 声明式 UI 框架（Python IDE）
# ================================================================
# 新的重写计划：先实现主 UI 框架，后续逐步完善数据层和业务逻辑
# 
# 参考标准：
#   - appui-module.md — 声明式 UI 框架
#   - 测试Miniapp.py — appui 完整示例
#   - 原 JS 版本 06_ui_views.js / 07_main.js
# 
# 架构：
#   - 主入口：启动年龄确认 → 初始化 → 显示 TabView
#   - Tab 1: 首页/搜索（SearchBar + Grid）
#   - Tab 2: 演员列表（ActressGrid）
#   - Tab 3: 收藏/归档（FavList）
#   - Tab 4: 设置（Settings）
# ================================================================

import appui
import os
import json
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlencode

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
    "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
    search_mode="home",  # "home" / "search" / "actress"
    current_page=0,
    movie_list=[],  # 影片数据列表
    
    # 当前影片详情
    selected_movie=None,
    movie_detail=None,
    
    # 演员信息
    actress_list=[],
    selected_actress=None,
    
    # 本地数据
    favorites=[],
    archive=[],
    history=[],
    
    # UI 状态
    loading=False,
    show_search_tips=True,
    active_tab=0,
)

# ================================================================
# 模型 / 数据结构
# ================================================================

class MovieData:
    """影片数据模型"""
    def __init__(self, code, title, cover_url, actress_list=None, hd=False, subtitle=False, recommend=False):
        self.code = code
        self.title = title
        self.cover_url = cover_url
        self.actress_list = actress_list or []
        self.hd = hd
        self.subtitle = subtitle
        self.recommend = recommend
        self.link = f"{CONFIG['BASE_URL']}{code}"

class ActressData:
    """演员数据模型"""
    def __init__(self, name, photo_url, movies_count=0):
        self.name = name
        self.photo_url = photo_url
        self.movies_count = movies_count


# ================================================================
# 工具函数
# ================================================================

def load_local_data():
    """加载本地收藏/归档数据"""
    try:
        if os.path.exists(CONFIG["DATA_FILE"]):
            with open(CONFIG["DATA_FILE"], "r", encoding="utf-8") as f:
                data = json.load(f)
                state.favorites = data.get("favorite", [])
                state.archive = data.get("archive", [])
                state.history = data.get("history", [])
    except Exception as e:
        print(f"Error loading local data: {e}")

def save_local_data():
    """保存本地数据"""
    try:
        data = {
            "favorite": state.favorites,
            "archive": state.archive,
            "history": state.history,
            "last_update": datetime.now().isoformat(),
        }
        with open(CONFIG["DATA_FILE"], "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving local data: {e}")

def normalize_code(raw_code):
    """规范化番号格式"""
    code = raw_code.strip().upper()
    code = re.sub(r'\s+', '', code)
    code = re.sub(r'([a-zA-Z]+)(?=\d)', r'\1-', code)
    return code

# ================================================================
# 网络请求模块
# ================================================================

_session = None

def get_session():
    """获取 HTTP Session（带默认 headers）"""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": CONFIG["USER_AGENT"],
        })
    return _session

def get_demo_movies():
    """获取演示影片数据"""
    demo_movies = [
        MovieData("SNIS-001", "演员1", "https://via.placeholder.com/150?text=SNIS-001", hd=True, subtitle=True),
        MovieData("MIDE-123", "演员2", "https://via.placeholder.com/150?text=MIDE-123", hd=True, subtitle=False),
        MovieData("IPZ-456", "演员3", "https://via.placeholder.com/150?text=IPZ-456", hd=False, subtitle=True),
        MovieData("ABP-789", "演员4", "https://via.placeholder.com/150?text=ABP-789", hd=True, subtitle=True),
        MovieData("STAR-101", "演员5", "https://via.placeholder.com/150?text=STAR-101", hd=False, subtitle=False),
        MovieData("EBOD-202", "演员6", "https://via.placeholder.com/150?text=EBOD-202", hd=True, subtitle=False),
        MovieData("JUX-303", "演员7", "https://via.placeholder.com/150?text=JUX-303", hd=True, subtitle=True),
        MovieData("MIAD-404", "演员8", "https://via.placeholder.com/150?text=MIAD-404", hd=False, subtitle=False),
        MovieData("PGD-505", "演员9", "https://via.placeholder.com/150?text=PGD-505", hd=True, subtitle=True),
    ]
    return demo_movies

def fetch_homepage(page=1):
    """获取首页影片列表（支持多个源）"""
    try:
        # 方法1: 尝试javbus无审查版本
        url = f"{CONFIG['BASE_URL']}uncensored/page/{page}"
        print(f"尝试获取: {url}")
        
        try:
            resp = get_session().get(url, timeout=CONFIG["TIMEOUT"])
            resp.encoding = "utf-8"
            movies = parse_movie_list(resp.text, CONFIG["BASE_URL"])
            if movies:
                print(f"✅ 从javbus获取 {len(movies)} 部影片")
                return movies
        except Exception as e:
            print(f"javbus请求失败: {e}")
        
        # 方法2: 使用演示数据
        print("使用演示数据...")
        return get_demo_movies()
        
    except Exception as e:
        print(f"Error fetching homepage: {e}")
        return get_demo_movies()

def search_movies(keyword, page=1):
    """搜索影片"""
    try:
        keyword = normalize_code(keyword)
        url = f"{CONFIG['BASE_URL']}search/{keyword}/{page}"
        print(f"搜索: {keyword} - {url}")
        
        try:
            resp = get_session().get(url, timeout=CONFIG["TIMEOUT"])
            resp.encoding = "utf-8"
            movies = parse_movie_list(resp.text, CONFIG["BASE_URL"])
            if movies:
                print(f"✅ 搜索到 {len(movies)} 部影片")
                return movies
        except Exception as e:
            print(f"搜索请求失败: {e}")
        
        # 如果网络请求失败，尝试在演示数据中搜索
        print(f"在演示数据中搜索 '{keyword}'...")
        demo = get_demo_movies()
        results = [m for m in demo if keyword.lower() in m.code.lower() or keyword.lower() in m.title.lower()]
        if results:
            print(f"✅ 在演示数据中找到 {len(results)} 部影片")
        return results
        
    except Exception as e:
        print(f"Error searching movies: {e}")
        return get_demo_movies()

def parse_movie_list(html, base_url):
    """解析影片列表 HTML"""
    movies = []
    try:
        # 使用正则表达式提取 movie-box（更可靠）
        pattern = r'<a class="movie-box"[\s\S]*?<date>(.*?)</date>[\s\S]*?</a>'
        matches = re.findall(pattern, html)
        
        if not matches:
            print(f"未找到movie-box，尝试备用解析方法")
            # 备用方法：使用BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            boxes = soup.find_all("a", class_="movie-box")
            
            for box in boxes:
                try:
                    link = box.get("href", "").strip()
                    if not link:
                        continue
                    
                    img = box.find("img")
                    image_src = img.get("src", "") if img else ""
                    if image_src and not image_src.startswith("http"):
                        image_src = base_url.rstrip("/") + "/" + image_src.lstrip("/")
                    
                    date_elem = box.find("date")
                    if not date_elem:
                        continue
                    
                    date_text = date_elem.get_text(strip=True)
                    code = date_text.split("/")[0].strip() if "/" in date_text else date_text
                    
                    box_html = str(box)
                    hd = "高清" in box_html
                    subtitle = "字幕" in box_html
                    
                    movie = MovieData(
                        code=code,
                        title=code,
                        cover_url=image_src,
                        hd=hd,
                        subtitle=subtitle,
                        recommend=False
                    )
                    movies.append(movie)
                except Exception as e:
                    print(f"解析单个电影失败: {e}")
                    continue
        else:
            # 正则表达式提取成功，再获取详细信息
            pattern_detail = r'<a class="movie-box" href="(.*?)"[\s\S]*?<img src="(.*?)"[\s\S]*?<date>(.*?)</date>'
            details = re.findall(pattern_detail, html)
            
            for link, image, date_info in details:
                try:
                    if not link:
                        continue
                    
                    if image and not image.startswith("http"):
                        image = base_url.rstrip("/") + "/" + image.lstrip("/")
                    
                    code = date_info.split("/")[0].strip() if "/" in date_info else date_info
                    if not code:
                        continue
                    
                    # 在原始HTML中查找对应的movie-box检查标签
                    pattern_box = r'<a class="movie-box" href="' + re.escape(link) + r'"[\s\S]*?</a>'
                    box_match = re.search(pattern_box, html)
                    box_html = box_match.group(0) if box_match else ""
                    
                    hd = "高清" in box_html
                    subtitle = "字幕" in box_html
                    
                    movie = MovieData(
                        code=code,
                        title=code,
                        cover_url=image,
                        hd=hd,
                        subtitle=subtitle,
                        recommend=False
                    )
                    movies.append(movie)
                except Exception as e:
                    print(f"解析电影详情失败: {e}")
                    continue
        
        print(f"成功解析 {len(movies)} 部影片")
        return movies
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        import traceback
        traceback.print_exc()
        return []

# ================================================================
# UI 组件：核心视图
# ================================================================

def home_view():
    """首页 - 搜索 + 影片网格"""
    return appui.VStack([
        # 标题栏
        appui.Text("JavBus").font("title").bold().padding(16),
        
        # 搜索框
        appui.HStack([
            appui.TextField(
                "搜索番号或演员...",
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
        
        # 提示信息
        appui.Text("所有内容来自 javbus.com")
            .font("caption")
            .foreground_color(COLORS["text_secondary"])
            .padding(8)
            .frame(max_width=float('inf'))
            if state.show_search_tips else None,
        
        # 影片网格（LazyVGrid）
        appui.ScrollView(
            appui.LazyVGrid(
                columns=[appui.flexible()] * CONFIG["COLUMNS"],
                content=[
                    movie_grid_cell(movie) 
                    for movie in state.movie_list
                ],
                spacing=CONFIG["SPACING"],
            ).padding(8)
        ) if state.movie_list else appui.VStack([
            appui.Text("暂无数据")
                .font("headline")
                .foreground_color(COLORS["text_secondary"])
                .padding(32),
        ]).frame(max_height=float('inf')),
        
        # Loading 指示
        appui.Text("加载中...").foreground_color(COLORS["primary"])
            if state.loading else None,
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

def actress_view():
    """演员列表 Tab"""
    return appui.VStack([
        appui.Text("演员").font("title").bold().padding(16),
        
        appui.ScrollView(
            appui.LazyVGrid(
                columns=[appui.flexible()] * 2,
                content=[
                    actress_grid_cell(actress)
                    for actress in state.actress_list
                ],
                spacing=8,
            ).padding(8)
        ) if state.actress_list else appui.VStack([
            appui.Text("暂无演员数据")
                .font("headline")
                .foreground_color(COLORS["text_secondary"])
                .padding(32),
        ]).frame(max_height=float('inf')),
    ], spacing=0)

def actress_grid_cell(actress):
    """演员网格单元"""
    return appui.VStack([
        # 头像
        appui.Image(system_name="person.circle.fill")
            .resizable()
            .aspect_ratio(content_mode='fit')
            .frame(max_width=float('inf'), max_height=150)
            .foreground_color(COLORS["primary"]),
        
        # 名字
        appui.Text(actress.name)
            .font("callout").bold()
            .padding(8),
        
        # 作品数
        appui.Text(f"{actress.movies_count} 部作品")
            .font("caption")
            .foreground_color(COLORS["text_secondary"])
            .padding(4),
    ]).on_tap(lambda: handle_actress_select(actress))

def collection_view():
    """收藏/归档 Tab"""
    return appui.VStack([
        appui.Text("收藏").font("title").bold().padding(16),
        
        appui.Form([
            appui.Section(header="收藏夹", content=[
                appui.ForEach(
                    state.favorites,
                    lambda item, i: appui.HStack([
                        appui.VStack([
                            appui.Text(item.get("code", "N/A"))
                                .font("headline"),
                            appui.Text(item.get("info", ""))
                                .font("caption")
                                .foreground_color(COLORS["text_secondary"]),
                        ], alignment='leading'),
                        appui.Spacer(),
                    ]).padding(8).frame(max_width=float('inf')),
                    key='code'
                ),
            ]),
            
            appui.Section(header="归档", content=[
                appui.ForEach(
                    state.archive,
                    lambda item, i: appui.HStack([
                        appui.VStack([
                            appui.Text(item.get("code", "N/A"))
                                .font("headline"),
                            appui.Text(item.get("info", ""))
                                .font("caption")
                                .foreground_color(COLORS["text_secondary"]),
                        ], alignment='leading'),
                        appui.Spacer(),
                    ]).padding(8).frame(max_width=float('inf')),
                    key='code'
                ),
            ]),
        ])
    ])

def settings_view():
    """设置 Tab"""
    return appui.VStack([
        appui.Text("设置").font("title").bold().padding(16),
        
        appui.Form([
            appui.Section(header="数据管理", content=[
                appui.Button("清除本地数据", action=lambda: clear_local_data())
                    .foreground_color(COLORS["danger"]),
            ]),
            
            appui.Section(header="关于", content=[
                appui.HStack([
                    appui.Text("版本"),
                    appui.Spacer(),
                    appui.Text("1.0.0").foreground_color(COLORS["text_secondary"]),
                ]).padding(12).frame(max_width=float('inf')),
                
                appui.HStack([
                    appui.Text("源站点"),
                    appui.Spacer(),
                    appui.Text("javbus.com").foreground_color(COLORS["text_secondary"]),
                ]).padding(12).frame(max_width=float('inf')),
                
                appui.HStack([
                    appui.Text("更新说明"),
                    appui.Spacer(),
                    appui.Image(system_name="chevron.right")
                        .font("system", size=14)
                        .foreground_color(COLORS["text_secondary"]),
                ]).padding(12).frame(max_width=float('inf'))
                    .on_tap(lambda: show_readme()),
            ]),
        ])
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
    
    # 获取搜索结果
    movies = search_movies(keyword, page=1)
    state.movie_list = movies
    state.loading = False
    
    print(f"搜索: {keyword}, 找到 {len(movies)} 部影片")

def handle_movie_select(movie):
    """处理影片选择"""
    state.selected_movie = movie
    print(f"选择影片: {movie.code}")

def handle_actress_select(actress):
    """处理演员选择"""
    state.selected_actress = actress
    print(f"选择演员: {actress.name}")

def clear_local_data():
    """清除本地数据"""
    state.favorites = []
    state.archive = []
    state.history = []
    save_local_data()
    print("本地数据已清除")

def show_readme():
    """显示更新说明"""
    print("显示更新说明...")

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
            content=actress_view()
        ),
        appui.Tab(
            title="收藏",
            system_image="heart.fill",
            content=collection_view()
        ),
        appui.Tab(
            title="设置",
            system_image="gearshape.fill",
            content=settings_view()
        ),
    ])

def main():
    """应用启动入口"""
    # 加载本地数据
    load_local_data()
    
    # 在后台线程加载首页数据
    def load_initial_movies():
        state.loading = True
        try:
            print("开始加载首页数据...")
            movies = fetch_homepage(page=1)
            state.movie_list = movies
            state.loading = False
            print(f"加载首页: {len(movies)} 部影片")
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

# ================================================================
# 下一步实现计划：
# 
# Phase 2 - 数据层：
#   - 01_config.py: 配置常量、URL 定义
#   - 02_utils.py: 正则、日期、剪贴板、番号规范化
#   - 03_storage.py: 本地数据读写（替代 _local_data.js）
# 
# Phase 3 - 网络层：
#   - 04_fetcher.py: HTTP 请求（requests/httpx）
#   - 05_parser.py: HTML 解析（BeautifulSoup）
#   - 06_integrations.py: 第三方 API（Missav/JavDB/Fanza）
# 
# Phase 4 - 扩展 UI：
#   - 影片详情页面（DetailView）
#   - 演员详情页面（ActressDetailView）
#   - 磁链列表页面（MagnetListView）
#   - 样品图预览（ScreenshotView）
# 
# Phase 5 - 高级功能：
#   - 剪贴板自动检测
#   - URL Scheme 参数处理
#   - 搜索历史
#   - 智能推荐
# ================================================================
