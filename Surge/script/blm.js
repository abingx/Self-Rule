let obj = JSON.parse($response.body);
if (Array.isArray(obj.user_infos) && obj.user_infos.length > 0) {
  obj.user_infos[0].vip = true;
}
$done({body: JSON.stringify(obj)});
