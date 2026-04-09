// ============================================================
// 01_config.js — 全局配置与状态变量
// 转写说明：对应 Python 中的 config.py / constants.py
//   - 所有大写/全局变量 → Python 模块级变量
//   - $cache.get() → 自行实现的缓存层（如 shelve / json 文件）
//   - $color() / $rgb() → 在 UI 层单独处理，这里仅保留色值数组
// ============================================================

// ---- 版本 ----
version = 9.1;

// ---- 推荐数据缓存（运行时） ----
recommend = $cache.get("recommend") || 0;  // Python: cache.get("recommend", 0)
RecAv       = [];   // 作者推荐影片列表
RecBotAv    = [];   // 网友投稿推荐列表
RecAvCode   = [];   // 全部推荐影片番号（合并）
RecAuthorCode = []; // 作者推荐番号
RecBotCode  = [];   // 网友推荐番号

// ---- 浏览状态 ----
ALL    = false;  // 是否显示全部（含收录）
ALLC   = false;  // 详细类目下的全部状态
Again  = 0;      // 二次搜索标志
Oumei  = 0;      // 欧美站状态（0=日本站, 1=欧美站）

// ---- URL 配置 ----
catUrl = "https://www.javbus.com/genre";
// Python: BASE_URL = "https://www.javbus.com/"

// ---- 分类标题（有码 / 无码） ----
Titles  = ["主題", "角色", "服裝", "體型", "行為", "玩法", "類別"];
Utitles = ["主題", "角色", "服裝", "體型", "行為", "玩法", "其他", "場景"];
Category = [];   // 动态加载的分类数据

// ---- UI & 功能状态 ----
Menustatus = 0;     // 当前分类菜单选中状态
Trans      = 0;     // 翻译开关（0=关）
uncensored = false; // 无码模式
JavMag     = 0;     // 磁链获取状态
Timeout    = 10;    // 网络请求超时（秒）
flag       = 0;     // 从通知中心启动标志

// ---- 第三方平台联动开关 ----
Jable      = false;
Avgle      = false;
preMissavV = false;
Missav     = false;
Fanza      = false;

// ---- 网络请求头（由 processCookies 动态填充） ----
// Python: cookie_header = {}
cookieHeader = {};

// ---- 本地数据路径 ----
// Python: LOCAL_DATA_PATH = "JavBusBackup.json"
LocalDataPath = "JavBusBackup.json";

// ---- 主站 URL（由 main() 设置） ----
url = "https://www.javbus.com/";

// ---- 渐变配色方案（UI 用，共 15 组） ----
// Python 转写提示：直接用 HEX 字符串列表，UI 层再解析
// colorData[i] = [start_color_hex, end_color_hex]
var colorData = [
  ["#fd354a", "#da0a6f"],
  ["#f97227", "#f52156"],
  ["#edb319", "#e47b18"],
  ["#eecb01", "#e8a400"],
  ["#7ace1e", "#5aba23"],
  ["#25c578", "#3ab523"],
  ["#24d59a", "#24bb9d"],
  ["#00c0c8", "#00a0ca"],
  ["#12b7de", "#2193e6"],
  ["#2f74e0", "#5d44e0"],
  ["#825af6", "#6251f5"],
  ["#cc3ec8", "#9f0cdd"],
  ["#f66295", "#cf30a0"],
  ["#728199", "#54617e"],
  ["#1f436a", "#003268"]
];

// ---- 资源 Base64（新消息图标） ----
// Python 转写提示：写入 assets/new_icon.png 文件，运行时读取路径即可
const newIcon = "data:image/png;base64,iVBORw0KGgo..."; // (完整 base64 见原文件第 83-84 行)
