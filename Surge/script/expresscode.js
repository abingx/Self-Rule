/*
[Script]
test = type=http-response,pattern=^https\:\/\/guide-acs\.m\.taobao\.com\/gw\/mtop\.cainiao\.lpc\.packageservice\.querypackagelist\.lightapp\.get.*,requires-body=1,max-size=0,script-path=expresscode.js

[MITM]
hostname = %APPEND% taobao.com
*/

let obj = JSON.parse($response.body);
let results = obj.data.result;
let selectedData = {};

results.forEach(jsonObj => {
    if (jsonObj.packageStation && jsonObj.packageStation.showAuthCode === "true") {
        let stationName = jsonObj.packageStation.stationName;
        if (selectedData[stationName]) {
            selectedData[stationName].push(jsonObj.packageStation.authCode);
        } else {
            selectedData[stationName] = [jsonObj.packageStation.authCode];
        }
    }
});

console.log(selectedData);
$done({});
