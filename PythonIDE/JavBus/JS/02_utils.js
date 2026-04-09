// ============================================================
// 02_utils.js — 工具函数
// 转写说明：对应 Python 中的 utils.py
//   - 正则表达式语法基本一致，注意 Python 用 re 模块
//   - $clipboard / $detector → 需在 iOS 脚本层调用系统剪贴板 API
//   - $file.extensions → Python 中可用 os.listdir() 遍历扩展脚本目录
// ============================================================

// ---- 剪贴板番号检测 ----
// Python 转写：
//   import re
//   def clipboard_detect(clip: str) -> dict:
//       ...
//       return {"mode": mode, "keyword": keyword}
function clipboardDetect(clip) {
  let str = clip;
  // 精确匹配特定厂牌格式（优先级高）
  let reg1 = /[sS][nN][iI][sS][\s\-]?\d{3}|[aA][bB][pP][\s\-]?\d{3}|[iI][pP][zZ][\s\-]?\d{3}|[sS][wW][\s\-]?\d{3}|[jJ][uU][xX][\s\-]?\d{3}|[mM][iI][aA][dD][\s\-]?\d{3}|[mM][iI][dD][eE][\s\-]?\d{3}|[mM][iI][dD][dD][\s\-]?\d{3}|[pP][gG][dD][\s\-]?\d{3}|[sS][tT][aA][rR][\s\-]?\d{3}|[eE][bB][oO][dD][\s\-]?\d{3}|[iI][pP][tT][dD][\s\-]?\d{3}/i;
  // 通用番号格式（3-5字母 + 3-4数字）
  let reg2 = /[a-zA-Z]{3,5}[\s\-]?\d{3,4}/g;

  let match = str.match(reg1);
  if (match) {
    mode = "search";
    keyword = match[0]
      .replace(/\s+/g, "")
      .replace(/([a-zA-Z])(?=\d)(?!-)(?<!fc)/gi, "$1-") // 字母与数字间补 -
      .replace(/(\d)(?=[a-zA-Z])(?!-)/g, "$1-");        // 数字与字母间补 -
    $("input").text = keyword;  // Python: 此行改为 return 或 callback
  } else {
    let match = str.match(reg2);
    if (match) {
      mode = "search";
      keyword = match[0]
        .replace(/\s+/g, "")
        .replace(/([a-zA-Z])(?=\d)(?!-)(?<!fc)/gi, "$1-")
        .replace(/(\d)(?=[a-zA-Z])(?!-)/g, "$1-");
      $("input").text = keyword;
    } else {
      mode = "home";
      keyword = "";
    }
  }
  return { mode: mode, keyword: keyword };
}

// ---- 随机颜色生成（UI 用） ----
// Python 转写：import random; random.randint(Min, Max)
function random256(begin, end) {
  return $rgb(randomColor(begin, end), randomColor(begin, end), randomColor(begin, end));
}

function randomColor(Min, Max) {
  var Range = Max - Min;
  var Rand = Math.random();
  return Min + Math.round(Rand * Range);
}

// ---- 当前日期字符串 ----
// Python: from datetime import date; date.today().isoformat()
function nowTime() {
  let t = new Date();
  let y = t.getFullYear();
  let m = t.getMonth() + 1;
  let d = t.getDate();
  return y + "-" + m + "-" + d;
}

// ---- 判断是否在通知中心（Today Widget）中运行 ----
// Python/iOS 脚本：通常通过启动参数或环境变量区分
function isInToday() {
  return $app.env == $env.today ? true : false;
}

// ---- 通知中心启动时的路由 ----
// Python 转写：在 main() 入口判断 context 后决定跳转
function runWhere() {
  let clip = $clipboard.text;
  let link = $detector.link(clip);
  let detect = { mode: "", keyword: "" };
  if (clip) detect = clipboardDetect(clip);
  if (detect.keyword == "" || link.length > 0) {
    $app.openURL("jsbox://run?name=JavBus");  // Python: 打开主 App
  }
}

// ---- 首次运行提示（每个 key 仅弹一次） ----
// Python: 用 cache / db 记录 shown 状态
function showTips(name, str) {
  if ($cache.get(name) == undefined) {
    alert(str);
    $cache.set(name, 1);
  }
}

// ---- 检测 Avgle 扩展脚本是否存在 ----
// Python 转写：os.path.exists("Avgle.py") 或遍历扩展目录
function jsDetect() {
  var js = $file.extensions;
  for (var i = 0; i < js.length; i++) {
    var match = /Avgle[\s\S]*?/g.exec(js[i]);
    if (match) {
      return { js: js[i], num: i };
    }
  }
  return false;
}

// ---- Cookie 处理 ----
// Python 转写：requests.Session() + session.cookies 管理
function processCookies(cookies) {
  let cookie = "";
  cookies.map(c => {
    if (c.domain.indexOf("javbus") > 0) {
      cookie += `${c.name}=${c.value};`;
    }
  });
  cookieHeader = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
    "referer": "https://www.javbus.com/",
    "cookie": cookie
  };
  return cookieHeader;
}

// ---- 从 WebView 获取全部 Cookie ----
// Python 转写：requests.Session 中 cookie jar 或 http.cookiejar
function getAllCookies(webView) {
  return new Promise((resolve, reject) => {
    const httpCookieStore = webView
      .ocValue()
      .invoke("configuration")
      .invoke("websiteDataStore")
      .invoke("httpCookieStore");

    const handler = $block("void, NSArray *", function (array) {
      const list = [];
      const length = array.$count();
      for (let index = 0; index < length; index++) {
        const element = array.$objectAtIndex_(index);
        list.push(element);
      }
      resolve(list.map(n => ({
        domain: n.$domain().jsValue(),
        path: n.$path().jsValue(),
        version: n.$version(),
        sessionOnly: n.$sessionOnly(),
        name: n.$name().jsValue(),
        value: n.$value().jsValue(),
        HTTPOnly: n.$HTTPOnly(),
        secure: n.$secure()
      })));
    });

    httpCookieStore.$getAllCookies_(handler);
  });
}
