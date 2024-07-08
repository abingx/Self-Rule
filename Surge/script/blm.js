let obj = JSON.parse($response.body);
obj.user_infos.vip=true;
$done({body: JSON.stringify(obj)});
