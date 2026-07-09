// v2exopen_shadowrocket.js
// 说明: V2EX 页面拦截脚本，将非白名单客户端跳转到 app 方案（Shadowrocket版本）
// 在Shadowrocket配置中添加:
// http-request ^https:\/\/www\.v2ex\.com/t/(\d+) script-path=v2exopen_shadowrocket.js, requires-body=false

const url = $request.url;
const headers = $request.headers || {};

// Shadowrocket headers 可能全是小写，统一处理
const userAgent = (
  headers['User-Agent'] || 
  headers['user-agent'] || 
  headers['USER-AGENT'] || 
  ''
).toLowerCase();

// 仅在 iOS 设备上执行
const isIOS = /iphone|ipad|ipod/i.test(userAgent);
if (!isIOS) {
  $done({});
  return;
}

// 白名单客户端
const allowClients = ['V2Fun', 'Vetiver'].map((c) => c.toLowerCase());
const openapp = 'V2Fun';
const openappScheme = openapp.toLowerCase();

// 白名单检查
if (allowClients.some((c) => userAgent.includes(c))) {
  $done({});
  return;
}

// URL 话题页检查
const topicMatch = url.match(/^https:\/\/www\.v2ex\.com\/t\/(\d+)/);
if (!topicMatch) {
  $done({});
  return;
}

// 302 重定向
$done({
  response: {
    status: 302,
    headers: {
      'Location': `${openappScheme}://topic/${topicMatch[1]}`
    }
  }
});