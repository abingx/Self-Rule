var obj = JSON.parse($response.body);
let a = obj.rs.utoken;
var obj = {
  "code" : "0",
  "rs" : {
    "serverLink" : "http://cloud.gstarcad.com/getServerLink.do",
    "serverUrl" : "http://user.gstarcad.com/login",
    "utoken" : "a7fe88e2-b4d2-4851-9b51-e9c3eb9db0f5",
    "third" : [
      {
        "openId" : "o7FOBxJg--LpI94-TVko8OFhQGpM",
        "favicon" : "http://thirdwx.qlogo.cn/mmopen/vi_32/xpzVGibPLxHospia3ckhDXYdbuH6SrHfmOSuRnIlOkwhqXSO01pGm0xN7NJb1IT358ibVElIwb7KoKgB0Za00WgjA/132",
        "sex" : "1",
        "name" : "薛",
        "type" : "weixin",
        "unionId" : "oKziUs7J6essD2uROYWmLkK6hrbc"
      },
      {
        "openId" : "3A52512AD2B1D1FEE949FAEE5A0AD1F8",
        "favicon" : "http://thirdqq.qlogo.cn/g?b=oidb&k=yDwXGFjPfE1Iw37wKX7IBw&s=100&t=1556716251",
        "sex" : "1",
        "name" : "薛",
        "type" : "qq",
        "unionId" : "UID_6C7BF5154B4A063C4F4503FD5295988C"
      },
      {
        "openId" : "1927821362",
        "favicon" : "https://tva2.sinaimg.cn/crop.0.0.180.180.50/72e83832jw1e8qgp5bmzyj2050050aa8.jpg?KID=imgbed,tva&Expires=1575368382&ssig=J6t5pz0dnv",
        "sex" : "1",
        "name" : "冰哥很蛋定",
        "type" : "weibo",
        "unionId" : ""
      },
      {
        "type" : "apple"
      }
    ],
    "vipInfo" : {
      "serverEndTimeStamp" : 1954815132000,
      "amount" : 0,
      "appTryStatus" : true,
      "serverEndTime" : "2012-12-12 12:12:12",
      "goodId" : 73,
      "canBuy" : false,
      "canUpgrade" : false,
      "goodsCodes" : "ML2",
      "descs" : "免费领取高级账户1小时试用,不包含免广告和云图扩容",
      "serverStartTime" : "2021-02-01 21:09:58",
      "serverStartTimeStamp" : 1612184998000,
      "name" : "高级账户（试用）"
    },
    "active" : {
      "app_try_give_id" : 9,
      "app_try_get_show" : true,
      "app_try_give_show" : false,
      "app_try_give_usable" : false,
      "app_try_get_id" : 2,
      "app_try_get_overdue" : true,
      "app_try_get_guide" : false,
      "app_try_get_info" : {
        "try_request_date" : 1612188533097,
        "try_end_date" : 1954815132000,
        "try_start_date" : 1612184998000
      },
      "app_try_get_usable" : false
    },
    "recentlyExpired" : [

    ],
    "myAmountNumbers" : "2个群组，每个群组限5人",
    "advertisingUrl" : "http://web.gstarcad.com/upgrade?uid=4321770&utoken=a7fe88e2-b4d2-4851-9b51-e9c3eb9db0f5",
    "serverCode" : "CN",
    "storage" : {
      "free" : 100,
      "surplus" : 100,
      "total" : 100,
      "used" : 0
    },
    "vipList" : [

    ],
    "userInfo" : {
      "id" : 4321770,
      "score" : 6,
      "updateTime" : "2019-12-15 15:41:03",
      "registerDate" : "2019-12-03 15:18:51",
      "mobile" : "17761239071",
      "sex" : 1,
      "level" : 1,
      "nickName" : "allin_schroe",
      "favicon" : "http://thirdwx.qlogo.cn/mmopen/vi_32/xpzVGibPLxHospia3ckhDXYdbuH6SrHfmOSuRnIlOkwhqXSO01pGm0xN7NJb1IT358ibVElIwb7KoKgB0Za00WgjA/132",
      "lastLoginTime" : "2021-02-01 22:07:53",
      "email" : "allin_schroe@hotmail.com",
      "isActivate" : 1,
      "name" : "allin_schroe"
    },
    "chat" : {
      "userSig" : "eJw9js0KgkAURt9l1iF3-h2hTRsFFYkyrF00k1yiaTAxIXr3RKPldz4OnDfZF7vIjQE7RxIFIgZYzWxwHUkIi4As*2lv5xDQkoQKAK61MXR50Drf4xVnQXBGtf5L2E6sMwOUwyY3WVOVJ9**LoVs0pHlWeW3vlbayPRxtOJQi-VP7PE*9VBFGY1jyfnnC9l1L74_",
      "ordinary" : {
        "joinGroupNumberLimit" : 500,
        "createGroupNumberLimit" : 3,
        "createGroupUserNumberLimit" : 200
      },
      "senior" : {
        "joinGroupNumberLimit" : 500,
        "createGroupNumberLimit" : 20,
        "createGroupUserNumberLimit" : 200
      }
    }
  },
  "status" : true,
  "msg" : ""
};
let obj.rs.utoken = a;


$done({ body: JSON.stringify(obj) });


