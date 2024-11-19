// 获取持久化存储中的 doortoken
const token = $persistentStore.read('doortoken');
// 如果没有找到 token，输出错误信息并结束执行
if (!token) {
    console.log('No doortoken found in persistent storage.');
    $done({});
}
// 设置请求参数
const url = 'http://api.jzznck.com:8080/api/basics/appCore/scann';
const headers = {
    'Host': 'api.jzznck.com:8080',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'app-secret': 'vLtagGH6WUG8gaYK',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
    'Content-Type': 'application/json',
    'Origin': 'http://www.jzznck.com',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.53(0x1800352e) NetType/4G Language/zh_CN',
    'Connection': 'keep-alive',
    'Referer': 'http://www.jzznck.com/',
    'x-access-token': token // 使用从持久化存储中读取的 token
};
// 请求的数据
const data = {
    id: 'd100187_123323073_1_1'
};
// 发送 POST 请求
$httpClient.post({
    url: url,
    headers: headers,
    body: JSON.stringify(data)
}, function (error, response, data) {
    if (error) {
        console.log(error);
    } else {
        console.log(response);
        console.log(data);
        // 假设数据是 JSON 格式，解析 response 数据
        try {
            const parsedData = JSON.parse(data);
            if (parsedData.message && !parsedData.message.includes('openResult=True')) {
                // 如果 message 不包含 openResult=True，弹出通知
                $notification.post('芝麻开门', '', 'access-token失效，点击后需重新获', {
                    "action": "open-url",
                    "url": "wechat://"  // 你想跳转的 URL
                });
            } else {
				$notification.post('芝麻开门', '', '开门成功🎉', {
					"auto-dismiss": 5  
				});
			}
        } catch (e) {
            console.log('Error parsing response data:', e);
        }
    }
    // 完成脚本执行
    $done({});
});