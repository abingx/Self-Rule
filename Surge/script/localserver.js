const wifiName = $network.wifi.ssid;
if (!wifiName) {
    console.log("不在Wi-Fi环境，无内网服务器.");
    $done({});
}
let url = $request.url;
let headers = { ...$request.headers };

console.log(wifiName);
console.log(url);

const hostConfig = {
    'shzlk': 'mac-mini.local',
    'H&B_Family': 'xueimac.local'
};
function getHost(wifiName) {
    for (const key in hostConfig) {
        if (wifiName.includes(key)) {
            return hostConfig[key];
        }
    }
    return null;
}
const lanHost = getHost(wifiName);
if (!lanHost) {
    console.log("不在有内网服务的Wi-Fi中");
    $done({});
}

const portConfig = {
    'feiyang.allinhub.top': 35455,
    'openlist.allinhub.top': 5244,
    'open-webui.allinhub.top': 3000
};
function getPort(url) {
    for (const domain in portConfig) {
        if (url.includes(domain)) { 
            return portConfig[domain];
        }
    }
    return null;
}
const lanPort = getPort(url);
if (!lanPort) {
    console.log("未找到对应的内网端口");
    $done({});
}

url = url.replace(/https:\/\/[^\/]+(:\d+)?/, `http://${lanHost}:${lanPort}`);
if (headers[':authority']) {
    headers[':authority'] = `${lanHost}:${lanPort}`;
}
['referer', 'Referer'].forEach(key => {
    if (headers[key]) {
        headers[key] = `http://${lanHost}:${lanPort}`;
    }
});

console.log(url);
$done({ url: url, headers: headers });
