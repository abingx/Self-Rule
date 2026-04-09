// ============================================================
// 07_main.js — 应用入口与生命周期
// 转写说明：对应 Python 中的 main.py / app.py
//   - start() → if __name__ == "__main__": main()
//   - $context.query → Python: sys.argv 或 URL Scheme 参数解析
//   - $cache.get("adultCheck") → Python: 读取本地 config 文件判断
//   - 整体启动流程：年龄验证 → initial() 加载本地数据 → main() 触发首屏
// ============================================================

// ============================================================
// 启动入口
// Python:
//   if __name__ == "__main__":
//       if not cache.get("adult_check"):
//           check_adult()       # 弹出年龄确认
//       else:
//           initial()           # 加载本地收藏/归档数据
//           main(BASE_URL)      # 触发首屏数据请求
// ============================================================
function start() {
  if ($cache.get("adultCheck") === undefined) {
    checkAdult();         // 首次运行显示年龄确认界面
  } else {
    initial();            // 加载本地数据、初始化 UI 框架
    main(url);            // 检测剪贴板 / URL Scheme 参数，触发首屏
  }
}

// ============================================================
// 主逻辑路由
// 处理三种启动来源：
//   1. URL Scheme 带 code 参数 → 直接跳转详情
//   2. 分享扩展 textItems     → 剪贴板检测后搜索
//   3. 普通启动               → 首页浏览
//
// Python 转写：
//   def main(base_url: str):
//       global page, homepage, home_search_page
//       page = 0
//       homepage = base_url
//       home_search_page = homepage + "search/"
//
//       code = get_url_scheme_param("code")  # URL Scheme 参数
//       if code:
//           code = normalize_code(code)
//           open_with_code(code)
//           return
//
//       clip = get_clipboard()
//       if clip:
//           detect = clipboard_detect(clip)
//           get_initial(detect["mode"], detect["keyword"])
//       else:
//           get_initial()   # 首页
// ============================================================
function main(url) {
  page = 0;
  homepage       = url;
  homeSearchPage = homepage + "search/";

  let clip = $clipboard.text;
  let link = $detector.link(clip);
  let detect = { mode: "home", keyword: "" };

  // ① URL Scheme 启动：jsbox://run?name=JavBus&code=ABC-123
  if ($context.query.code) {
    let code = clipboardDetect($context.query.code).keyword;
    if (!code) {
      alert("💔 搜索无果,车牌无效", 2);
      getInitial();
      return;
    }
    code = code.toUpperCase();
    // 补全缺失的连字符
    if (code.indexOf("-") < 0) {
      code = code.replace(/([a-zA-Z]+)/, "$1-");
    }
    favCode   = code;
    RecAvCode = $cache.get("RecAvCode");
    openJS(code);   // 触发详情 + 首页并行加载
    // 更新收藏/归档按钮状态
    if (LocalFavList.indexOf(code) > -1) {
      $("favorite").title  = "取消收藏";
      $("favorite").bgcolor = $color("#f25959");
    } else if (LocalArcList.indexOf(code) > -1) {
      $("favorite").title  = "已归档";
      $("favorite").bgcolor = $color("#aaaaaa");
    }
    return;
  }

  // ② 无分享内容 / 欧美 tab / 剪贴板为空 / 剪贴板是链接 → 首页
  if (
    !$context.textItems &&
    ($("tabC").index == 2 || clip == null || link.length > 0)
  ) {
    getInitial();
  } else {
    // ③ 分享扩展 textItems 或剪贴板番号 → 自动搜索
    if ($context.textItems) {
      detect = clipboardDetect($context.textItems[0]);
    } else {
      detect = clipboardDetect(clip);
    }
    getInitial(detect.mode, detect.keyword);
  }
}

// ============================================================
// 版本更新检测
// Python:
//   def script_version_update():
//       resp = requests.get(VERSION_URL)
//       remote_ver = resp.json()["version"]
//       if remote_ver > LOCAL_VERSION:
//           notify_update(remote_ver)
// ============================================================
function scriptVersionUpdate() {
  // 详见原文件 5262-5311 行
  // 请求 Gitlab 上的版本 JSON，比较 version 字段，弹出更新提示
}

// ============================================================
// 更新说明 / README 展示
// Python:
//   def read_me():
//       resp = requests.get(README_URL)
//       show_text_page(resp.text)
// ============================================================
function readMe() {
  let updateUrl = "https://raw.githubusercontent.com/Nicked639/xteko/master/JavBus/Readme.txt";
  $cache.set("samp", "1");
  $http.get({ url: updateUrl, handler: function (resp) {
    $ui.push({
      // 详见原文件 5522-5546 行
      // 展示 Readme 文本的只读页面
    });
  }});
}

// ============================================================
// 全局常量（在 main 模块最后定义，保持与原文件一致）
// Python: 放在 config.py 开头
// ============================================================
LocalDataPath = "JavBusBackup.json";
url           = "https://www.javbus.com/";

// ============================================================
// 程序启动
// Python: if __name__ == "__main__": start()
// ============================================================
start();
