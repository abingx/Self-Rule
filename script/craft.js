var obj = JSON.parse($response.body);
let obj.subscription.expirationDate = 1890725831000;

$done({ body: JSON.stringify(obj) });