/*
 * 拼多多取件码查询 —— Loon「request」脚本（请求重写 / 直接返回响应）
 * ------------------------------------------------------------
 * 触发：访问 https://loonjs.ai/pddpickup 时执行本脚本
 * 流程：
 *   1) 从 $persistentStore 读取 pdd_session（由 pdd_cookie_capture.js 写入的 JSON）
 *   2) 用其中的 Cookie 请求取快递 H5 页面，解析 SSR 里的 window.rawData
 *   3) 按驿站分组，以结构化 JSON 作为响应体返回（status 200）
 *
 * 响应格式：
 *   成功 { "success": true,  "total": 3, "updated_at": "...", "groups": [{ "station": "...", "codes": ["..."] }] }
 *   失败 { "success": false, "message": "..." }
 *
 * 重要：Loon 的 $httpClient 里 timeout 单位是「毫秒」，默认 5000ms。
 */

(function () {
  var KEY_SESSION = "pdd_session";
  var PDD_URL = "https://m.pinduoduo.net/psnl_goods_help.html?_t_module_name=assistant_pickup";

  var session = {};
  try { session = JSON.parse($persistentStore.read(KEY_SESSION) || "{}") || {}; } catch (e) {}
  var cookie = session.cookie || "";
  if (!cookie) {
    return json({ success: false, message: "还没有 Cookie。请先在拼多多里打开一次「我的 → 快递 / 取快递」页面，让脚本自动捕获 Cookie。" });
  }

  var ua = session.ua ||
    "Mozilla/5.0 (iPhone; CPU iPhone OS 27_2 like Mac OS X) AppleWebKit/605.1.15 " +
    "(KHTML, like Gecko) Mobile/15E148 Model/iPhone14,7 phh_ios_version/8.29.0 " +
    "phh_ios_build/202610251658 pversion/0 am_webview_id/165e35400";

  var extra = session.hdr || {};

  var headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-Hans-CN;q=1, en-CN;q=0.9",
    "User-Agent": ua,
    "Cookie": cookie
  };

  var defaults = {
    "x-pdd-queries": "width=1170.000000&height=2532.000000&brand=apple&model=iPhone 14&osv=27.2&appv=8.29.0&pl=iOS&net=1&dpr=3.000000",
    "x-pdd-info": "tz%3DAsia%2FShanghai%26pzvonm%3D15%266cpi%3DMjQwOTo4MTYyOjE5OjExOWU6MTQ5NTpjYjRiOjZkN2Y6YzMwYQ",
    "x-client-language": "zh",
    "x-client-region": "1",
    "x-yak-llt": "1711338940000"
  };
  for (var k in defaults) headers[k] = extra[k] || defaults[k];
  if (extra["x-app-ui"]) headers["x-app-ui"] = extra["x-app-ui"];

  var opts = {
    url: PDD_URL,
    headers: headers,
    timeout: 15000,            // 毫秒：15 秒（默认 5000）
    "auto-redirect": true,
    "auto-cookie": false,
    insecure: true
  };

  doRequest(opts, function (err, resp, data) {
    if (!err) return handle(resp, data);

    // 首次失败（常见于走了海外节点导致国内站超时）：改用直连再试一次
    console.log("[PDD] 首次请求失败：" + err + "，改用 DIRECT 重试");
    var direct = {};
    for (var k2 in opts) direct[k2] = opts[k2];
    direct.node = "DIRECT";

    doRequest(direct, function (err2, resp2, data2) {
      if (err2) {
        return json({ success: false, message: "请求拼多多失败：" + err2 });
      }
      handle(resp2, data2);
    });
  });

  /* ---------- 请求封装 ---------- */

  function doRequest(o, cb) {
    $httpClient.get(o, function (err, resp, data) {
      if (err) return cb(err);
      cb(null, resp, data);
    });
  }

  /* ---------- 主处理 ---------- */

  function handle(resp, data) {
    var body = (resp && resp.body) ? resp.body : (data || "");
    var items = parseItems(body);

    if (items === null) {
      // 页面里没有 window.rawData：Cookie 失效 / 未登录 / 被风控
      return json({ success: false, message: "Cookie 可能已失效。请打开一次拼多多「我的 → 快递 / 取快递」页面重新捕获 Cookie。" });
    }

    var groups = {}, order = [];
    items.forEach(function (it) {
      // 驿站名称显示为 address
      var station = it.address || it.station || "未知驿站";
      if (!groups[station]) { groups[station] = []; order.push(station); }
      var code = normalizeCode(it.pick_code);
      if (code && groups[station].indexOf(code) < 0) groups[station].push(code);
    });

    // 通知：各驿站取件码数量
    var lines = order.map(function (station) {
      return station + "：" + groups[station].length + " 个";
    });
    $notification.post(
      "PDD取件",
      "共 " + items.length + " 个待取",
      lines.length ? lines.join("\n") : "当前暂无待取",
      { openUrl: "pinduoduo://com.xunmeng.pinduoduo/psnl_goods_help.html?_t_module_name=assistant_pickup" }
    );

    json({
      success: true,
      total: items.length,
      updated_at: new Date().toISOString(),
      groups: order.map(function (station) {
        return { station: station, codes: groups[station] };
      })
    });
  }

  /* ---------- 输出 ---------- */

  function json(payload) {
    $done({
      response: {
        status: 200,
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(payload, null, 2)
      }
    });
  }

  /* ---------- 工具函数 ---------- */

  // 规范化取件码：去掉页面里自带的「取件码」前缀和多余空白
  function normalizeCode(code) {
    return String(code == null ? "" : code)
      .replace(/^\s*取件码\s*[:：]?\s*/, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  // 从字符串中截取第一个完整的 JSON 对象（容忍后面还有别的 JS 语句）
  function extractJson(str) {
    var start = str.indexOf("{");
    if (start < 0) return null;
    var depth = 0, inStr = false, esc = false;
    for (var i = start; i < str.length; i++) {
      var c = str.charAt(i);
      if (inStr) {
        if (esc) { esc = false; }
        else if (c === "\\") { esc = true; }
        else if (c === "\"") { inStr = false; }
      } else {
        if (c === "\"") { inStr = true; }
        else if (c === "{") { depth++; }
        else if (c === "}") {
          depth--;
          if (depth === 0) return JSON.parse(str.substring(start, i + 1));
        }
      }
    }
    return null;
  }

  // 返回 null 表示未登录/无数据；否则返回取件码数组
  function parseItems(html) {
    if (!html) return null;
    var key = "window.rawData=";
    var i = html.indexOf(key);
    if (i < 0) return null;

    var end = html.indexOf("</script>", i);
    var s = html.substring(i + key.length, end >= 0 ? end : html.length);

    var data = null;
    try { data = extractJson(s); } catch (e) { data = null; }

    var items = [];
    if (data && data.stores && data.stores.store && data.stores.store.noPickupPackageData) {
      var np = data.stores.store.noPickupPackageData;
      var list = np.combine_list || [];
      for (var a = 0; a < list.length; a++) {
        var it = list[a], tracks = it.combine_track_list || [];
        for (var b = 0; b < tracks.length; b++) {
          var t = tracks[b];
          var code = t.pick_code || t.pickCodeLocale;
          if (!code) continue;
          items.push({
            pick_code: code,
            station: it.company_name || "",
            address: it.address || "",
            shipping: t.shipping_name || "",
            tracking: t.tracking_number || "",
            time: t.operation_time || ""
          });
        }
      }
    }

    // 兜底：快递助手首页的 expressListData 里也带 pick_code
    if (!items.length) {
      var re = /"pick_code"\s*:\s*"([^"]+)"/g, m, uniq = {};
      while ((m = re.exec(html))) {
        if (!uniq[m[1]]) {
          uniq[m[1]] = 1;
          items.push({ pick_code: m[1], station: "", address: "", shipping: "", tracking: "", time: "" });
        }
      }
    }
    return items;
  }
})();
