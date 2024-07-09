/*
#!name=两步路会员
#!desc=非一次性解锁，先开启规则，在进入软件登录即可！如果没有解锁重新打开APP即可。

[Script]
lbl = type=http-response,pattern=^https\:\/\/helper\.2bulu\.com\/tokenLogin\?psign\=?,requires-body=1,script-path=https://raw.githubusercontent.com/abingx/Self-Rule/master/Surge/script/lbl.js

[MITM]
hostname = %APPEND% helper.2bulu.com
*/
let obj = JSON.parse($response.body);
//obj.UserInfoHttp.vipLevel = "MQ==";
//obj.vipExpireTime = "MTk5NDgwMzIwMA==";
$done({body: JSON.stringify(obj)});



/*
https://helper.2bulu.com/tokenLogin?psign=7e57fd46d07c3d69f74c5cbd39202a78

{
  "UserInfoHttp": {
    "weichatAccount": "o98-dtz39hszCwPTJtWnLQ71jJyo",
    "isConfirm": 0,
    "areaCode": "86",
    "hasPassword": 1,
    "albumPics": null,
    "tagCodes": null,
    "qqNickname": null,
    "vipLevel": "0lEDlMnKZy8=",
    "onOff": {
      "autoPositinFileByArticle": 1,
      "autoPositinFileByDynamic": 1,
      "aaOuting": 1,
      "autoDynamicByAlbum": 0,
      "autoDynamicByOuting": 1,
      "autoPositinFileByMark": 1,
      "event": 1,
      "serverEvent": 1,
      "autoDynamicByZTeam": 0,
      "autoDynamicByPai": 1,
      "commentArticle": 1,
      "focusAndFans": 1,
      "receiveMsgByZan": 1,
      "receiveMsgByFocus": 1,
      "outing": 1,
      "receiveMsgNotification": 1,
      "releaseAaOuting": 1
    },
    "autoDynamicByTrack": 1,
    "accountType": 0,
    "mofang_account": null,
    "weight": null,
    "is_real_name": 0,
    "userBg": 1031184,
    "emergencyContacts": null,
    "receiveMsgModule": null,
    "qqBlogNickname": null,
    "coin": 0,
    "mail": null,
    "amount": 0,
    "wxMiniAppHeadPicId": null,
    "realName": null,
    "stamina": 10,
    "fansType": 0,
    "openApiToken": null,
    "type": 0,
    "friendType": 0,
    "addConfirm": 0,
    "isCheck": 1,
    "openId": null,
    "facebookAccount": null,
    "userId": 56527663,
    "appleNickname": null,
    "nickName": "Sit",
    "qqAccount": null,
    "signature": null,
    "searchByPhone": 1,
    "limitLogin": false,
    "weichatNickname": null,
    "buryCrazyTreasures": 0,
    "isOpenSpace": 1,
    "wxMiniAppNickName": null,
    "achieveNum": 3,
    "qqBlogAccount": null,
    "height": null,
    "vipType": null,
    "email": null,
    "sinaBlogAccount": null,
    "sinaBlogNickname": null,
    "mailVerification": 0,
    "exp": 259,
    "isUseDailyPicture": 0,
    "serverVersion": 0,
    "beMaskMsg": 0,
    "birthday": 0,
    "emergencyContactsNew": null,
    "picId": 1302795745,
    "achieveTotalNum": 86,
    "haiLiaoAccount": null,
    "headWidgetPicId": null,
    "beMaskDymanic": 0,
    "backPicId": 1031184,
    "bloodType": null,
    "userName": "Sit____",
    "hasChangedUsername": 1,
    "phoneVerification": 2,
    "isOpenLocation": 1,
    "level": 2,
    "remarkName": null,
    "receiverMsgScope": 0,
    "appleAccount": null,
    "dynamicShowOnlyFriends": 0,
    "gender": 1,
    "phone": "17761239071",
    "addressId": null,
    "interest": null,
    "isOpenActivity": 1,
    "posInfo": {
      "userId": null,
      "speed": null,
      "time": 1720502187000,
      "posType": null,
      "latitude": null,
      "accuracy": null,
      "longtitude": null,
      "altitude": null,
      "gpsStatus": null
    },
    "mofang_nickname": null,
    "isReceiveMsg": null,
    "vipExpireTime": "Aly7pdOUyLD0VsMjQwrnNA==",
    "createTime": null,
    "userSettingInfo": {
      "authentication": {
        "status": -1,
        "score": 0,
        "qualityGuaranteeDepositFlag": 0,
        "satisfaction": 100,
        "serviceScore": 0,
        "level": 0,
        "stateExt": 0,
        "type": 1,
        "scheduleScore": 0,
        "appraiseNum": 0
      }
    },
    "loginStatus": 0
  },
  "userId": 56527663,
  "authCode": "dc882c95ebb64e8daf4cc55e2557668c",
  "errCode": "0"
}
*/