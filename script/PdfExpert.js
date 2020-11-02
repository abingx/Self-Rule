var obj= {
  "productId" : "com.readdle.PDFExpert5.subscription.year50_pe6",
  "receiptStatus" : "ok",
  "subscriptionExpirationDate" : "14:12 09/11/2029",
  "isPDFExpert6User" : true,
  "inAppStates" : [
    {
      "receiptStatus" : "ok",
      "productId" : "com.readdle.PDFExpert5.subscription.year50_pe6",
      "isInGracePeriod" : false,
      "subscriptionAutoRenewStatus" : "autoRenewOff",
      "originalTransactionId" : "70000885799916",
      "isEligibleForIntroPeriod" : false,
      "subscriptionExpirationDate" : "14:12 09/11/2029",
      "type" : "subscription",
      "subscriptionState" : "trial",
      "productName" : "subscription"
    },
    {
      "type" : "custom purchase",
      "entitlements" : [
        "ios.pe6.basic-features"
      ],
      "productId" : "pdfexpert6-user"
    }
  ],
  "isEligibleForIntroPeriod" : false,
  "originalTransactionId" : "70000885799916",
  "bundleId" : "com.readdle.PDFExpert5",
  "type" : "subscription",
  "inAppPurchased" : [
    "com.readdle.PDFExpert5.subscription.year50_pe6"
  ],
  "receiptId" : 1447477507000,
  "chargingPlatform" : "iOS AppStore",
  "subscriptionState" : "trial",
  "subscriptionAutoRenewStatus" : "autoRenewOff",
  "isInGracePeriod" : false
};

$done({body: JSON.stringify(obj)});
