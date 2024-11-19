// Surge脚本：记录响应体中的 access_token
// 获取响应体内容
const responseBody = $response.body;
// 解析响应体为 JSON 对象
let responseObj = null;
try {
	responseObj = JSON.parse(responseBody);
} catch (e) {
	console.log('Failed to parse response body');
}
// 检查并提取 access_token
if (responseObj && responseObj.data && responseObj.data.access_token) {
	const token = responseObj.data.access_token;
	// 将 token 存储在持久化存储中，键名为 'doortoken'
	$persistentStore.write(token, 'doortoken');
	$notification.post('芝麻开门', '', 'access-token获取成功🎉', {
		"auto-dismiss": 5
	});
	// 输出日志
	console.log(`doortoken recorded: ${token}`);
} else {
	$notification.post('芝麻开门', '', 'access-token获取未成功💀', {
		"auto-dismiss": 5
	});
	// 如果没有找到 token，输出日志
	console.log('No doortoken found in response body.');
}
// 完成脚本执行
$done({});

