var obj= {
  "data": {
    "results": {
      "locale": "zh_CN",
      "id": "0a70aff1-0e3e-4eb7-860d-872e8ed6ce3f",
      "created_at": "2022-06-08T00:46:37.194Z",
      "subscriptions": [
        {
          "id": "ec662469-e6c9-49e8-9d4c-cd4c9d200215",
          "unit": "year",
          "group_id": "237801a2",
          "autorenew_enabled": true,
          "expires_at": "2032-06-22T02:09:24.000Z",
          "in_retry_billing": false,
          "introductory_activated": true,
          "cancelled_at": null,
          "platform": "ios",
          "product_id": "com.wiheads.paste.macos.subscription.annual",
          "retries_count": 0,
          "started_at": "2022-06-08T02:09:25.000Z",
          "local": false,
          "next_check_at": "2032-06-22T02:16:24.000Z",
          "kind": "autorenewable",
          "units_count": 1,
          "environment": "production",
          "status": "trial"
        }
      ],
      "paywalls": [
        {
          "default": true,
          "variation_identifier": null,
          "variation_name": null,
          "id": "e8f6c54e",
          "items": [
            {
              "product_id": "com.wiheads.paste.macos.subscription.monthly",
              "id": "661199d9",
              "store": "app_store",
              "name": "Monthly Subscription"
            },
            {
              "product_id": "com.wiheads.paste.macos.subscription.annual",
              "id": "516a4f97",
              "store": "app_store",
              "name": "Annual Subscription"
            },
            {
              "product_id": "com.wiheads.paste.macos.subscription.annual.family",
              "id": "b2cd7cfe",
              "store": "app_store",
              "name": "Annual Family Subscription"
            }
          ],
          "from_paywall": null,
          "identifier": "default",
          "experiment_id": null,
          "experiment_name": null,
          "json": null,
          "name": "Default Paywall"
        }
      ],
      "user_id": "9B3D54C8-43F4-46CD-BBB8-086797670AE0",
      "currency": {
        "id": "a5604c08-9833-4d8b-a677-f31e7717d8e5",
        "country_code": "CN",
        "code": "CNY"
      },
      "devices": [
      ]
    },
    "meta": null
  },
  "errors": null
}


$done({body: JSON.stringify(obj)});

  
/*
https://api.apphud.com/v1/customers

{
  "data": {
    "results": {
      "locale": "zh_CN",
      "id": "0a70aff1-0e3e-4eb7-860d-872e8ed6ce3f",
      "created_at": "2022-06-08T00:46:37.194Z",
      "subscriptions": [
        {
          "id": "ec662469-e6c9-49e8-9d4c-cd4c9d200215",
          "unit": "year",
          "group_id": "237801a2",
          "autorenew_enabled": false,
          "expires_at": "2022-06-22T02:09:24.000Z",
          "in_retry_billing": false,
          "introductory_activated": true,
          "cancelled_at": null,
          "platform": "ios",
          "product_id": "com.wiheads.paste.macos.subscription.annual",
          "retries_count": 0,
          "started_at": "2022-06-08T02:09:25.000Z",
          "local": false,
          "next_check_at": "2022-06-22T02:16:24.000Z",
          "kind": "autorenewable",
          "units_count": 1,
          "environment": "production",
          "status": "trial"
        }
      ],
      "paywalls": [
        {
          "default": true,
          "variation_identifier": null,
          "variation_name": null,
          "id": "e8f6c54e",
          "items": [
            {
              "product_id": "com.wiheads.paste.macos.subscription.monthly",
              "id": "661199d9",
              "store": "app_store",
              "name": "Monthly Subscription"
            },
            {
              "product_id": "com.wiheads.paste.macos.subscription.annual",
              "id": "516a4f97",
              "store": "app_store",
              "name": "Annual Subscription"
            },
            {
              "product_id": "com.wiheads.paste.macos.subscription.annual.family",
              "id": "b2cd7cfe",
              "store": "app_store",
              "name": "Annual Family Subscription"
            }
          ],
          "from_paywall": null,
          "identifier": "default",
          "experiment_id": null,
          "experiment_name": null,
          "json": null,
          "name": "Default Paywall"
        }
      ],
      "user_id": "9B3D54C8-43F4-46CD-BBB8-086797670AE0",
      "currency": {
        "id": "a5604c08-9833-4d8b-a677-f31e7717d8e5",
        "country_code": "CN",
        "code": "CNY"
      },
      "devices": [
      ]
    },
    "meta": null
  },
  "errors": null
}
*/