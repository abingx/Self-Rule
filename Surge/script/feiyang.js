const wifiName = $network.wifi.ssid;
let url = $request.url;
let headers = JSON.parse(JSON.stringify($request.headers));
let body = $request.body;
let match = url.match(/^http:\/\/feiyang\.allinone\/(.*)$/);
if (!match) {
	$done({});
} else {
	let path = match[1];
	let newUrl;
	if (wifiName) {
		if (wifiName.includes("shzlk")) {
			newUrl = `http://Mac-mini.local:35455/${path}`;
		} else if (wifiName.includes("H&B_Family")) {
			newUrl = `http://xueiMac.local:35455/${path}`;
		} else {
			// 阻止访问，返回空的响应
			$done({});
		}
	} else {
		// 没有 Wi-Fi 名称时也阻止访问
		$done({});
	}
	// 返回修改后的 URL
	$done({ url: newUrl });
}