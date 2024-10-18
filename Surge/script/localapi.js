if ($network && $network.wifi.ssid && $network.wifi.ssid.includes("shzlk")) {
    let url = $request.url;
    let headers = JSON.parse(JSON.stringify($request.headers));
    let body = $request.body;
    if (url.includes("https://qwen.allinhub.top")) {
        url = url.replace("https://qwen.allinhub.top", "http://xueiMac.local:8000");
    } else if (url.includes("https://metaso.allinhub.top")) {
        url = url.replace("https://metaso.allinhub.top", "http://xueiMac.local:8001");
    } else if (url.includes("https://kimi.allinhub.top")) {
        url = url.replace("https://kimi.allinhub.top", "http://xueiMac.local:8002");
    } else {
        $done({});
    }
    if (headers['authorization']) {
        headers['Authorization'] = headers['authorization'];
        delete headers['authorization'];
    }
    delete headers['host'];
    delete headers['Host'];
    $done({url: url, headers: headers, body: body});
} else {
    $done({});
}