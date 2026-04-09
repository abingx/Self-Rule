// ============================================================
// 04_network.js — 网络请求层（HTML 抓取 / API 调用）
// 转写说明：对应 Python 中的 fetcher.py / api.py
//   - $http.get() / $http.request() → Python: requests.get() / httpx.get()
//   - 所有 handler 回调 → Python 中改为 return resp.text
//   - HTML 解析用 re.search() / re.findall()，或换 BeautifulSoup
//   - cookieHeader → requests.Session(headers=..., cookies=...)
// ============================================================

// ---- 首页 / 搜索 / 分类列表抓取 ----
// Python 转写：
//   def get_initial(mode="home", keyword="", caturl="", page=1) -> list[dict]:
//       url = build_url(mode, keyword, caturl, page)
//       resp = session.get(url, timeout=TIMEOUT)
//       return parse_movie_list(resp.text)
function getInitial(mode = "home", keyword = "", caturl = "") {
  page++;
  if      (mode == "home")   { url = homepage + "page/"; }
  else if (mode == "search") {
    url = encodeURI(homeSearchPage + keyword + "/");
    preMissav(keyword, 0);   // 并发预检 Missav
    jableTv(keyword, 0);     // 并发预检 JableTV
  }
  else if (mode == "cat")    { url = keyword + "/"; }

  let cookies = {};
  if (mode == "cat") {
    matrixID  = "initialViewCat";
    loadingID = "loadingc";
    if (ALLC) cookies = { cookie: "existmag=all" };
  } else {
    matrixID  = "initialView";
    loadingID = "loading";
    if (ALL)  cookies = { cookie: "existmag=all" };
  }

  $http.request({
    url: url + page,
    timeout: Timeout,
    header: cookies,
    handler: function (resp) {
      // 404 / 无结果处理
      if (resp.data.indexOf("404 Page Not Found") > -1) {
        $ui.toast("🙈 到底了", 0.5);  $ui.loading(false);  return;
      }
      if (resp.data.indexOf("沒有您要的結果") > -1) {
        // 自动切换有码/无码重试
        if (mode == "search" && $("initialView").data.length > 0) {
          $ui.toast("🙈 到底了", 0.5);  $ui.loading(false);  return;
        }
        if (Again == 1) {
          if (preMissavV || Jable) {
            // 找到 Missav/JableTV 资源，直接推入详情
            $ui.push(detailView(keyword));
            favLink = "Missav";
            favCode = keyword;
            getDetail(favLink);
          } else {
            $ui.error("💔 搜索无果,车牌无效");
          }
          return;
        } else if (mode == "search") {
          // 有码→无码→欧美 自动重试
          if (!uncensored) {
            homepage        = "https://www.javbus.com/uncensored/";
            homeSearchPage  = homepage + "search/";
            uncensored      = true;
            $("tabC").index = 1;
          } else {
            homepage        = "https://www.javbus.com/";
            homeSearchPage  = homepage + "search/";
            uncensored      = false;
            $("tabC").index = 0;
          }
          if (Oumei == 1) Again = 0;  else Again = 1;
          Oumei = 0;  page = 0;
          getInitial(mode, $("input").text);
          return;
        }
      }
      if (!resp.response) { $ui.alert("❌ 网络错误或无法访问"); $ui.loading(false); return; }
      $ui.loading(false);

      // ---- HTML 解析：movie-box 列表 ----
      // Python: pattern = r'<a class="movie-box"[\s\S]*?</span>\s'
      //         matches = re.findall(pattern, html)
      var reg   = /<a class="movie-box"[\s\S]*?<\/span>\s/g;
      var match = resp.data.match(reg);

      match.map(function (i) {
        link  = /href="([\s\S]*?)(")/.exec(i)[1];
        var im = /<img src="([\s\S]*?)(")/.exec(i)[1];
        image  = im.indexOf("http") >= 0 ? im : homepage.replace("uncensored/", "") + im;
        // var title = /title="(.*?)(">)/.exec(i)[1];  // 影片标题（备用）
        code  = /<date>(.*?)<\/date>/.exec(i)[1];       // 番号
        date  = /\/\s<date>(.*?)<\/date><\/span>/.exec(i)[1]; // 日期
        let hd  = i.includes("高清");
        let sub = i.includes("字幕");

        $(matrixID).data = $(matrixID).data.concat({
          link: link,
          initialCover: { src: image, source: { url: image, header: cookieHeader } },
          info:  { text: code + " | " + date },
          HD:    { hidden: !hd },
          SUB:   { hidden: !sub },
          recLabel: {
            hidden: RecAvCode.indexOf(code) > -1 ? false : true,
            bgcolor: RecAuthorCode.indexOf(code) > -1 ? $color("#f68b1f") : $color("#b20083")
          },
          recGra:  { hidden: LocalFavList.indexOf(code) > -1 ? false : true },
          recBlur: { hidden: LocalArcList.indexOf(code) > -1 ? false : true }
        });
      });

      $("input").placeholder = "输入番号或演员进行搜索";
      $(loadingID).text = "";
      // 若结果唯一，直接跳转详情
      if ($(matrixID).data.length == 1) {
        $ui.push(detailView(code));
        favLink = link;  favSrc = image;  favCode = code;
        favInfo = code + " | " + date;
        shortCode = favLink.split("/").pop();
        getDetail(link);
      }
    }
  });
}

// ---- 演员列表抓取 ----
// Python: def get_actress_list(url, page) -> list[dict]
function getInitialActress(url) {
  page++;
  $http.request({
    url: url + page,
    handler: function (resp) {
      $ui.loading(false);
      // Python: pattern = r'<a class="avatar-box text-center"[\s\S]*?</span>'
      var reg   = /<a class="avatar-box text-center"[\s\S]*?<\/span>/g;
      var match = resp.data.match(reg);
      match.map(function (i) {
        var link  = /href="([\s\S]*?)(")/.exec(i)[1];
        var image = homepage + /<img src="([\s\S]*?)(")/.exec(i)[1];
        var title = /title="(.*?)(">)/.exec(i)[1];
        $("initialView").data = $("initialView").data.concat({
          link: link,
          initialCover: { src: image, source: { url: image, header: cookieHeader } },
          info: { text: title }
        });
      });
      $("loading").text = "";
      $("input").placeholder = "输入番号或演员进行搜索";
    }
  });
}

// ---- 影片详情抓取 ----
// Python: def get_detail(url) -> dict  (包含封面/演员/磁链入口等)
function getDetail(url) {
  flag++;
  Trans = 0;  preMissavV = false;  Avgle = false;  Missav = false;  Jable = false;
  preMissav(favCode, 1);
  jableTv(favCode, 0);
  playMissav(favCode);
  javdbRate(favCode);

  $http.request({
    url: url,
    timeout: Timeout,
    handler: function (resp) {
      if (!resp.response && url !== "Missav") { $ui.error("❌ 网络连接错误"); return; }
      javbusLink = url;

      // 演员头像列表
      // Python: actor_reg = r'<a class="avatar-box"[\s\S]*?</a>'
      var actressReg = /<a class="avatar-box"[\s\S]*?<\/a>/g;
      var match = resp.data.match(actressReg);
      if (match) {
        $("whoInFilm").hidden = false;
        match.map(function (i) {
          name = /<span>(.*?)<\/span>/.exec(i)[1];
          var nameLink  = /href="([\s\S]*?)(")/.exec(i)[1];
          var ni = /<img src="([\s\S]*?)(")/.exec(i)[1];
          var nameImage = ni.indexOf("http") >= 0 ? ni
                        : ni.length == 0 ? "https://pics.dmm.co.jp/mono/actjpgs/nowprinting.gif"
                        : homepage.replace("uncensored/", "") + ni;
          $("filmActress").data = $("filmActress").data.concat({
            link: nameLink,
            actressCover: { src: nameImage, source: { url: nameImage, header: cookieHeader } },
            actressName:  { text: name }
          });
        });
      } else { $("whoInFilm").hidden = true; }

      // 封面大图
      var fm = /<a class="bigImage" href="(.*?)"/.exec(resp.data)[1];
      filmCover = fm.indexOf("http") >= 0 ? fm : homepage.replace("uncensored/", "") + fm;
      $("filmCover").src = filmCover;
      $("filmCover").source = { url: filmCover, header: cookieHeader };

      // 影片名、发行日期等
      var filmName = /<a class="bigImage" href="(.*?)" title="(.*?)"/.exec(resp.data)[2];
      $("filmName").text = filmName;
      var temp = /<span class="header">發行日期:<\/span>([\s\S]*?)<\/p>/.exec(resp.data);
      if (temp) {
        var filmTime = temp[1];
        // 更新 favData.info ...（详见原文件 4626 行后续）
      }
      // ... 更多字段解析详见原文件 4390-4626 行
    }
  });
}

// ---- 单部演员作品列表抓取 ----
// Python: def get_actress(url, page) -> list[dict]
function getActress(url) {
  actressPage++;
  $http.request({
    url: url + "/" + actressPage,
    timeout: Timeout,
    handler: function (resp) {
      if (resp.data.indexOf("404 Page Not Found") > -1) {
        $ui.toast("🙈 到底了", 0.5);  $ui.loading(false);  return;
      }
      $ui.loading(false);
      var reg   = /<a class="movie-box"[\s\S]*?<\/span>\s/g;
      var match = resp.data.match(reg);
      if (!match) return;
      match.map(function (i) {
        var link  = /href="([\s\S]*?)(")/.exec(i)[1];
        var image = /<img src="([\s\S]*?)(")/.exec(i)[1];
        var code  = /<date>(.*?)<\/date>/.exec(i)[1];
        var date  = /\/\s<date>(.*?)<\/date><\/span>/.exec(i)[1];
        $("actressView").data = $("actressView").data.concat({
          link: link,
          initialCover: { src: image, source: { url: image, header: cookieHeader } },
          info: { text: code + " | " + date }
        });
      });
    }
  });
}

// ---- 推荐列表拉取（作者/网友） ----
// Python: def get_new_rec() -> None  (更新全局 RecAv / RecBotAv)
function getNewRec(mode = "Author") {
  const recUrl    = "https://gitlab.com/Nicked639/javrev/raw/master/Rec";
  const recbotUrl = "https://gitlab.com/Nicked639/javrev/raw/master/RecBot";

  $http.get({ url: recUrl, handler: function (resp) {
    RecAv = resp.data;
    if (recommend < RecAv.length) $("newIcon").hidden = false;
    RecAv.map(i => { RecAvCode.push(i.code); RecAuthorCode.push(i.code); });
    $cache.set("RecAvCode", RecAvCode);
  }});

  $http.get({ url: recbotUrl, handler: function (resp) {
    RecBotAv = resp.data;
    RecBotAv.map(i => { RecAvCode.push(i.code); RecBotCode.push(i.code); });
    $cache.set("RecAvCode", RecAvCode);
  }});
}

// ---- 推荐展示列表（从 Gitlab 拉取 JSON） ----
function getRec(url) {
  showTips("Rec", "众口难调，欢迎投稿\n\n注:本界面封面时间为收藏时间而非上映时间");
  $http.get({ url: url, handler: function (resp) {
    $("recMatrix").data = [];
    $cache.set("recommend", resp.data.length);
    $("newIcon").hidden = true;
    resp.data.map(function (i) {
      $("recMatrix").data = $("recMatrix").data.concat({
        recCover: { src: i.src, source: { url: i.src, header: cookieHeader } },
        recInfo:  { text: i.info },
        recGra:   { hidden: LocalFavList.indexOf(i.code) > -1 ? false : true },
        recBlur:  { hidden: LocalArcList.indexOf(i.code) > -1 ? false : true },
        link: i.link,
        code: i.code
      });
    });
    $("loading").hidden = true;
  }});
}

// ---- 翻译影片名（Google Translate API） ----
// Python: def translate(keyword: str) -> str
function translate(keyword) {
  $("filmName").text = "翻译中...";
  let url = "https://translate.google.hk/translate_a/single?client=it&dt=t&dt=rmt&dt=bd&dt=rms&dt=qca&dt=ss&dt=md&dt=ld&dt=ex&otf=3&dj=1&hl=zh_CN&ie=UTF-8&oe=UTF-8&sl=auto&tl=zh-CN&q="
           + $text.URLEncode(keyword);
  $http.get({
    header: { "User-Agent": "GoogleTranslate/5.8.58002 (iPhone; iOS 10.3; zh_CN; iPhone8,1)" },
    url: url,
    handler: function (resp) {
      var json = resp.data.sentences;
      var text = json.splice(0, json.length - 1).map(i => i.trans);
      $("filmName").text = text.join("");
    }
  });
}

// ---- 版本更新检测 ----
// Python: def script_version_update() -> None
function scriptVersionUpdate() {
  // 详见原文件 5262-5311 行
  // 主要逻辑：比较本地 version 与远程 Gitlab JSON 中的版本号
}

// ---- 开屏搜索（从分享/URL Scheme 带入番号） ----
// Python: def open_with_code(code: str) -> None
function openJS(code) {
  getOpenData(code);
  favLink = "https://www.javbus.com/" + code;
  $ui.push(detailView(code));
  getDetail(favLink);
  getInitial();
}

// 获取番号对应的封面与日期（用于补全 favData）
function getOpenData(code) {
  let url = encodeURI("https://www.javbus.com/search/" + code + "/");
  $http.request({ url: url, handler: function (resp) {
    var image = /photo-frame">[\s\S]*?<img src="([\s\S]*?)(")/.exec(resp.data)[1];
    var date  = /\/\s<date>(.*?)<\/date><\/span>/.exec(resp.data)[1];
    favData   = { code: code, info: code + " | " + date, src: image, shortCode: code };
  }});
}

// ---- 分类页抓取 ----
// Python: def get_cat(url) -> dict  (按 Titles 分组的分类数据)
function getCat(url) {
  $http.request({ url: url, handler: function (resp) {
    if (!resp.response) { $ui.error("❌ 网络错误或无法访问"); return; }
    let catTitles = url.includes("uncensored") ? Utitles : Titles;
    $("catMatrix").data = [];
    for (let i = 0; i < catTitles.length; i++) {
      let re = new RegExp(catTitles[i] + "</h4>([\\s\\S]*?)</div>");
      // 详见原文件 5087-5122 行
    }
  }});
}

// ---- 磁链获取（WebView 注入方式） ----
// Python 转写提示：磁链通过 Ajax 请求获取，需 session 保持登录态
//   可改为直接 requests.get(ajax_url, headers=cookie_header)
function getJavMag(link, flag = "0") {
  // 详见原文件 4159-4241 行
  // 核心：在隐藏 WebView 中拦截 uncledatoolsbyajax.php 请求并 eval 获取数据
  // Python 替代方案：requests + re 解析 HTML，或 selenium headless
}
