//* 
// opendoor_loon.js
// 说明: Loon 脚本 - 另一条开门接口路径（ID 不同）
// 触发条件: http-request ^https://loonjs.ai/opendoor$
// 逻辑同 dooropen_loon.js，仅 OPEN_ID 不同
// */
// http-request ^https:\/\/loonjs\.ai\/(opendoor|dooropen)$ script-path=opendoor_loon.js, timeout=20, tag=opendoor, argument="opendoor=<id>&dooropen=<id>"

// 根据请求 URL 结尾决定使用哪个 ID
function parseArgument(arg) {
	const params = {};
	if (!arg || typeof arg !== 'string') {
		return params;
	}
	arg.split('&').forEach(item => {
		const [key, value] = item.split('=');
		if (key && value) {
			params[key] = decodeURIComponent(value);
		}
	});
	return params;
}

function resolveOpenId() {
	const args = parseArgument($argument);
	let path = '';
	try {
		if ($request && $request.url) {
			path = new URL($request.url).pathname || '';
		}
	} catch (e) {
		console.log('解析请求 URL 失败：', e);
	}

	if (path.endsWith('/opendoor') && args.opendoor) {
		return args.opendoor;
	}
	if (path.endsWith('/dooropen') && args.dooropen) {
		return args.dooropen;
	}

	// 兼容旧行为：直接传 id 且没有 key
	if (typeof $argument === 'string' && !$argument.includes('=')) {
		return $argument;
	}

	return null;
}

const OPEN_ID = resolveOpenId();

const DEFAULT_CONFIG = {
	url: 'http://api.jzznck.com:8080/api/basics/appCore/scann',
	appSecret: 'vLtagGH6WUG8gaYK',
	origin: 'http://www.jzznck.com',
	referer: 'http://www.jzznck.com/',
	userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.53(0x1800352e) NetType/4G Language/zh_CN'
};

// notify: 统一通知格式输出，日志级别与通知渠道统一入口
//   title: 标题
//   subtitle: 子标题
//   message: 内容
//   url: 点击后跳转链接，可选
function notify(title, subtitle, message, url = '') {
	$notification.post(title, subtitle, message, url);
}

// done: 统一结果返回封装，防止重复格式错误
function done(status, payload) {
	$done({
		response: {
			status: status,
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		}
	});
}

// resolveToken: 检查持久化 token 并在缺失时直接结束流程
//   返回：token 字符串或 null（表示未找到）
function resolveToken() {
	const token = $persistentStore.read('doortoken');
	if (!token) {
		console.log('No doortoken found in persistent storage.');
		notify('芝麻开门', '', 'access-token 未找到，请重新获取', 'wechat://');
		done(401, { success: false, message: 'No doortoken found' });
		return null;
	}
	return token;
}

// buildHeaders: 构造请求头，包含鉴权 token
function buildHeaders(token) {
	return {
		Host: 'api.jzznck.com:8080',
		Accept: 'application/json, text/javascript, */*; q=0.01',
		'app-secret': DEFAULT_CONFIG.appSecret,
		'Accept-Encoding': 'gzip, deflate',
		'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
		'Content-Type': 'application/json',
		Origin: DEFAULT_CONFIG.origin,
		'User-Agent': DEFAULT_CONFIG.userAgent,
		Connection: 'keep-alive',
		Referer: DEFAULT_CONFIG.referer,
		'x-access-token': token
	};
}

// isOpenSuccess: 判定 response 是否标识开门成功
function isOpenSuccess(result) {
	if (!result) {
		return false;
	}
	if (typeof result.message === 'string' && result.message.includes('openResult=True')) {
		return true;
	}
	if (result.code === 0 || result.result === 'success') {
		return true;
	}
	return false;
}

// openDoor: 主流程 - 发起开门请求 -> 处理错误/成功/过期
function openDoor(id) {
	const token = resolveToken();
	if (!token) {
		return;
	}

	$httpClient.post({
		url: DEFAULT_CONFIG.url,
		headers: buildHeaders(token),
		body: JSON.stringify({ id })
	}, (error, response, body) => {
		if (error) {
			console.log('请求错误:', error);
			notify('芝麻开门', '', '请求失败: ' + error, '');
			done(500, { success: false, message: 'Request failed: ' + error });
			return;
		}

		let parsed;
		try {
			parsed = typeof body === 'string' ? JSON.parse(body) : body;
		} catch (e) {
			console.log('Error parsing response data:', e);
			notify('芝麻开门', '', '返回解析失败', '');
			done(502, { success: false, message: 'Parse error' });
			return;
		}

		const success = isOpenSuccess(parsed);
		if (success) {
			notify('芝麻开门', '', '开门成功🎉');
			done(200, { success: true, message: '开门成功' });
			return;
		}

		if (parsed && typeof parsed.message === 'string' && parsed.message.includes('token') && !parsed.message.includes('openResult=True')) {
			$persistentStore.write('', 'doortoken');
			notify('芝麻开门', '', 'access-token失效，已清理，请重新获取', 'wechat://');
			done(401, { success: false, message: 'Token expired' });
			return;
		}

		console.log('开门请求返回：', parsed);
		notify('芝麻开门', '', '开门失败：' + (parsed.message || '未知原因'), '');
		done(200, { success: false, message: parsed.message || '开门失败' });
	});
}

if (!OPEN_ID) {
	console.log('OPEN_ID 未获取，参数可能有误：', $argument);
	notify('芝麻开门', '', '未找到有效的 OPEN_ID，请检查参数', '');
	done(400, { success: false, message: 'Invalid OPEN_ID' });
} else {
	openDoor(OPEN_ID);
}
