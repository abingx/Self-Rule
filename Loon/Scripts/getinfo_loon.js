//* 
// getinfo_loon.js
// 说明: 订阅信息接口查询脚本（机场流量查询）
// 触发条件: get https://loonjs.ai/getinfo（argument 传递 barkkey=xxx&url=xxx 或 url=xxx&barkkey=xxx）
// 主要流程:
//   1. 获取 $argument / 默认机场列表
//   2. 请求 subscription-userinfo 头部获取流量数据
//   3. 解析数据，构造消息、计算重置及到期时间
//   4. 发送通知与返回结构化 JSON
// */
// http-request ^https:\/\/loonjs\.ai\/getinfo$ script-path=getinfo_loon.js, timeout=20, tag=getinfo, argument="barkkey=xxxxxxx&url=https://url"

// 默认机场配置（当未传入 argument 时使用）
function parseArgument(argument) {
	if (typeof argument !== 'string' || !argument.trim()) return null;
	const trimmed = argument.trim();
	let barkKey = '';
	let url = trimmed;

	// 支持：
	// 1) barkkey=xxxx&url=https://test.com
	// 2) url=https://test.com&barkkey=xxxx
	// 3) 下游兼容原始 url
	const pairs = trimmed.split('&').map((item) => item.trim()).filter(Boolean);
	const map = {};
	for (const pair of pairs) {
		const [k, ...rest] = pair.split('=');
		const v = rest.join('=');
		if (!k || !v) continue;
		map[k.trim().toLowerCase()] = v.trim();
	}

	if (map.barkkey) {
		barkKey = map.barkkey;
	}
	if (map.url) {
		url = map.url;
	}

	if (!map.barkkey && !map.url && pairs.length === 2) {
		// 兼容老写法 barkKey&URL 或 URL&barkKey
		if (/^https?:\/\//i.test(pairs[0]) && !/^https?:\/\//i.test(pairs[1])) {
			url = pairs[0];
			barkKey = pairs[1];
		} else if (!/^https?:\/\//i.test(pairs[0]) && /^https?:\/\//i.test(pairs[1])) {
			barkKey = pairs[0];
			url = pairs[1];
		}
	}

	return { barkKey, url };
}

const parsedArg = parseArgument($argument);
const { url, barkKey } = parsedArg || { url: '', barkKey: '' };

const DEFAULT_AIRPORTS = [
	{
		url: url || '',
		title: 'FlowerCloud',
		reset_day: 21,
		barkKey: barkKey || '',
	},
];

// 读取入口参数，支持：
// 1. 单个字符串，格式 barkkey=xxxx&url=https://xxxx
// 2. 数组形式 [{url,title,reset_day,barkKey},...]
// 3. 无参数时使用默认机场
let args = [];
if (typeof $argument === 'string' && $argument.trim()) {
	if (parsedArg && parsedArg.url) {
		args.push({ url: parsedArg.url, title: 'FlowerCloud', reset_day: 21, barkKey: parsedArg.barkKey || '' });
	} else {
		args.push({ url: $argument.trim(), title: 'FlowerCloud', reset_day: 21, barkKey: '' });
	}
} else if (Array.isArray($argument) && $argument.length) {
	args = $argument.map((item) => {
		const parsedItem = parseArgument(item.url || '');
		return {
			url: parsedItem?.url || item.url,
			title: item.title || '机场',
			reset_day: item.reset_day || 0,
			expire: item.expire,
			barkKey: item.barkKey || parsedItem?.barkKey || '',
		};
	});
} else {
	args = DEFAULT_AIRPORTS;
}

// 主逻辑入口（异步执行）
// 对每个机场：获取订阅信息 -> 解析 -> 组装通知与结果集
!(async () => {
	try {
		const messages = [];
		const results = [];

		for (const arg of args.reverse()) {
			const info = await getDataInfo(arg.url);
			if (!info) {
				results.push({ title: arg.title, error: "获取失败" });
				continue;
			}

			const message = buildAirportMessage(arg, info);
			if (message) {
				messages.push(message);
			}

			// 构建结构化结果供响应体使用
			const used = info.download + info.upload;
			results.push({
				title: arg.title,
				used: bytesToSize(used),
				total: bytesToSize(info.total),
				expire: formatExpiry(arg.expire || info.expire),
				reset_days_left: arg.reset_day ? getRemainingDays(parseInt(arg.reset_day, 10)) : null,
			});
		}

		// 所有机场信息汇总后，发送通知（如无内容则不发送）
		const notifyText = messages.join("\n\n");
		if (notifyText) {
			const effectiveBarkKey = args.find((item) => item.barkKey && item.barkKey.trim())?.barkKey.trim() || '';
			await sendNotification(notifyText, effectiveBarkKey);
		}

		// 统一返回结果给调用方
		$done({
			response: {
				status: 200,
				headers: {
					"Content-Type": "application/json; charset=utf-8",
					"Access-Control-Allow-Origin": "*",
				},
				body: JSON.stringify({
					success: true,
					data: results,
				}),
			},
		});
	} catch (error) {
		console.log(`Error: ${error}`);
		$done({
			response: {
				status: 500,
				headers: {
					"Content-Type": "application/json; charset=utf-8",
				},
				body: JSON.stringify({
					success: false,
					error: String(error),
				}),
			},
		});
	}
})();

/**
 * 构建单个机场的消息
 * 参数：
 *   arg: {title,url,reset_day,expire}
 *   info: {download,upload,total,expire...}
 * 返回：格式化后多行字符串，供通知使用
 */
function buildAirportMessage(arg, info) {
	const lines = [`机场：${arg.title}`];

	// 添加流量使用信息
	const used = info.download + info.upload;
	const total = info.total;
	lines.push(`用量：${bytesToSize(used)} | ${bytesToSize(total)}`);

	// 添加重置天数信息（如果有）
	if (arg.reset_day) {
		const resetDayLeft = getRemainingDays(parseInt(arg.reset_day));
		if (resetDayLeft) {
			lines.push(`重置：剩余${resetDayLeft}天`);
		}
	}

	// 添加到期时间信息（如果有）
	const expired = formatExpiry(arg.expire || info.expire);
	if (expired) {
		lines.push(`到期：${expired}`);
	}

	return lines.join("\n");
}

/**
 * 发送通知
 * 支持同时推送到多个通知地址，当前为一个 day.app 组合
 * 失败不影响主流程（放宽通知失败容错）
 */
async function sendNotification(message, barkKey = '') {
	if (!barkKey || !barkKey.trim()) {
		// 未配置 barkKey 时发本地通知提醒，并在日志中输出消息内容
		$notification.post('机场流量', '', '请配置 barkKey 后再发送到推送服务');
		console.log('未配置 barkKey，消息内容：', message);
		return;
	}

	const title = encodeURIComponent("机场流量");
	const encodedMessage = encodeURIComponent(message);
	const key = barkKey.trim();
	const baseUrls = [`https://api.day.app/${key}`];
	const urls = baseUrls.map((base) => {
		return `${base}/${title}/${encodedMessage}?group=机场流量&sound=bell`;
	});

	// 同时发送到两个地址
	const promises = urls.map((url) => {
		const request = {
			url: url,
			headers: {
				"User-Agent": "Loon",
			},
		};

		return new Promise((resolve) => {
			$httpClient.get(request, (error, response, data) => {
				if (error) {
					console.log(`Notification request error for ${url}: ${error}`);
				}
				resolve();
			});
		});
	});

	// 等待所有通知发送完成
	await Promise.all(promises);
}

/**
 * 获取用户订阅信息
 */
async function getUserInfo(url) {
	return new Promise((resolve) => {
		const request = {
			url: url,
			headers: {
				"User-Agent": "Surge%20iOS/3556",
			},
		};

		let timeout = setTimeout(() => {
			console.log(`Request timeout for ${url}`);
			resolve(null);
		}, 5000);

		$httpClient.head(request, (error, response, data) => {
			clearTimeout(timeout);
			if (error) {
				console.log(`Request error for ${url}: ${error}`);
				resolve(null);
				return;
			}

			if (response.status !== 200) {
				console.log(`Request failed with status code: ${response.status}`);
				resolve(null);
				return;
			}

			const headerValue = response.headers['subscription-userinfo'] || response.headers['Subscription-Userinfo'];
			if (headerValue) {
				resolve(headerValue);
			} else {
				console.log('Response headers do not contain traffic information');
				resolve(null);
			}
		});
	});
}

/**
 * 解析并获取数据信息
 */
async function getDataInfo(url) {
	try {
		const data = await getUserInfo(url);
		if (!data || typeof data !== 'string') {
			console.log(`No subscription data from ${url}`);
			return null;
		}

		const pairs = data.match(/\w+=[\d.eE+-]+/g);
		if (!pairs) {
			console.log(`No subscription-userinfo fields found for ${url}: ${data}`);
			return null;
		}

		return Object.fromEntries(
			pairs
				.map((item) => item.split('='))
				.map(([k, v]) => [k, Number(v)])
		);
	} catch (error) {
		console.log(`Failed to get data info for ${url}: ${error}`);
		return null;
	}
}

/**
 * 计算距离重置日的剩余天数
 */
function getRemainingDays(resetDay) {
	if (!resetDay || resetDay < 1 || resetDay > 31) return null;

	const now = new Date();
	const today = now.getDate();
	const currentMonth = now.getMonth();
	const currentYear = now.getFullYear();

	// 如果重置日还没到，计算到本月重置日的天数
	if (resetDay > today) {
		return resetDay - today;
	}

	// 如果重置日已过，计算到下个月重置日的天数
	const daysInCurrentMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
	return daysInCurrentMonth - today + resetDay;
}

/**
 * 将字节转换为可读格式
 */
function bytesToSize(bytes) {
	if (bytes === 0) return "0 B";

	const k = 1024;
	const sizes = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"];
	const i = Math.floor(Math.log(bytes) / Math.log(k));

	return (bytes / Math.pow(k, i)).toFixed(2) + " " + sizes[i];
}

/**
 * 格式化时间戳为日期字符串
 */
function formatTime(timestamp) {
	const date = new Date(timestamp);

	// 检查日期是否有效
	if (isNaN(date.getTime())) {
		return "日期无效";
	}

	const year = date.getFullYear();
	const month = date.getMonth() + 1;
	const day = date.getDate();

	return `${year}年${month}月${day}日`;
}

/**
 * 将时间戳标准化并格式化为日期字符串
 */
function formatExpiry(expireValue) {
	if (!expireValue) return null;

	let expire = Number(expireValue);
	if (Number.isNaN(expire)) {
		if (/^[\d.]+$/.test(expireValue)) {
			expire = Number(expireValue);
		} else {
			return null;
		}
	}

	if (expire < 10000000000) {
		expire *= 1000;
	}

	const formatted = formatTime(expire);
	return formatted === '日期无效' ? null : formatted;
}
