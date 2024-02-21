let config = JSON.parse($files[0]);
let proxies = JSON.parse(await produceArtifact({
  type: 'subscription',
  name: 'AmyTelecom',
  platform: 'sing-box'
}));

let proxies1 = JSON.parse(await produceArtifact({
  type: 'subscription',
  name: 'PaopaoDog',
  platform: 'sing-box'
}));

let proxies2 = JSON.parse(await produceArtifact({
  type: 'subscription',
  name: 'FishChips',
  platform: 'sing-box'
}));

let additionalOutbound = JSON.parse(await produceArtifact({
  type: 'subscription',
  name: 'Vmess',
  platform: 'sing-box'
}));

function filterAndMap(data, regex) {
  return data.filter(obj => regex.test(obj.tag)).map(obj => obj.tag);
}

const regexes = {
  Other: /^(?!.*(香港|日本|新加坡|美国|台湾))/,
  HK: /香港/,
  JP: /日本/,
  US: /美国/,
  SG: /新加坡/,
  TW: /台湾/,
  AmyTelecom: /.*/,
  PaopaoDog: /.*/,
  FishChips: /.*/
};

let filtered = {};
Object.keys(regexes).forEach(key => {
  if (key === 'Other' || key === 'PaopaoDog') {
    filtered[key] = filterAndMap(proxies1, regexes[key]);
  } else if (key === 'FishChips') {
    filtered[key] = filterAndMap(proxies2, regexes[key]);
  } else {
    filtered[key] = filterAndMap(proxies, regexes[key]);
  }
});

function createOutbound(tag) {
  let type = tag === 'AmyTelecom' || tag === 'PaopaoDog' || tag === 'FishChips' || tag === 'Other' ? 'selector' : 'urltest';
  return filtered[tag].length > 0 ? { "outbounds": filtered[tag], "tag": tag, "type": type } : null;
}

const outservers = Object.keys(filtered).map(createOutbound).filter(outbound => outbound !== null);

proxies.forEach(proxy => {
  outservers.push(proxy);
});
proxies1.forEach(proxy => {
  outservers.push(proxy);
});
proxies2.forEach(proxy => {
  outservers.push(proxy);
});

function updateOutbound(tag, defaultTags) {
  let outbound = config.outbounds.find(o => o.tag === tag);
  if (outbound) {
    outbound.outbounds = defaultTags
      .filter(t => t === 'Direct' || t === 'Global' || (filtered[t] && filtered[t].length > 0));
  }
}

updateOutbound('Global', ["HK", "JP", "US", "SG", "TW", "Other", "Direct", "AmyTelecom", "PaopaoDog", "FishChips"]);
const globalOutbound = config.outbounds.find(o => o.tag === 'Global');
const proxyIndex = globalOutbound.outbounds.findIndex(out => out === 'Proxy');
if (proxyIndex !== -1) {
  globalOutbound.outbounds.splice(proxyIndex, 0, 'Vmess');
};
updateOutbound('Bing', ["Direct", "HK", "JP", "US", "SG", "TW", "Other", "Global"]);
updateOutbound('AI', ["US", "JP", "SG", "TW", "Global"]);
updateOutbound('Telegram', ["SG", "HK", "JP", "US", "TW", "Other", "Global"]);
updateOutbound('GitHub', ["US", "HK", "JP", "SG", "TW", "Other", "Global", "Direct"]);
updateOutbound('Crypto', ["HK", "JP", "US", "SG", "TW", "Other", "Global", "Direct"]);
updateOutbound('Oracle', ["Other", "HK", "JP", "US", "SG", "TW", "Global", "Direct"]);
updateOutbound('VPS', ["Direct", "HK", "JP", "US", "SG", "TW", "Other", "Global"]);
updateOutbound('Apple', ["Direct", "HK", "JP", "US", "SG", "TW", "Other", "Global"]);
updateOutbound('OneDrive', ["Direct", "Global"]);
updateOutbound('PikPak', ["Direct", "Global"]);
updateOutbound('Anytype', ["Direct", "Global"]);
updateOutbound('Speedtest', ["Direct", "HK", "JP", "US", "SG", "TW", "Other", "AmyTelecom", "PaopaoDog"]);
const speedtestOutbound = config.outbounds.find(o => o.tag === 'Speedtest');
const speedtestProxyIndex = speedtestOutbound.outbounds.findIndex(out => out === 'Proxy');
if (speedtestProxyIndex !== -1) {
  speedtestOutbound.outbounds.splice(speedtestProxyIndex, 0, 'Vmess');
};

config.outbounds = config.outbounds.concat(outservers.filter(outbound => outbound !== null));
config.outbounds = config.outbounds.concat(additionalOutbound);

$content = JSON.stringify(config, null, 2);
