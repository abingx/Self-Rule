let obj = JSON.parse($response.body);
obj = {
  "products": [
    {
      "inTrial": false,
      "cancelled": true,
      "expiresDate": "2032-10-08T06:17:47Z",
      "subscriptionId": 193717,
      "purchaseDate": "2021-10-08T06:17:51Z",
      "vendor": "apple",
      "product": "DuetProAnnual"
    }
  ],
  "success": true,
  "hasStripeAccount": true
};
$done({body: JSON.stringify(obj)});

/*           
host = rdp.duetdisplay.com
^https:\/\/rdp\.duetdisplay\.com\/v1\/users\/validateReceipt url script-response-body https://raw.githubusercontent.com/abingx/Self-Rule/master/script/duet.js


https://rdp.duetdisplay.com/v1/users/validateReceipt

{
  "products": [
    {
      "inTrial": true,
      "cancelled": true,
      "expiresDate": "2021-10-15T06:17:47Z",
      "subscriptionId": 193717,
      "purchaseDate": "2021-10-08T06:17:51Z",
      "vendor": "apple",
      "product": "DuetAirAnnual"
    }
  ],
  "success": true,
  "hasStripeAccount": false
}

*/