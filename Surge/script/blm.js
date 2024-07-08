let obj = JSON.parse($response.body);
obj.user_infos[0].vip = true;
$done({body: JSON.stringify(obj)});

/*
https://pebblefan.com/papi/get_users?user_seq_number=30658976

{
  "last_bians": [
    {
      "user_id": "30658976",
      "today_bian_count": 1,
      "last_bian": {
        "fuzhang": "fz0",
        "bianColor": "black_brown",
        "place": "place_company",
        "sticky": "sticky_yes",
        "province": "",
        "today_bian_count": 1,
        "country": "",
        "street": "",
        "deleted": false,
        "todayFeelStr": "好开心",
        "latitude": 0,
        "city": "",
        "endTime": 1720414680,
        "twoBianDuration": 0,
        "formattedAddress": "",
        "bianFeel": "easy",
        "streetNumber": "",
        "failBian": false,
        "bianSmell": "smell3",
        "bianWeight": "normal",
        "bianStyle": "muddy",
        "todayFeel": "happy",
        "longitude": 0,
        "recordDevice": "mobile",
        "noteText": "",
        "recordID": "8984AAAF-4C8D-4ACA-B680-72CB4B9A4FEC",
        "hasGeo": false,
        "durationTime": 60,
        "blood": "blood_no",
        "startTime": 1720414620
      }
    }
  ],
  "user_infos": [
    {
      "status": "ok",
      "nickname": "薛",
      "seq_number": "30658976",
      "notify_list": [
      ],
      "friend_date": 0,
      "headimgurl": "https:\/\/thirdwx.qlogo.cn\/mmopen\/vi_32\/PiajxSqBRaEISe1ibdbrPzh1M68YibBvffncVr95QmRFaYZjDiaQichQFSAibhEukibanCBfsFpTy30iabvpXMnz4cq6GTqpIUIGXmibw5GUEgKnkGwFV9UWTurk2hg\/132",
      "vip": false,
      "friend_can_see": false,
      "sex": 0
    }
  ]
}
*/
