var obj = JSON.parse($response.body);
let obj.rs.vipInfo.serverEndTimeStamp = 1954815132000;
let obj.rs.vipInfo.serverEndTime = "2031-12-12 12:12:12";
let obj.rs.active.app_try_get_info.try_end_date = 1954815132000;

$done({ body: JSON.stringify(obj) });