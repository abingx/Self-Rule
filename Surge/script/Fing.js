var obj = JSON.parse($response.body);
obj = {
    "latest_receipt_info":[
        {
            "transaction_id":"70001110227747",
            "in_app_ownership_type":"PURCHASED",
            "quantity":"1",
            "original_transaction_id":"70001110227747",
            "subscription_group_identifier":"20707789",
            "purchase_date_pst":"2021-08-30 08:13:39 America/Los_Angeles",
            "original_purchase_date_ms":"1630336420000",
            "is_in_intro_offer_period":"false",
            "expires_date":"2031-09-06 23:13:39 Etc/GMT",
            "original_purchase_date_pst":"2021-08-30 08:13:40 America/Los_Angeles",
            "is_trial_period":"true",
            "expires_date_pst":"2031-09-06 23:13:39 America/Los_Angeles",
            "original_purchase_date":"2021-08-30 15:13:40 Etc/GMT",
            "expires_date_ms":"1946474019000",
            "purchase_date_ms":"1630336419000",
            "product_id":"PREMIUM_1MO",
            "purchase_date":"2021-08-30 15:13:39 Etc/GMT",
            "web_order_line_item_id":"70000467396764"
        }],
    "environment":"Production",
    "latest_receipt":"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",
    "pending_renewal_info":[
        {
            "auto_renew_product_id":"PREMIUM_1MO",
            "original_transaction_id":"70001110227747",
            "product_id":"PREMIUM_1MO",
            "auto_renew_status":"1"
        }],
    "receipt":
        {
            "in_app":[
                {
                "transaction_id":"70001110227747",
                "in_app_ownership_type":"PURCHASED",
                "quantity":"1",
                "original_transaction_id":"70001110227747",
                "purchase_date_pst":"2021-08-30 08:13:39 America/Los_Angeles",
                "original_purchase_date_ms":"1630336420000",
                "is_in_intro_offer_period":"false",
                "expires_date":"2031-09-06 23:13:39 Etc/GMT",
                "original_purchase_date_pst":"2021-08-30 08:13:40 America/Los_Angeles",
                "is_trial_period":"true",
                "expires_date_pst":"2031-09-06 23:13:39 America/Los_Angeles",
                "original_purchase_date":"2021-08-30 15:13:40 Etc/GMT",
                "expires_date_ms":"1946474019000",
                "purchase_date_ms":"1630336419000",
                "product_id":"PREMIUM_1MO",
                "purchase_date":"2021-08-30 15:13:39 Etc/GMT",
                "web_order_line_item_id":"70000467396764"
                }],
            "adam_id":430921107,
            "receipt_creation_date":"2021-08-30 15:13:41 Etc/GMT",
            "original_application_version":"8221",
            "app_item_id":430921107,
            "original_purchase_date_ms":"1558957474000",
            "request_date_ms":"1630336425302",
            "original_purchase_date_pst":"2019-05-27 04:44:34 America/Los_Angeles",
            "original_purchase_date":"2019-05-27 11:44:34 Etc/GMT",
            "receipt_creation_date_pst":"2021-08-30 08:13:41 America/Los_Angeles",
            "receipt_type":"Production",
            "bundle_id":"overlook.fing",
            "receipt_creation_date_ms":"1630336421000",
            "request_date":"2021-08-30 15:13:45 Etc/GMT",
            "version_external_identifier":843129476,
            "request_date_pst":"2021-08-30 08:13:45 America/Los_Angeles",
            "download_id":27056819083906,
            "application_version":"110402000"
        },
    "status":0
};
$done({body: JSON.stringify(obj)});
