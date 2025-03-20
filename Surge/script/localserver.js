const wifiName = $network.wifi.ssid;
if (!wifiName) {
    console.log("不在Wi-Fi环境，无内网服务器.");
    $done({});
}
let url = $request.url;
let headers = { ...$request.headers };

console.log(wifiName);
console.log(url);

function getHost(wifiName) {
    if (wifiName.includes("shzlk")) {
        return 'mac-mini.local';
    } else if (wifiName.includes("H&B_Family")) {
        return 'xueimac.local';
    } else {
        return null;
    }
}
const lanHost = getHost(wifiName);
if (!lanHost) {
    console.log("不在有内网服务的Wi-Fi中");
    $done({});
}

function getPort(url) {
    if (url.includes("feiyang.allinhub.top")) {
        return 35455;
    } else if (url.includes("alist.allinhub.top")) {
        return 5244;
    } else if (url.includes("open-webui.allinhub.top")) {
        return 3000;
    } else {
        return null;
    }
}
const lanPort = getPort(url);
if (!lanPort) {
    console.log("未找到对应的内网端口");
    $done({});
}

url = url.replace(/https:\/\/[^\/]+(:\d+)?/, `http://${lanHost}:${lanPort}`);
if (headers[':authority']) {
    headers[':authority'] = lanHost;
}
if (headers.referer) {
    headers.referer = lanHost;
}

console.log(url);

$done({ url: url, headers: headers });
