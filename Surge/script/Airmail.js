var obj= {
  "request_date_ms" : 1604500076746,
  "request_date" : "2020-11-04T14:27:56Z",
  "subscriber" : {
    "non_subscriptions" : {

    },
    "first_seen" : "2020-11-04T14:19:19Z",
    "original_application_version" : "624",
    "other_purchases" : {

    },
    "management_url" : "itms-apps://apps.apple.com/account/subscriptions",
    "subscriptions" : {
      "Airmail_iOS_Monthly" : {
        "is_sandbox" : false,
        "period_type" : "trial",
        "billing_issues_detected_at" : null,
        "unsubscribe_detected_at" : null,
        "expires_date" : "2029-11-07T14:27:47Z",
        "grace_period_expires_date" : null,
        "original_purchase_date" : "2020-11-04T14:27:48Z",
        "purchase_date" : "2020-11-04T14:27:47Z",
        "store" : "app_store"
      }
    },
    "entitlements" : {
      "Airmail Premium" : {
        "grace_period_expires_date" : null,
        "purchase_date" : "2020-11-04T14:27:47Z",
        "product_identifier" : "Airmail_iOS_Monthly",
        "expires_date" : "2029-11-07T14:27:47Z"
      }
    },
    "original_purchase_date" : "2020-10-23T14:01:59Z",
    "original_app_user_id" : "FC90DB6C-54FF-4B1D-B96E-376471A7CC2E",
    "last_seen" : "2020-11-04T14:19:19Z"
  }
}


$done({body: JSON.stringify(obj)});

  
