const args = $argument.split("&");
let wifiNow, lanHost;
args.forEach(arg => {
    const [key, value] = arg.split("=");
    if (key === "wifiNow") wifiNow = value.trim().replace(/"/g, '');
    if (key === "lanHost") lanHost = value.trim().replace(/"/g, '');
});

const wifiName = $network.wifi.ssid;
let url = $request.url;
let headers = { ...$request.headers };

console.log(wifiName);
console.log(url);
console.log(wifiNow);
console.log(lanHost);

if (wifiName && wifiName.includes(wifiNow)) {
		url = url.replace(/https:\/\/alist\.allinhub\.top(:\d+)?/, `http://${lanHost}:5244`);
		console.log(url);
		console.log(headers[':authority']);
		if (headers[':authority']) {
			headers[':authority'] = 'mac-mini.local';
		}
		console.log(headers.referer);
		if (headers.referer) {
			headers.referer = 'mac-mini.local';
		}
		console.log(headers.cookie);
	$done({ url: url, headers: headers });
} else {
	console.log("Condition not met. Keeping original URL.");
	$done({});
}
