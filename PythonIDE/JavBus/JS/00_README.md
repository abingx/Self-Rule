# JavBus.js 模块拆分说明

## 文件结构

```
JavBus_modules/
├── 00_README.md        ← 本文件（架构说明 & 转写指南）
├── 01_config.js        ← 全局配置与状态变量
├── 02_utils.js         ← 工具函数（正则/日期/Cookie/剪贴板）
├── 03_local_data.js    ← 本地数据持久化（收藏/归档/演员）
├── 04_network.js       ← 网络请求层（HTML 抓取 + 数据解析）
├── 05_third_party.js   ← 第三方平台联动（Missav/Fanza/JavDB/磁链）
├── 06_ui_views.js      ← UI 视图模板与组件定义
└── 07_main.js          ← 应用入口与生命周期
```

---

## 模块职责说明

| 文件 | 职责 | Python 对应 |
|------|------|------------|
| `01_config.js` | 全局变量、URL 常量、色值表 | `config.py` / `constants.py` |
| `02_utils.js` | 番号正则、日期、Cookie、随机色 | `utils.py` |
| `03_local_data.js` | JSON 文件读写、收藏/归档增删 | `storage.py` / `db.py` |
| `04_network.js` | 影片列表/详情/演员 HTML 抓取与解析 | `fetcher.py` / `parser.py` |
| `05_third_party.js` | Missav/Avgle/Fanza/JavDB/磁链 API | `integrations.py` |
| `06_ui_views.js` | 所有 UI 视图模板和组件 | `ui_views.py` (纯 UI 层) |
| `07_main.js` | 启动路由、年龄确认、URL Scheme 处理 | `main.py` |

---

## 转写到 Python-iOS 脚本的关键对应

### JSBox API → Python 对应

| JSBox | Python-iOS (Pythonista/StaSh 等) |
|-------|----------------------------------|
| `$http.get({url, handler})` | `requests.get(url)` 或 `httpx.get(url)` |
| `$http.request({url, header, handler})` | `requests.get(url, headers=headers)` |
| `$cache.get(key)` | `shelve.open()` 或读取 JSON 文件 |
| `$cache.set(key, val)` | `shelve[key] = val` |
| `$file.read(path)` | `open(path).read()` |
| `$file.write({data, path})` | `open(path, "w").write(data)` |
| `$clipboard.text` | `clipboard.get()` (Pythonista) |
| `$ui.push(view)` | `ui.push_view(v)` 或导航控制器 |
| `$ui.loading(bool)` | 自定义 loading indicator |
| `$ui.toast(str)` | `ui.hud_alert(str)` |
| `$color("tint")` | `ui.parse_color("#007AFF")` |
| `$font(size)` | `UIFont.systemFont(ofSize: size)` |
| `$layout.fill` | `view.frame = superview.bounds` |
| `$context.query.code` | URL Scheme 参数解析 |

### HTML 解析对应

```python
# JSBox (正则)
var match = resp.data.match(/<a class="movie-box"[\s\S]*?<\/span>\s/g)

# Python (re 模块)
matches = re.findall(r'<a class="movie-box"[\s\S]*?</span>\s', html)

# 推荐：改用 BeautifulSoup
from bs4 import BeautifulSoup
soup = BeautifulSoup(html, "html.parser")
boxes = soup.select("a.movie-box")
```

### 番号正则（Python 版）

```python
import re

# 精确厂牌匹配
REG1 = re.compile(
    r'(SNIS|ABP|IPZ|SW|JUX|MIAD|MIDE|MIDD|PGD|STAR|EBOD|IPTD)[\s\-]?\d{3}',
    re.IGNORECASE
)
# 通用番号
REG2 = re.compile(r'[a-zA-Z]{3,5}[\s\-]?\d{3,4}')

def normalize_code(raw: str) -> str:
    code = raw.replace(" ", "")
    code = re.sub(r'([a-zA-Z])(?=\d)(?<!fc)', r'\1-', code, flags=re.IGNORECASE)
    return code.upper()
```

### 本地数据结构（Python dict）

```python
LOCAL_DATA = {
    "favorite": [{"code": str, "src": str, "info": str, "shortCode": str}],
    "archive":  [...],
    "actress":  [{"shortCode": str, "src": str, "info": str}],
    "director": [...],
    "filmMaker":[...],
    "filmEstab":[...],
    "series":   [...]
}
```

### Cookie 请求头

```python
COOKIE_HEADER = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X)...",
    "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
    "referer": "https://www.javbus.com/",
    "cookie": ""  # 由 session 自动管理，或手动从 WebView 提取
}
```

---

## 模块依赖关系

```
07_main.js
    ├── 01_config.js     (全局变量)
    ├── 02_utils.js      (clipboardDetect, nowTime 等)
    ├── 03_local_data.js (initial, writeCache, favoriteButtonTapped)
    ├── 04_network.js    (getInitial, getDetail, getActress)
    ├── 05_third_party.js(preMissav, javdbRate, getMagnet 等)
    └── 06_ui_views.js   (searchView, detailView, actressView 等)

04_network.js
    ├── 01_config.js     (cookieHeader, homepage 等全局状态)
    ├── 05_third_party.js(preMissav, jableTv, playMissav - 并发调用)
    └── 06_ui_views.js   (detailView - 推送视图)

06_ui_views.js
    ├── 04_network.js    (getDetail, getActress - 事件处理中调用)
    └── 03_local_data.js (favoriteButtonTapped - 按钮事件)
```

---

## 转写优先级建议

转写为 Python-iOS 脚本时，推荐按以下顺序进行：

1. **`01_config.py`** — 最简单，纯变量定义
2. **`02_utils.py`** — 正则/工具函数，无 UI 依赖
3. **`03_local_data.py`** — 文件读写，Python 更简洁
4. **`04_network.py`** — 核心抓取逻辑，用 requests + re/BS4
5. **`05_third_party.py`** — 各平台 API，逐个验证
6. **`06_ui_views.py`** — 最复杂，依赖 UI 框架选型
7. **`07_main.py`** — 最后整合入口

> ⚠️ `playMissav()` 中的 WebView JS 注入在 Python 侧需要 playwright/selenium 替代，
> 或直接用 requests 请求 missav.com 并解析 m3u8 流地址。
