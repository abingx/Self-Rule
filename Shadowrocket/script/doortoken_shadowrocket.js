//* 
// doortoken_shadowrocket.js
// 说明: 接收目标接口登录返回，解析 access_token 并持久化（Shadowrocket版本）
// 触发条件: 微信内访问 http://api.jzznck.com:8080/api/passport/sso/WeChatAuthorize
// 执行流程:
//   1. 解析 $response.body
//   2. 提取 token 候选字段
//   3. 写入 $persistentStore(path=doortoken)
// 在Shadowrocket配置中添加:
// http-response http:\/\/api\.jzznck\.com:8080\/api\/passport\/sso\/WeChatAuthorize script-path=doortoken_shadowrocket.js, requires-body=true

const responseBody = $response.body;
let responseObj = null;

try {
	responseObj = JSON.parse(responseBody);
} catch (e) {
	console.log('Failed to parse response body:', e);
	$done({});
	return;
}

// tokenCandidates: 尝试多个可能的字段名，因接口返回结构可能变动
// 优先级：data.access_token -> data.token -> access_token -> token
const tokenCandidates = [
	responseObj?.data?.access_token,
	responseObj?.data?.token,
	responseObj?.access_token,
	responseObj?.token
];

const token = tokenCandidates.find((item) => typeof item === 'string' && item.length > 10);

if (token) {
	// Shadowrocket 持久化存储：write(value, key)
	$persistentStore.write(token, 'doortoken');
	
	// Shadowrocket 通知方式
	$notification.post('获取开门token', '✅ access-token获取成功🎉', '');
	console.log(`doortoken recorded: ${token}`);
} else {
	console.log('No doortoken found in response body:', responseObj);
}

$done({});
