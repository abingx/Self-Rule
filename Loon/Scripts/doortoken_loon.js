//* 
// doortoken_loon.js
// 说明: 接收目标接口登录返回，解析 access_token 并持久化
// 触发条件: 微信内访问 http://api.jzznck.com:8080/api/passport/sso/WeChatAuthorize
// 执行流程:
//   1. 解析 $response.body
//   2. 提取 token 候选字段
//   3. 写入 $persistentStore(path=doortoken)
// */
// http-response http:\/\/api\.jzznck\.com:8080\/api\/passport\/sso\/WeChatAuthorize script-path=doortoken_loon.js, requires-body=true, timeout=20, tag=doortoken

const responseBody = $response.body;
let responseObj = null;

try {
	responseObj = JSON.parse(responseBody);
} catch (e) {
	console.log('Failed to parse response body:', e);
	$notification.post('芝麻开门', '', 'access-token解析失败，请检查登录流程', '');
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
	$persistentStore.write(token, 'doortoken');
	$notification.post('芝麻开门', '', 'access-token获取成功🎉');
	console.log(`doortoken recorded: ${token}`);
} else {
	console.log('No doortoken found in response body:', responseObj);
	//$notification.post('芝麻开门', '', 'access-token未找到，请检查响应', '');
}

$done({});
