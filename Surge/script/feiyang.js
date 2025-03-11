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
	url = url.replace(/https:\/\/feiyang\.allinhub\.top(:\d+)?/, `http://${lanHost}:35455`);
	console.log(url);
	$done({ url: url, headers: headers });
} else {
	console.log("Condition not met. Keeping original URL.");
	$done({});
}
