var obj = JSON.parse($response.body);
var a = obj.rs.utoken;
obj.rs.vipInfo = {
  "serverEndTimeStamp" : 1954815132000,
  "amount" : 0,
  "appTryStatus" : true,
  "serverEndTime" : "2031-12-12 12:12:12",
  "goodId" : 73,
  "canBuy" : false,
  "canUpgrade" : false,
  "goodsCodes" : "ML2",
  "descs" : "免费领取高级账户1小时试用,不包含免广告和云图扩容",
  "serverStartTime" : "2021-02-01 21:09:58",
  "serverStartTimeStamp" : 1612184998000,
  "name" : "高级账户"
};
obj.rs.active = {
  "app_try_give_id" : 9,
  "app_try_get_show" : true,
  "app_try_give_show" : false,
  "app_try_give_usable" : true,
  "app_try_get_id" : 2,
  "app_try_get_overdue" : true,
  "app_try_get_guide" : true,
  "app_try_get_info" : {
    "try_request_date" : 1612185018648,
    "try_end_date" : 1954815132000,
    "try_start_date" : 1612184998000
  },
  "app_try_get_usable" : true
};
let obj.rs.utoken = a;


$done({body: JSON.stringify(obj)});


