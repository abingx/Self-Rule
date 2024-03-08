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

let additionalOutbound = JSON.parse(await produceArtifact({
  type: 'subscription',
  name: 'Vmess',
  platform: 'sing-box'
}));

function filterAndMap(data, regex) {
  return data.filter(obj => regex.test(obj.tag)).map(obj => obj.tag);
}

const regexes = {
  UN: /^(?!.*(香港|日本|新加坡|美国|台湾))/,
  HK: /香港/,
  JP: /日本/,
  US: /美国/,
  SG: /新加坡/,
  TW: /台湾/,
  AmyTelecom: /.*/,
  PaopaoDog: /.*/
};

let filtered = {};
Object.keys(regexes).forEach(key => {
  if (key === 'UN' || key === 'PaopaoDog') {
    filtered[key] = filterAndMap(proxies1, regexes[key]);
  } else {
    filtered[key] = filterAndMap(proxies, regexes[key]);
  }
});

function createOutbound(tag) {
  let type = tag === 'AmyTelecom' || tag === 'PaopaoDog' || tag === 'UN' ? 'selector' : 'urltest';
  return filtered[tag].length > 0 ? { "outbounds": filtered[tag], "tag": tag, "type": type } : null;
}

const outservers = Object.keys(filtered).map(createOutbound).filter(outbound => outbound !== null);

proxies.forEach(proxy => {
  outservers.push(proxy);
});
proxies1.forEach(proxy => {
  outservers.push(proxy);
});

function updateOutbound(tag, defaultTags) {
  let outbound = config.outbounds.find(o => o.tag === tag);
  if (outbound) {
    outbound.outbounds = defaultTags;
  }
}

updateOutbound('Global', ["HK", "JP", "US", "SG", "TW", "UN", "Direct", "Vmess", "AmyTelecom", "PaopaoDog"]);
updateOutbound('VPS', ["Direct", "Global", "HK", "JP", "US", "SG", "TW", "UN"]);
updateOutbound('AI', ["US", "JP", "SG", "TW"]);
updateOutbound('Telegram', ["Global", "HK", "JP", "US", "SG", "TW"]);
updateOutbound('GitHub', ["Global", "HK", "JP", "US", "SG", "TW", "Direct"]);
updateOutbound('Oracle', ["UN", "Global", "Direct"]);
updateOutbound('Speedtest', ["Direct", "HK", "JP", "US", "SG", "TW", "UN", "Vmess", "AmyTelecom", "PaopaoDog"]);
updateOutbound('Final', ["Direct", "Global", "Block"]);

config.outbounds = config.outbounds.concat(outservers.filter(outbound => outbound !== null));
config.outbounds = config.outbounds.concat(additionalOutbound);

$content = JSON.stringify(config, null, 2);
