# Clash for Windows配置文件预处理

按个人需求，将Clash for Windows（CFW）下载的配置文件进行预处理，实现个性化需求，处理包括：

1. 替换所有`proxy-groups`，变更为

    `Proxy`，类型`Select`，包含所有`proxies`
    
    `Global`，类型`Select`，嵌套`"HK","US","SG","JP","TW","DIRECT","Proxy"`
    
    `ChatGPT`，类型`Select`，嵌套`"US","SG","JP","TW"`
    
    `Bing`，类型`Select`，嵌套`"US","HK","SG","JP","TW","DIRECT"`
    
    `Apple`，类型`Select`，嵌套`"DIRECT","Global","HK","US","SG","JP","TW"`
    
    `OneDrive`，类型`Select`，嵌套`"DIRECT","Global","HK","US","SG","JP","TW"`
    
    `Speedtest`，类型`Select`，嵌套`"DIRECT","Proxy"`
    
    `Final`，类型`Select`，嵌套`"DIRECT","Global","HK","US","SG","JP","TW"`
    
    `HK`，类型`url-test`，名称中包含`香港`或`HongKong`的所有`proxies`
    
    `US`，类型`url-test`，名称中包含`美国`或`United States`的所有`proxies`
    
    `SG`，类型`url-test`，名称中包含`新加坡`或`Singapore`的所有`proxies`
    
    `JP`，类型`url-test`，名称中包含`日本`或`Japan`的所有`proxies`
    
    `TW`，类型`url-test`，名称中包含`台湾`或`Taiwan`的所有`proxies`

2. 新增`rule-providers`，包含`ChatGPT`、` Bing`、`Apple`、`OneDrive`、`Speedtest`、`Global`、`Global_Domain`、`China`、`ChinaIP`、`Lan`，规则全部来源于[blackmatrix7/ios_rule_script仓库](https://github.com/blackmatrix7/ios_rule_script)，保存于CFW配置文件夹目录下`/ruleset/`目录

3. 新增`rules`，配合`rule-providers`使用

```yaml
DOMAIN-SUFFIX,msftconnecttest.com,Global
DOMAIN-SUFFIX,msftncsi.com,Global
RULE-SET,Lan,DIRECT
RULE-SET,ChatGPT,ChatGPT
RULE-SET,Bing,Bing
RULE-SET,Apple,Apple
RULE-SET,Speedtest,Speedtest
RULE-SET,OneDrive,OneDrive
RULE-SET,Global,Global
RULE-SET,Global_Domain,Global
RULE-SET,China,DIRECT
RULE-SET,ChinaIP,DIRECT
GEOIP,CN,DIRECT
MATCH,Final
```

4. 食用方法：`CFW—设置—Profiles—Parsers`，填入

```yaml
parsers:
    - reg: https://.*
      remote:
        url: https://raw.githubusercontent.com/abingx/Self-Rule/master/Clash/parsers.js
        cache: true # 默认为false，指示是否对重复下载此预处理代码使用缓存
```

5. 预处理能够涵盖大部分机场配置，特殊情况可自行修改，`CFW—设置—Profiles—Parsers`支持直接填写代码
```yaml
parsers:
    - reg: https://.*
      code: |
        module.exports.parse = async (raw, { axios, yaml, notify, console }, { name, url, interval, selected }) => {
            const obj = yaml.parse(raw);
            
            #自己的JS，机场的配置文件在obj中
            
            return yaml.stringify(obj);
        } 
   ```
 6. 更多用法请参考[Clash for Windows文档](https://docs.cfw.lbyczf.com)