let config = $files[0];
let proxies = await produceArtifact({
  type: 'subscription',
  name: 'Vmess',
  platform: 'QX'
});

let index = config.indexOf("[server_local]");

if (index !== -1) {
    config = config.slice(0, index + "[server_local]".length) + "\n" + proxies + "\n" + config.slice(index + "[server_local]".length);
} else {
    console.log("[server_local] not found in config");
}

$content = config;