/*
快捷指令中当前位置的定位用的地理坐标系和国内的不一样。自动化位置搜索框搜出来的地址是基于高德的 (GCJ02 坐标系），而快捷指令用来定位的坐标系是 WGS84。所以当在GCJO2坐标系看WGS84坐标系的点是偏移到了西北方向，在WGS84坐标系看GCJO2坐标系的点是偏移到了东南方向。那么要让这个自动化起作用，只要把选的点往西北方向偏移过去，这时候就要用坐标系转换工具，转换了之后把纬度，经度粘贴到搜索框就可以了。https://xream.notion.site/6fed380cf1d147c6a047bce452a8f2af#7fbbc4aa24124dc8b29d054b21b8ff59（此方法api失效）

地图坐标系转化中的gcj02towgs84，来源https://github.com/wandergis/coordTransform_py

注意传入和返回时lng和lat的顺序
*/

const lng = 104.140365;
const lat = 30.589884;

//IOS—Actions
//let str = $text;
//let [lng, lat] = str.split("\n").map(coord => parseFloat(coord));

const PI = 3.1415926535897932384626;
const X_PI = 3.14159265358979324 * 3000.0 / 180.0;
const A = 6378245.0;
const EE = 0.00669342162296594323;

function transformLat(lng, lat) {
    let ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * Math.sqrt(Math.abs(lng));
    ret += (20.0 * Math.sin(6.0 * lng * PI) + 20.0 * Math.sin(2.0 * lng * PI)) * 2.0 / 3.0;
    ret += (20.0 * Math.sin(lat * PI) + 40.0 * Math.sin(lat / 3.0 * PI)) * 2.0 / 3.0;
    ret += (160.0 * Math.sin(lat / 12.0 * PI) + 320 * Math.sin(lat * PI / 30.0)) * 2.0 / 3.0;
    return ret;
}
function transformLng(lng, lat) {
    let ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * Math.sqrt(Math.abs(lng));
    ret += (20.0 * Math.sin(6.0 * lng * PI) + 20.0 * Math.sin(2.0 * lng * PI)) * 2.0 / 3.0;
    ret += (20.0 * Math.sin(lng * PI) + 40.0 * Math.sin(lng / 3.0 * PI)) * 2.0 / 3.0;
    ret += (150.0 * Math.sin(lng / 12.0 * PI) + 300.0 * Math.sin(lng / 30.0 * PI)) * 2.0 / 3.0;
    return ret;
}
function gcj02ToWgs84(lng, lat) {
    const dLat = transformLat(lng - 105.0, lat - 35.0);
    const dLng = transformLng(lng - 105.0, lat - 35.0);
    const radLat = lat / 180.0 * PI;
    let magic = Math.sin(radLat);
    magic = 1 - EE * magic * magic;
    const sqrtMagic = Math.sqrt(magic);
    const mGlat = lat + (dLat * 180.0) / ((A * (1 - EE)) / (magic * sqrtMagic) * PI);
    const mGlng = lng + (dLng * 180.0) / (A / sqrtMagic * Math.cos(radLat) * PI);
    return [lng * 2 - mGlng, lat * 2 - mGlat];
}

const result = gcj02ToWgs84(lng, lat);
console.log(`${result[1]},${result[0]}`);
//IOS—Actions
//return `${result[1]},${result[0]}`;