module.exports.parse = async (raw, { axios, yaml, notify, console }, { name, url, interval, selected }) => {
    const obj = yaml.parse(raw);
    obj["allow-lan"] = false;
    obj.secret = "hyperapp";
    const proxyNames = obj['proxies'].map(proxy => proxy.name);
    const filteredHK = proxyNames.filter(proxyName => {
        const regex = /(?!.*(\*)).*(香港)/;
        return regex.test(proxyName);
    });
    const filteredUS = proxyNames.filter(proxyName => {
        const regex = /(?!.*(\*)).*(美国)/;
        return regex.test(proxyName);
    });
    const filteredJP = proxyNames.filter(proxyName => {
        const regex = /(?!.*(\*)).*(日本)/;
        return regex.test(proxyName);
    });
    const filteredSG = proxyNames.filter(proxyName => {
        const regex = /(?!.*(\*)).*(新加坡)/;
        return regex.test(proxyName);
    });
    const filteredTW = proxyNames.filter(proxyName => {
        const regex = /(?!.*(\*)).*(台湾)/;
        return regex.test(proxyName);
    });                  
    const filteredOther = proxyNames.filter(proxyName => {
        const regex = /^(?!.*(香港|日本|新加坡|美国|台湾|\*))/;
        return regex.test(proxyName); 
    });
    const filteredMultiple = proxyNames.filter(proxyName => {
        const regex = /\*/;
        return regex.test(proxyName); 
    }); 
    obj["proxy-groups"] = [
        {
            name: "Proxy",
            type: "select",
            proxies: proxyNames
        },
        {
            name: "Global",
            type: "select",
            proxies: [
                "HK",
                "JP",
                "US",
                "SG",
                "TW",
                "Other",
                "Multiple",
                "DIRECT",
                "Proxy"
            ]
        },
        {
            name: "ChatGPT",
            type: "select",
            proxies: [
                "US",
                "JP",
                "SG",
                "TW"
            ]
        },
        {
            name: "Bing",
            type: "select",
            proxies: [
                "US",
                "HK",
                "JP",
                "SG",
                "TW",
                "DIRECT"
            ]
        },
        {
            name: "VPS",
            type: "select",
            proxies: [
                "DIRECT",
                "Global",
                "HK",
                "JP",
                "US",
                "SG",
                "TW"
            ]
        },
        {
            name: "Apple",
            type: "select",
            proxies: [
                "DIRECT",
                "Global",
                "HK",
                "JP",
                "US",
                "SG",
                "TW"
            ]
        },
        {
            name: "OneDrive",
            type: "select",
            proxies: [
                "DIRECT",                
                "Global",
                "HK",
                "JP",
                "US",
                "SG",
                "TW"
            ]
        },
        {
            name: "Speedtest",
            type: "select",
            proxies: [
                "DIRECT",
                "HK",
                "JP",
                "US",
                "SG",
                "TW",
                "Other",
                "Multiple",
                "Proxy"
            ]
        },
        {
            name: "Final",
            type: "select",
            proxies: [
                "Global",
                "DIRECT",
                "HK",
                "JP",
                "US",
                "SG",
                "TW"
            ]
        },
        {
            name: "HK",
            type: "url-test",
            proxies: filteredHK,
            url: "http://www.gstatic.com/generate_204",
            interval: "600"
        }, 
        {
            name: "US",
            type: "url-test",
            proxies: filteredUS,
            url: "http://www.gstatic.com/generate_204",
            interval: "600"
        }, 
        {
            name: "SG",
            type: "url-test",
            proxies: filteredSG,
            url: "http://www.gstatic.com/generate_204",
            interval: "600"
        }, 
        {
            name: "JP",
            type: "url-test",
            proxies: filteredJP,
            url: "http://www.gstatic.com/generate_204",
            interval: "600"
        }, 
        {
            name: "TW",
            type: "url-test",
            proxies: filteredTW,
            url: "http://www.gstatic.com/generate_204",
            interval: "600"
        },
        {
            name: "Other",
            type: "select",
            proxies: filteredOther
        },
        {
            name: "Multiple",
            type: "select",
            proxies: filteredMultiple
        }        
    ];
    obj["rule-providers"] = {
        Direct_Fix: {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Direct/Direct.yaml",
            interval: 604800,
            path: "./ruleset/Direct_Fix.yaml"
        },
        Download: {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Download/Download.yaml",
            interval: 604800,
            path: "./ruleset/Download.yaml"
        },
        ChatGPT: {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/OpenAI/OpenAI.yaml",
            interval: 604800,
            path: "./ruleset/ChatGPT.yaml"
        },
        Bing: {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Bing/Bing.yaml",
            interval: 604800,
            path: "./ruleset/Bing.yaml"
        },
        Apple: {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Apple/Apple.yaml",
            interval: 604800,
            path: "./ruleset/Apple.yaml"
        },
        Apple_Domain: {
            behavior: "domain",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Apple/Apple_Domain.yaml",
            interval: 604800,
            path: "./ruleset/Apple_Domain.yaml"
        },
        OneDrive: {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/OneDrive/OneDrive.yaml",
            interval: 604800,
            path: "./ruleset/OneDrive.yaml"
        },
        Speedtest: {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Speedtest/Speedtest.yaml",
            interval: 604800,
            path: "./ruleset/Speedtest.yaml"
        },
        Global: {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Global/Global.yaml",
            interval: 604800,
            path: "./ruleset/Global.yaml"
        },
        Global_Domain: {
            behavior: "domain",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Global/Global_Domain.yaml",
            interval: 604800,
            path: "./ruleset/Global_Domain.yaml"
        },
        Anti_IP : {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/lwd-temp/anti-ip-attribution/main/generated/rule-provider.yaml",
            interval: 604800,
            path: "./ruleset/Anti_IP.yaml"
        },
        ChinaMax : {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/ChinaMax/ChinaMax.yaml",
            interval: 604800,
            path: "./ruleset/ChinaMax.yaml"
        },
        ChinaMax_Domain: {
            behavior: "domain",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/ChinaMax/ChinaMax_Domain.yaml",
            interval: 604800,
            path: "./ruleset/ChinaMax_Domain.yaml"
        },
        Lan: {
            behavior: "classical",
            type: "http",
            url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Lan/Lan.yaml",
            interval: 604800,
            path: "./ruleset/Lan.yaml"
        }
    };
    obj.rules = [
        "DOMAIN-SUFFIX,poe.com,Global",
        "DOMAIN,bard.google.com,US",
        "DOMAIN,www.yppan.com,DIRECT",
        "DOMAIN-SUFFIX,splashtop.com,DIRECT",
        "DOMAIN-SUFFIX,allinhub.top,Global",
        "IP-CIDR,132.145.93.220/32,VPS,no-resolve",
        "IP-CIDR,146.56.161.117/32,VPS,no-resolve",
        "RULE-SET,Direct_Fix,DIRECT",
        "RULE-SET,Lan,DIRECT",
        "RULE-SET,Download,DIRECT",
        "RULE-SET,ChatGPT,ChatGPT",
        "RULE-SET,Bing,Bing",
        "RULE-SET,Apple,Apple",
        "RULE-SET,Apple_Domain,Apple",
        "RULE-SET,Speedtest,Speedtest",
        "RULE-SET,OneDrive,OneDrive",
        "RULE-SET,Global,Global",
        "RULE-SET,Global_Domain,Global",
        "RULE-SET,Anti_IP,DIRECT",
        "RULE-SET,ChinaMax,DIRECT",
        "RULE-SET,ChinaMax_Domain,DIRECT",
        "GEOIP,CN,DIRECT",
        "MATCH,Final"
    ];
    return yaml.stringify(obj);
}