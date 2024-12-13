const wifiName = $network.wifi.ssid;
let url = $request.url;
let headers = JSON.parse(JSON.stringify($request.headers));
let body = $request.body;
let path = url.match(/^http:\/\/feiyang\.allinone\/(.*)$/)[1];
let newUrl;
if (wifiName) {
	if (wifiName.includes("shzlk")) {
		newUrl = `http://mac-mini.local:35455/${path}`;
		headers.host = 'mac-mini.local';
	} else if (wifiName.includes("H&B_Family")) {
		newUrl = `http://xueimac.local:35455/${path}`;
		headers.host = 'xueimac.local';
	} else {
		newUrl = `https://feiyang.allinhub.top/${path}`;
		headers.host = 'feiyang.allinhub.top';
	}
} else {
	newUrl = `https://feiyang.allinhub.top/${path}`;
	headers.host = 'feiyang.allinhub.top';
}
$done({ url: newUrl, headers: headers });
