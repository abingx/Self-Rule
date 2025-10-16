let args = [
	{
		url: "{url}",
		title: "Amytelecom",
		reset_day: 11
	}
];

!(async () => {
	try {
		const messages = [];

		// 反转数组以获得期望的顺序
		for (const arg of args.reverse()) {
			const info = await getDataInfo(arg.url);
			if (!info) continue;

			// 构建单个机场的信息
			const message = buildAirportMessage(arg, info);
			if (message) {
				messages.push(message);
			}
		}

		// 使用统一的分隔符连接所有消息
		const result = messages.join('\n\n');

		if (result) {
			await sendNotification(result);
		}

		$done();
	} catch (error) {
		console.log(`Error: ${error}`);
		$done();
	}
})();

/**
 * 构建单个机场的消息
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
	let expire = arg.expire || info.expire;
	if (expire) {
		// 如果是秒级时间戳，转换为毫秒
		if (/^[\d.]+$/.test(expire) && expire < 10000000000) {
			expire *= 1000;
		}
		lines.push(`到期：${formatTime(expire)}`);
	}

	return lines.join('\n');
}

/**
 * 发送通知
 */
async function sendNotification(message) {
	const title = encodeURIComponent("机场流量");
	const encodedMessage = encodeURIComponent(message);
	const baseUrls = [
		'https://api.day.app/dzvjx4SKAH',
		'https://api.day.app/sVZ3K8wZJ'
	];
	const urls = baseUrls.map(base => {
		return `${base}/${title}/${encodedMessage}?group=机场流量&sound=bell`;
	});

	// 同时发送到两个地址
	const promises = urls.map(url => {
		const request = {
			url: url,
			headers: {
				'User-Agent': 'Surge'
			}
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
				'User-Agent': 'Surge%20iOS/3556'
			}
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

			const headerValue = response.headers['subscription-userinfo'];
			if (headerValue) {
				resolve(headerValue);
			} else {
				console.log("Response headers do not contain traffic information");
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
		return Object.fromEntries(
			data
				.match(/\w+=[\d.eE+-]+/g)
				.map((item) => item.split("="))
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