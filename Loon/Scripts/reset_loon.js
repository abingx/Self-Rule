//* 
// reset_loon.js
// 说明: Loon 脚本，用于切换分流策略及运行模型
// 触发条件: post https://loonjs.ai/reset（需要 body）
// 主要流程:
//   1. 解析请求体为 JSON
//   2. model 结构遍历设置策略 $config.setSelectPolicy
//   3. 设置运行模型 $config.setRunningModel(1)
//   4. 返回全面策略状态
// */
// http-request ^https:\/\/loonjs\.ai\/reset$ script-path=reset_loon.js, requires-body=true, timeout=20, tag=reset

// 解析请求体，将分流模型配置从字符串转换为对象
// 如果请求体不是合法 JSON，返回 400 并退出
let body;
try {
	body = JSON.parse($request.body);
} catch (e) {
	console.log('reset_loon: 无法解析请求体', e);
	$done({
		response: {
			status: 400,
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ success: false, message: 'Invalid request body' })
		}
	});
	return;
}

// model 支持两种形式：直接对象或 JSON 字符串
const model = typeof body.model === 'string' ? JSON.parse(body.model) : body.model;

// 校验 model 是否为合法对象
if (!model || typeof model !== 'object') {
	console.log('reset_loon: model 参数错误', body);
	$done({
		response: {
			status: 400,
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ success: false, message: 'Invalid model parameter' })
		}
	});
	return;
}

const results = {};

// 遍历每个策略项并依次设置
// 返回每个策略设置结果，以便外部核对是否生效
for (const [policyName, selectName] of Object.entries(model)) {
	const success = $config.setSelectPolicy(policyName, selectName);
	results[policyName] = { select: selectName, success };
}

// 切换当前运行模型到分流模式
const modelSuccess = $config.setRunningModel(1);

$done({
	response: {
		status: 200,
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			runningModel: { model: '分流模式', success: modelSuccess },
			policies: results
		})
	}
});