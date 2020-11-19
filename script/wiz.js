var obj = JSON.parse($response.body);
let obj.result.vipDate = 1890725831000;
let obj.result.vip = true;

$done({ body: JSON.stringify(obj) });