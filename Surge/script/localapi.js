const args = $argument.split("&");
let wifiNow, lanHost;
args.forEach(arg => {
    const [key, value] = arg.split("=");
    if (key === "wifiNow") wifiNow = value.trim().replace(/"/g, '');
    if (key === "lanHost") lanHost = value.trim().replace(/"/g, '');
});

const wifiName = $network.wifi.ssid;
let url = $request.url;
let headers = JSON.parse(JSON.stringify($request.headers));

console.log(wifiName);
console.log(url);
console.log(wifiNow);
console.log(lanHost);

if (wifiName && wifiName.includes(wifiNow)) {
		if (url.includes("https://qwen.allinhub.top")) {
			url = url.replace("https://qwen.allinhub.top", `http://${lanHost}:8000`);
		} else if (url.includes("https://metaso.allinhub.top")) {
			url = url.replace("https://metaso.allinhub.top", `http://${lanHost}:8001`);
		} else if (url.includes("https://kimi.allinhub.top")) {
			url = url.replace("https://kimi.allinhub.top", `http://${lanHost}:8002`);
		}
		if (headers['authorization']) {
			headers['Authorization'] = headers['authorization'];
			delete headers['authorization'];
		}
		delete headers['host'];
		delete headers['Host'];
		console.log(url);
		$done({ url: url, headers: headers});
} else {
	console.log("Condition not met. Keeping original URL.");
	$done({});
}
