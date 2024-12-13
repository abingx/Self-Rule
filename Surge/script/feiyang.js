const wifiName = $network.wifi.ssid;
let url = $request.url;
let headers = JSON.parse(JSON.stringify($request.headers));
let body = $request.body;

if (wifiName) {
	if (wifiName.includes("shzlk")) {
		url = url.replace("https://feiyang.allinhub.top", "http://mac-mini.local:35455");
		url.Host = "mac-mini.local";
	} else if (wifiName.includes("H&B_Family")) {
		url = url.replace("https://feiyang.allinhub.top", "http://xueimac.local:35455");
		url.Host = "xueimac.local";
	} else {
		$done({});
	}
	$done({ url: url, headers: headers, body: body });
} else {
	$done({});
}
