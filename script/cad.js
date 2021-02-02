var obj = JSON.parse($response.body);
//var a = obj.rs.utoken;
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


//let obj.rs.utoken = a;


$done({body: JSON.stringify(obj)});


