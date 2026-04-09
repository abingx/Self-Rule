// ============================================================
// 05_third_party.js — 第三方平台联动（预览 / 评分 / 磁链）
// 转写说明：对应 Python 中的 integrations.py
//   - 各函数可独立转写为 def xxx(code: str) -> str | None
//   - 视频预览 URL 获取后，Python 侧用系统播放器或 VLC 打开
//   - WebView 注入方式（playMissav）在 Python 中需换成 playwright/selenium
// ============================================================

// ---- Avgle 视频预览 ----
// Python:
//   def pre_avgle(code: str) -> str | None:
//       url = f"https://api.avgle.com/v1/search/{code}/0?limit=10&t=a&o=bw"
//       resp = requests.get(url, timeout=2)
//       data = resp.json()
//       if not data["success"] or data["response"]["total_videos"] == 0:
//           return None
//       return data["response"]["videos"][0]["preview_video_url"]
function preAvgle(code, flag) {
  let url = "https://api.avgle.com/v1/search/" + encodeURI(code) + "/0?limit=10&t=a&o=bw";
  $http.get({
    url: url,
    timeout: 2,
    handler: function (resp) {
      if (!resp.data.success || !resp.response) { $ui.error("❌ Avgle 网络连接出错！"); return; }
      let video_num = resp.data.response.total_videos;
      if (video_num == 0) {
        preMissav(code);
        return;
      }
      let infos = resp.data.response.videos;
      Avgle = true;
      $ui.toast("预览来自 Avgle");
      play(infos[0].preview_video_url);
    }
  });
  return Avgle;
}

// ---- Missav 视频预览（HTTP HEAD 检测） ----
// Python:
//   def pre_missav(code: str) -> str | None:
//       url = f"https://eightcha.com/{code.lower()}/preview.mp4"
//       resp = requests.head(url, timeout=5)
//       return url if resp.ok else None
function preMissav(code, flag) {
  let url = "https://eightcha.com/" + code.toLowerCase() + "/preview.mp4";
  $http.get({
    url: url,
    handler: function (resp) {
      if (resp.data.info) {
        preMissavV = true;
        if (flag == 0) return;
        $ui.toast("预览来自 Missav");
        play(url);
      }
    }
  });
}

// ---- Missav 正片流地址获取（WebView 注入） ----
// Python 替代方案：playwright 加载页面后提取 video.currentSrc
//   async def play_missav(code: str) -> str | None:
//       async with async_playwright() as p:
//           page = await browser.new_page()
//           await page.goto(f"https://missav.com/{code}")
//           video = await page.wait_for_selector("video.player", timeout=10000)
//           return await video.get_attribute("src")
function playMissav(code) {
  $cache.remove("Missav");
  Missav = false;
  // 隐藏 WebView，注入 JS 轮询 video.currentSrc，通过 $notify 回传
  $("detailView").add({
    props: { id: "missWeb" },
    views: [{
      type: "web",
      props: {
        url: "https://missav.com/" + code,
        script: function () {
          const maxWaitTime = 10000;
          let timerId = null, startTime = null;
          const checkVideoUrl = () => {
            const now = Date.now();
            if (!startTime) startTime = now;
            if (now - startTime > maxWaitTime) { clearInterval(timerId); return; }
            const video = document.querySelector("video.player");
            if (video) { clearInterval(timerId); $notify("share", { url: video.currentSrc }); }
          };
          timerId = setInterval(checkVideoUrl, 100);
        }
      },
      events: {
        share: function (object) {
          Missav = true;
          $cache.set("Missav", object.url);
          $("check").bgcolor = $color("tint");
          $("check").titleColor = $color("white");
          $("missWeb").remove();
        }
      }
    }]
  });
}

// ---- JableTV 检测 ----
// Python:
//   def jable_tv(code: str) -> str | None:
//       # 详见原文件 5547-5606 行
//       # 访问 jable.tv 搜索接口，解析结果 URL
function jableTv(code, flag) {
  // 详见原文件 5547-5606 行
  // 核心：GET https://jable.tv/api/... 检测是否有资源
}

// ---- Fanza DMM 预览视频 ----
// Python:
//   def pre_fanza(code: str) -> str:
//       c = code.lower().replace("-", "00")
//       return f"https://cc3001.dmm.co.jp/litevideo/freepv/{c[0]}/{c[:3]}/{c}/{c}_sm_w.mp4"
function preFanza(favCode) {
  let code = favCode.toLowerCase().replace("-", "00");
  let url  = `https://cc3001.dmm.co.jp/litevideo/freepv/${code[0]}/${code.slice(0,3)}/${code}/${code}_sm_w.mp4`;
  play(url);
}

// ---- JavDB 评分获取 ----
// Python:
//   def javdb_rate(code: str) -> dict:
//       resp = requests.get(f"https://javdb.com/search?q={code}&f=all")
//       score = re.search(r"([0-9.]+)分", resp.text)
//       count = re.search(r"由(\d+)人評價", resp.text)
//       return {"score": score.group(1), "count": count.group(1)} if score else {}
function javdbRate(favCode) {
  $http.get({
    url: "https://javdb.com/search?q=" + favCode + "&f=all",
    handler: resp => {
      var html = /class="score">[\s\S]*?div>/.exec(resp.data)[0];
      const scoreMatch  = html.match(/([0-9.]+)分/);
      const ratingMatch = html.match(/由(\d+)人評價/);
      if (scoreMatch && ratingMatch) {
        $("rate").title = `评分: ${scoreMatch[1]}   数量: ${ratingMatch[1]}`;
      } else {
        $("rate").title = "评分:N/A   数量:N/A";
      }
    }
  });
}

// ---- 通用视频播放（跳转系统播放器） ----
// Python: webbrowser.open(url) 或调用 VLC 等
function play(url) {
  // 详见原文件 5607-5709 行
  // 主要使用 AVPlayer/系统播放器打开 HLS/MP4 流
}

// ---- 磁链列表弹出（JavBus WebView 注入） ----
// Python 替代：直接 requests.get(ajax_url, cookies=...) 获取磁链列表
function aboutMag() {
  $ui.push(magnetList(favCode));
  $("javbusList").data = javMagData;
  if (javMagData.length == 0) {
    $("loadingm").text = "☹️ JavBus 暂无磁链";
    $("loadingm").hidden = false;
  } else {
    $("loadingm").hidden = true;
  }
}

// ---- JavMag 第三方磁链搜索 API ----
// Python:
//   def get_magnet(code: str) -> list[dict]:
//       resp = requests.get(MAGNET_API + code + "&page=1&sort=time&a=...&b=...")
//       return resp.json()["data"]["results"]
function getMagnet(code) {
  showTips("Meg", "单击复制磁链，\n左滑分享磁链,\n若无磁链，尝试下拉刷新");
  $ui.loading(true);
  $http.request({
    url: urls[$("mMenu").index].pattern + code + "&page=1&sort=time&a=1566535262486&b=9e46e189be0a95d862379467a19322e7",
    handler: function (resp) {
      var data = resp.data;
      if (!data.success) {
        $("mlist").data = [{ mFileName: { text: "无资源" }, mFileSize: { text: "请切换源" }, mTime: { text: "" }, info: "" }];
      } else {
        data.data.results.map(function (i) {
          $("mlist").data = $("mlist").data.concat({
            mFileName: { text: i.name, textColor: i.name.indexOf("中文") > -1 ? $color("red") : $color("black") },
            mFileSize: { text: i.formatSize },
            mTime:     { text: i.date },
            info:      i.magnet
          });
        });
      }
      $ui.loading(false);
    }
  });
}

// ---- 归档收藏详情操作按钮处理 ----
function favDetailTapped(mode, Button) {
  // 详见原文件 3769-3819 行
  // 根据 mode ("favorite"/"archive") 调用 favoriteButtonTapped
}

// ---- 分类详情跳转 ----
function pushCat(sender, position = "") {
  // 详见原文件 3820-3871 行
  // 跳转至 director/series/filmMaker/filmEstab 类目列表
}

// ---- Javlibrary WebView 集成 ----
function getJavLib() {
  // 详见原文件 3872-3889 行
  // 获取当前 WebView URL 并在结果页面调用 getInitial
}
