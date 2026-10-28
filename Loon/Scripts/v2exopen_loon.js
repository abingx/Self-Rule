//* 
// v2exopen_loon.js
// 说明: V2EX 页面拦截脚本，仅在「需要跳转 app」时返回 302，其他一切请求保持原样（不修改任何内容）
// 触发条件: GET 访问 V2EX 话题页（https://www.v2ex.com/t/xxx），非 GET 请求不处理
// 平台支持: 全平台生效（不再限制 iOS）
// 主要逻辑:
//   1. 读取请求方法、URL 和 UA
//   2. 仅处理 GET 请求，其他方法（PUT/POST/DELETE 等）原样返回
//   3. 如果是允许的客户端（V2Fun/Vetiver/V2Echo），保持原样返回
//   4. 如果 Referer 指向 v2ex（站内跳转，如收藏/取消收藏成功后回跳），保持原样返回
//   5. 以上都不满足、且命中 /t/xxx 话题页时，才返回 302 Location => 目标方案（见下方 appTargets）
//   —— 除第 5 步外，脚本不做任何改写
// 传参说明:
//   通过 argument 传入目标 App（不区分大小写，默认 V2Echo）
//   可选值见下方 appTargets，例: argument=app=V2Echo
// */
// Loon 配置示例（新语法）:
// request if ${url} ~= /^https:\/\/www\.v2ex\.com\/t\/(\d+)$/i then script("https://raw.githubusercontent.com/abingx/Self-Rule/main/Loon/Scripts/v2exopen_loon.js", "V2Echo") with tag="v2exopen"

// 入口参数抓取：请求方法、URL 与 User-Agent
const method = ($request.method || 'GET').toUpperCase();
const url = $request.url;
const headers = $request.headers || {};
const userAgent = (headers['User-Agent'] || headers['user-agent'] || '').toLowerCase();

// 非 GET 请求：原样返回，不做修改
if (method !== 'GET') {
	$done({});
	return;
}

// 目标映射：{id} 会被替换为实际话题 ID，支持 scheme 与网页地址
const appTargets = {
	v2fun: 'v2fun://topic/{id}',
	v2echo: 'v2echo://www.v2ex.com/t/{id}',
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

// 白名单客户端：原样返回，不做修改
if (allowClients.some((c) => userAgent.includes(c))) {
	$done({});
	return;
}

// 站内跳转：原样返回，不做修改。Referer 指向 v2ex 说明这是 V2EX 自身发起的跳转
// 典型场景：收藏/取消收藏成功后，服务端 302 => https://www.v2ex.com/t/xxx，
// app 依赖这一步的 http 302 判定操作成功；若在此改写成 v2echo:// 会被误判为「操作失败」（实际已生效）。
// 外部打开链接时 Referer 为站外地址或为空，不受影响，仍会跳转 app。
const referer = (headers['Referer'] || headers['referer'] || '').toLowerCase();
if (/\/\/([a-z0-9-]+\.)*v2ex\.com(\/|$)/.test(referer)) {
	$done({});
	return;
}

// 非 /t/xxx 话题页：原样返回，不做修改
const topicMatch = url.match(/^https:\/\/www\.v2ex\.com\/t\/(\d+)$/i);
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