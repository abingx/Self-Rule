//* 
// v2exopen_loon.js
// 说明: V2EX 页面拦截脚本，将非白名单客户端跳转到 app 方案
// 触发条件: 访问 V2EX 话题页（https://www.v2ex.com/t/xxx）
// 主要逻辑:
//   1. 读取请求 URL 和 UA
//   2. 如果是允许的客户端（V2Fun/Vetiver/V2Echo），保持原样返回
//   3. 否则返回 302 Location => 目标方案（见下方 appTargets）
// 传参说明:
//   通过 argument 传入目标 App（不区分大小写，默认 V2Echo）
//   可选值见下方 appTargets，例: argument=app=V2Echo
// */
// http-request ^https:\/\/www\.v2ex\.com/t/(\d+) script-path=v2exopen_loon.js, argument=app=V2Echo, timeout=20, tag=v2exopen

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

// 目标映射：{id} 会被替换为实际话题 ID，支持 scheme 与网页地址
const appTargets = {
	v2fun: 'v2fun://topic/{id}',
	v2echo: 'https://app.v2echo.com/t/{id}',
	vetiver: 'v2explorer://topic/{id}'
};

// 解析传入参数 app（兼容 "app=V2Echo" / "V2Echo" / 无参数 三种写法）
function parseAppArgument(raw) {
	if (!raw) return 'V2Echo';
	const str = String(raw).trim();
	// 形如 app=V2Echo&foo=bar 或直接 V2Echo
	const matched = str.match(/(?:^|&)app=([^&]+)/i);
	return matched ? matched[1] : str;
}

const openapp = parseAppArgument(typeof $argument !== 'undefined' ? $argument : '');
const openappKey = openapp.toLowerCase();
const targetTemplate = appTargets[openappKey] || `${openappKey}://topic/{id}`;

// 白名单客户端列表：UA 命中即直通，不再被重定向
// 白名单与跳转目标彼此独立：V2Fun/V2Echo/Vetiver 既是白名单，也可作为 openapp 跳转目标
const allowClients = ['V2Fun', 'Vetiver', 'V2Echo'].map((c) => c.toLowerCase());

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

// 采用 302 临时重定向到目标地址，携带话题 ID
$done({
	response: {
		status: 302,
		headers: {
			Location: targetTemplate.replace('{id}', topicMatch[1])
		}
	}
});