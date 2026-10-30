/*
 * 拼多多 Cookie 自动捕获 —— Loon「request」脚本
 * ------------------------------------------------------------
 * 作用：只要拼多多客户端访问 m.pinduoduo.net（H5 页面/接口），
 *      就把该请求头里的完整 Cookie 等信息合并成一个 JSON 写入持久化。
 *
 * 只使用一个键：
 *   pdd_session = {
 *     cookie: "完整 Cookie（含 PDDAccessToken / pdd_user_id / _nano_fp 等）",
 *     ua:     "当时的 User-Agent",
 *     hdr:    { x-pdd-queries, x-pdd-info, x-client-language, x-client-region, x-app-ui, x-yak-llt },
 *     ts:     "捕获时间 ISO",
 *     time:   捕获时间戳（毫秒）
 *   }
 *
 * 说明：只有带 PDDAccessToken 的 Cookie 才会被保存，避免把登录页等无效会话覆盖进来。
 */

(function () {
  var KEY_SESSION = "pdd_session";
  var h = ($request && $request.headers) || {};
  var cookie = h["Cookie"] || h["cookie"] || "";

  // 没有登录态就跳过
  if (!cookie || cookie.indexOf("PDDAccessToken=") < 0) {
    return $done({});
  }

  var old = {};
  try { old = JSON.parse($persistentStore.read(KEY_SESSION) || "{}") || {}; } catch (e) {}
  if (old.cookie === cookie) {
    return $done({}); // Cookie 没变化不重复写
  }

  var session = {
    cookie: cookie,
    ua: h["User-Agent"] || h["user-agent"] || "",
    hdr: {
      "x-pdd-queries": h["x-pdd-queries"] || h["X-Pdd-Queries"] || "",
      "x-pdd-info": h["x-pdd-info"] || h["X-Pdd-Info"] || "",
      "x-client-language": h["x-client-language"] || "",
      "x-client-region": h["x-client-region"] || "",
      "x-app-ui": h["x-app-ui"] || "",
      "x-yak-llt": h["x-yak-llt"] || ""
    },
    ts: new Date().toISOString(),
    time: Date.now()
  };

  $persistentStore.write(JSON.stringify(session), KEY_SESSION);

  console.log("[PDD] Cookie 已更新，长度=" + cookie.length);

  // 捕获/更新成功后弹通知（Cookie 没变化时不会走到这里，不会刷屏）
  var ts = session.ts.substring(11, 19);
  $notification.post(
    "拼多多 Cookie",
    old.cookie ? "已更新" : "捕获成功",
    "长度 " + cookie.length + " · " + ts
  );

  $done({});
})();
