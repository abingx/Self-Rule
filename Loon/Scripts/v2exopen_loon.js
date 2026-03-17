//* 
// v2exopen_loon.js
// 说明: V2EX 页面拦截脚本，将非白名单客户端跳转到 app 方案
// 触发条件: 访问 V2EX 话题页（https://www.v2ex.com/t/xxx）
// 主要逻辑:
//   1. 读取请求 URL 和 UA
//   2. 如果是允许的客户端（V2Fun/Vetiver），保持原样返回
//   3. 否则返回 302 Location => app scheme（V2Fun）
// */
// http-request ^https:\/\/www\.v2ex\.com/t/(\d+) script-path=v2exopen_loon.js, timeout=20, tag=v2exopen

// 入口参数抓取：URL 与 User-Agent
const url = $request.url;
const headers = $request.headers || {};
const userAgent = (headers['User-Agent'] || headers['user-agent'] || '').toLowerCase();

// 仅在 iOS 设备上执行白名单判断和重定向
const isIOS = /iphone|ipad|ipod/i.test(userAgent);
if (!isIOS) {
	$done({});
	return;
}

// 白名单客户端列表，遇到这些 UA 不做重定向
const allowClients = ['V2Fun', 'Vetiver'].map((c) => c.toLowerCase());
// 目标 App Scheme（可按需要切换为 V2Explorer）
const openapp = 'V2Fun';
const openappScheme = openapp.toLowerCase();

// 如果是白名单客户端，保持请求直通（不改写 URL）
if (allowClients.some((c) => userAgent.includes(c))) {
	$done({});
	return;
}

// 仅处理符合 /t/xxx 话题页格式的 URL，其他请求原样返回
const topicMatch = url.match(/^https:\/\/www\.v2ex\.com\/t\/(\d+)/);
if (!topicMatch) {
	$done({});
	return;
}

// 采用 302 临时重定向到客户端 app Scheme，携带话题 ID
$done({
	response: {
		status: 302,
		headers: {
			Location: `${openappScheme}://topic/${topicMatch[1]}`
		}
	}
});