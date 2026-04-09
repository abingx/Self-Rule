// ============================================================
// 06_ui_views.js — UI 视图模板与组件定义
// 转写说明：对应 Python-iOS 脚本中的 ui_views.py
//   - JSBox 的 $ui.push({type, props, views, layout, events}) 体系
//     → Python: 用 ui.View / ui.TableView 等系统组件对应
//   - layout 闭包 (make) → Python: view.frame / autoresizing
//   - 所有 $color() / $font() → Python 中用 ui.parse_color() / UIFont
//   - template 列表（matrix cell 定义）→ Python: 自定义 UITableViewCell
// ============================================================

// ============================================================
// ① 影片列表 Cell 模板（Grid Matrix 通用）
// Python: 自定义 TableView cell，包含封面图、番号标签、HD/字幕/推荐角标
// ============================================================
mainTemplate = {
  props: { bgcolor: $color("white") },
  views: [
    { type: "image", props: { id: "initialCover", radius: 5 }, layout: $layout.fill },
    {
      type: "label",
      props: { id: "info", bgcolor: $rgba(0,0,0,0.35), textColor: $color("white"),
               align: $align.center, font: $font(10), autoFontSize: true, radius: 5 },
      layout: function (make) { make.left.right.inset(0); make.bottom.inset(0); make.height.equalTo(20); }
    },
    {
      type: "label",
      props: { text: "高清", id: "HD", bgcolor: $rgb(114,148,177), textColor: $color("white"),
               align: $align.center, font: $font("bold", 12), radius: 4, hidden: true, alpha: 0.8 },
      layout: function (make) { make.top.left.inset(0); make.height.equalTo(18); make.width.equalTo(34); }
    },
    {
      type: "label",
      props: { text: "字幕", id: "SUB", bgcolor: $rgb(242,184,103), textColor: $color("white"),
               align: $align.center, font: $font("bold", 12), radius: 4, hidden: true, alpha: 0.8 },
      layout: function (make) { make.top.right.inset(0); make.height.equalTo(18); make.width.equalTo(34); }
    },
    {
      type: "gradient",
      props: { id: "gradient", colors: colorData[randomColor(0,11)],
               locations: [0.0, 1.0], startPoint: $point(0,0), endPoint: $point(1,1),
               radius: 8, hidden: true, alpha: 1 },
      layout: $layout.fill
    },
    {
      type: "label",
      props: { text: "推荐", id: "recLabel", bgcolor: $color("#b20083"), textColor: $color("white"),
               align: $align.center, font: $font("bold", 12), radius: 4, hidden: true, alpha: 0.8 },
      layout: function (make) { make.top.right.inset(0); make.height.equalTo(18); make.width.equalTo(34); }
    },
    {
      type: "blur",
      props: { id: "recBlur", radius: 8, hidden: true, alpha: 0.4 },
      layout: $layout.fill
    },
    {
      type: "gradient",
      props: { id: "recGra", colors: colorData[9], locations: [0.0, 1.0],
               startPoint: $point(0,0), endPoint: $point(1,1), radius: 8, hidden: true, alpha: 0.4 },
      layout: $layout.fill
    },
    {
      type: "label",
      props: { id: "name", bgcolor: $color("clear"), textColor: $color("white"),
               align: $align.center, font: $font(15), autoFontSize: true, hidden: true },
      layout: $layout.fill
    }
  ]
};

// ============================================================
// ② 磁链列表 Cell 模板
// Python: TableView cell，显示文件名 / 大小 / 时间 / HD/字幕角标
// ============================================================
const mTemplate = {
  props: { bgcolor: $color("clear") },
  views: [
    {
      type: "label",
      props: { id: "mFileName", font: $font(11), textColor: $color("black"),
               lines: 2, align: $align.left },
      layout: function (make) {
        make.left.inset(5); make.right.inset(120);
        make.top.inset(2); make.height.equalTo(36);
      }
    },
    {
      type: "label",
      props: { id: "mFileSize", font: $font(10), textColor: $color("#555555"), align: $align.right },
      layout: function (make) { make.right.inset(5); make.top.inset(2); make.height.equalTo(18); }
    },
    {
      type: "label",
      props: { id: "mTime", font: $font(10), textColor: $color("#555555"), align: $align.right },
      layout: function (make) { make.right.inset(5); make.bottom.inset(2); make.height.equalTo(18); }
    },
    {
      type: "label",
      props: { text: "高清", id: "HD", bgcolor: $rgb(114,148,177), textColor: $color("white"),
               align: $align.center, font: $font("bold", 10), radius: 3, hidden: true },
      layout: function (make) { make.right.inset(75); make.bottom.inset(2); make.size.equalTo($size(30,16)); }
    },
    {
      type: "label",
      props: { text: "字幕", id: "SUB", bgcolor: $rgb(242,184,103), textColor: $color("white"),
               align: $align.center, font: $font("bold", 10), radius: 3, hidden: true },
      layout: function (make) { make.right.inset(40); make.bottom.inset(2); make.size.equalTo($size(30,16)); }
    }
  ]
};

// ============================================================
// ③ 主搜索视图（首页 / 搜索结果页）
// Python: 顶部 SearchBar + GridView，通过 mode 切换数据源
// ============================================================
function searchView(height, catname, cols = 3, spa = 1) {
  return {
    type: "view",
    props: { title: catname, id: "searchView", bgcolor: $color("white") },
    views: [
      // 背景提示文字
      {
        type: "text",
        props: { id: "bgInfo", text: "\n\n\n脚本所有内容来自\n\nhttps://www.javbus.com ",
                 editable: false, textColor: $color("#CCCCCC"), font: $font(12),
                 align: $align.center, hidden: false },
        layout: function (make) {
          make.top.inset(35); make.height.equalTo(100); make.width.equalTo($device.info.screen.width);
        }
      },
      // Loading 文字
      {
        type: "text",
        props: { id: "loading", text: "Loading...", bgcolor: $color("clear"),
                 textColor: $color("#888888"), font: $font("HelveticaNeue-BoldItalic", 20),
                 align: $align.center, editable: false },
        layout: function (make) {
          make.top.inset(200); make.height.equalTo(100); make.width.equalTo($device.info.screen.width);
        }
      },
      // 搜索框
      {
        type: "input",
        props: { id: "input", placeholder: "载入中, 请稍候...", font: $font(13),
                 bgcolor: $color("#f3f3f3"), radius: 8, stickyHeader: false },
        events: {
          didBeginEditing: function (sender) { $("input").runtimeValue().invoke("selectAll"); },
          changed: function (sender) {
            // 归档 tab 实时搜索
            if ($("menu").index == 5) { searchAr(sender.text); return; }
          },
          returned: function (sender) {
            // 详见原文件 645-686 行
            // 归档搜索 / 切换站点 / 触发 getInitial
            if ($("menu").index == 5) { searchAr(sender.text); sender.blur(); return; }
            Again = 0;
            let index = $("tabC").index;
            if (index == 2)      { homepage = "https://www.javbus.org/"; Oumei = 1; }
            else if (index == 0) { homepage = "https://www.javbus.com/"; }
            else                 { homepage = "https://www.javbus.com/uncensored/"; }
            homeSearchPage = homepage + "search/";
            if ($("searchView").super == $("JavBus")) $("searchView").remove();
            $("JavBus").add(searchView(180));
            $("tabC").index = index;
            $("input").text = sender.text;
            sender.blur();
            $("initialView").data = [];
            $ui.loading(true);
            $("loading").text = "Loading...";
            if (sender.text) {
              mode = "search";
              keyword = sender.text.replace(/\s+/g, "")
                .replace(/([a-zA-Z])(?=\d)(?!-)(?<!fc)/gi, "$1-")
                .replace(/(\d)(?=[a-zA-Z])(?!-)/g, "$1-");
              $("input").text = keyword;
              page = 0;
              getInitial(mode, keyword);
            } else {
              mode = "home"; page = 0; getInitial(mode);
            }
            $("initialView").contentOffset = $point(0, 0);
            $("initialView").hidden = false;
            $("menu").index = 0;
          }
        },
        layout: function (make) { make.left.right.top.inset(5); make.height.equalTo(30); }
      },
      // 影片 Grid（主视图）
      {
        type: "matrix",
        props: { id: "initialView", itemHeight: height, columns: cols, spacing: spa,
                 square: false, bgcolor: $color("clear"), template: mainTemplate },
        layout: function (make) {
          make.left.right.bottom.inset(5);
          make.top.equalTo($("input").bottom).offset(5);
        },
        events: {
          pulled(sender) {
            // 下拉显示作者声明/更新说明
            sender.endRefreshing();
            $ui.menu({ items: ["作者声明", "更新说明"], handler: function(title, idx) {
              if (idx == 0) tutorial(); else readMe();
            }});
          },
          didReachBottom(sender) {
            // 上滑加载更多
            sender.endFetchingMore();
            if ($("menu").index == 0) { $ui.loading(true); getInitial(mode, keyword); }
            else if ($("menu").index == 1) {
              $ui.loading(true);
              url = $("tabC").index == 0
                ? "https://www.javbus.com/actresses/"
                : "https://www.javbus.com/uncensored/actresses/";
              getInitialActress(url);
            }
          },
          didSelect(sender, indexPath, data) {
            // 点击 cell 的路由（影片 / 演员 / 导演等）
            // 详见原文件 736-811 行
            favSrc  = data.initialCover.source.url;
            favInfo = data.info.text;
            favLink = data.link;
            shortCode = favLink.split("/").pop();
            favCode = shortCode;
            favData = { code: favCode, src: favSrc, info: favInfo, shortCode: shortCode };

            if ($("tab").hidden == false && $("tab").index == 1) {
              // 演员 tab
              favActressCover = favSrc;
              favActressName  = favInfo;
              url = favLink;
              actressView(favInfo, favSrc);
              actressPage = 0;
              getActress(favLink);
            } else {
              // 主搜索结果 → 影片详情
              $ui.push(detailView(favCode));
              getDetail(data.link);
            }
          }
        }
      }
    ]
  };
}

// ============================================================
// ④ 影片详情视图
// Python: 全屏页面，含封面大图 / 演员列表 / 磁链按钮 / 收藏按钮
// 原文件 1176-2415 行，结构复杂，此处列出关键子组件 ID
// ============================================================
function detailView(code) {
  return {
    type: "view",
    props: { title: code, id: "detailView" },
    views: [
      // filmCover      - 封面大图 (image)
      // filmName       - 影片标题 (label)
      // filmActress    - 演员头像列表 (matrix)
      // whoInFilm      - 演员区容器 (view)
      // favorite       - 收藏/归档按钮 (button)
      // check          - Missav 可播放指示 (button)
      // rate           - JavDB 评分 (button)
      // magnet         - 磁链按钮 (button)
      // whoInFilm      - 演员区 (view)
      // 详见原文件 1176-2415 行
    ]
    // events: didSelect on filmActress → 演员详情
  };
}

// ============================================================
// ⑤ 磁链列表视图
// Python: TableView，每行显示文件名/大小/时间，支持左滑复制/分享
// ============================================================
function magnetList(code) {
  return {
    props: { title: code },
    views: [
      // mMenu   - 磁链源切换 segmented control
      // mlist   - 磁链列表 list (template: mTemplate)
      // loadingm - 无资源提示 label
      // 详见原文件 2532-2688 行
    ]
  };
}

// ============================================================
// ⑥ 截图/样品图预览视图
// Python: ScrollView 横向展示多张样品图，支持长按保存
// ============================================================
const screenshotView = {
  type: "view",
  props: { title: "样品图像" },
  views: [
    // scroll (scroll) + images (matrix)
    // 详见原文件 2690-2831 行
  ]
};

// ============================================================
// ⑦ 演员详情视图
// Python: 顶部演员头像 + 姓名，下方影片 Grid
// ============================================================
function actressView(actress, cover) {
  $ui.push({
    type: "view",
    props: { title: actress },
    views: [
      // actressCoverView  - 头像 (image)
      // actressName       - 姓名 (label)
      // favActress        - 收藏演员按钮 (button)
      // actressView       - 影片 grid (matrix, template: mainTemplate)
      // 详见原文件 2917-3208 行
    ]
  });
}

// ============================================================
// ⑧ 推荐视图（作者推荐 / 网友投稿 切换）
// Python: 顶部 SegmentedControl + 影片 Grid
// ============================================================
recView = {
  props: { id: "recView" },
  layout: function (make) { make.left.right.bottom.inset(0); make.top.equalTo($("menu").bottom); },
  views: [
    // inputRec  - 推荐片投稿搜索框 (input)
    // recMatrix - 推荐影片 grid (matrix)
    // tabAll    - "作者推荐/网友推荐" segmented (tab)
    // 详见原文件 228-511 行
  ]
};

// ============================================================
// ⑨ 内嵌 WebView（Javlibrary 等外部页面）
// Python: WKWebView 对应 → 使用系统浏览器或 WebView 组件
// ============================================================
webview = {
  type: "view",
  props: { id: "webview" },
  views: [
    // web (web)  - 浏览器主体
    // 导航按钮（后退/前进/分享/刷新）
    // 详见原文件 512-576 行
  ],
  layout: function (make) { make.left.right.bottom.inset(0); make.top.equalTo($("menu").bottom); },
  events: { didFinish: function (sender) { getJavLib(); } }
};

// ============================================================
// ⑩ 辅助 UI 组件
// ============================================================

// WebView 导航按钮工厂
function webPreviewBTN(icon, layout, handler) {
  return {
    type: "button",
    props: { icon: $icon(icon, $color("tint"), $size(30, 22)), bgcolor: $color("clear") },
    layout: layout,
    events: { tapped: handler }
  };
}

// 导航按钮等宽布局（4 等分）
function navLayout() {
  return function (make, view) {
    make.left.equalTo(leftView.right);
    make.bottom.inset(25);
    make.height.equalTo(20);
    make.width.equalTo(view.super).multipliedBy(0.25);
    leftView = view;
  };
}

// 分类封面生成（渐变色块 + 标题）
function catCover(title) {
  // 详见原文件 3579-3768 行
  // 返回一个带随机渐变和标题的 view 配置对象
}

// 年龄确认弹窗（首次运行）
function checkAdult() {
  // 详见原文件 4910-5034 行
  // 全屏黑色遮罩 + FBI WARNING + 中文声明 + 两个确认按钮
}

// 用户协议/免责声明（NSAttributedString 富文本）
function tutorial() {
  // 详见原文件 5741-5803 行
}

// 归档搜索（本地过滤，不发网络请求）
// Python: def search_archive(text: str) -> list[dict]:
//   return [i for i in local_data["archive"] if text.upper() in i["code"]]
function searchAr(text) {
  let tempArc = [];
  LocalData.archive.map(function (i) {
    if (i.code.indexOf(text.toUpperCase()) > -1) {
      tempArc = tempArc.concat({
        code: i.code,
        link: homepage + i.shortCode,
        initialCover: { src: i.src, source: { url: i.src, header: cookieHeader } },
        info: { text: i.info },
        recLabel: {
          hidden: RecAvCode.indexOf(i.code) > -1 ? false : true,
          bgcolor: RecAuthorCode.indexOf(i.code) > -1 ? $color("#f68b1f") : $color("#b20083")
        }
      });
    }
  });
  $("initialView").data = tempArc;
}

// ============================================================
// ⑪ 分类浏览视图（genre 分组）
// Python: SectionedTableView，每节对应一个类目
// ============================================================
function iniCat(titles) {
  // 详见原文件 5123-5261 行
  // 构建带 titles 作为 section header 的分类矩阵视图
}
