let obj = JSON.parse($response.body);
obj.subscription.expirationDate = 1890725831000;
obj.subscription.tier = "Pro";
obj.subscription.subscriptionActive = true;
obj.isBetaUser = false;

$done({body: JSON.stringify(obj)});