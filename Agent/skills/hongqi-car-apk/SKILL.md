---
name: hongqi-car-apk
description: 一汽红旗 H5 车机第三方 APK 适配一站式技能。含三项能力：①用实测放行的白名单包名（com.android.gallery3d / com.android.htmlviewer / com.android.statementservice）绕过车机安装拦截；②向二进制 AndroidManifest.xml 注入车机桌面注册 meta-data（Group / Domain / Ability / MoreApp）让应用出现在原厂桌面；③用 AOSP 官方 testkey 重新签名以匹配车机白名单的签名校验。当用户提到"红旗车机装不上 apk""车机提示无法安装 / 解析包错误 / 签名冲突""装上了但桌面没有图标""改包名""applicationId""做共存版""重签名 apk""让应用出现在车机桌面"时使用。方法同样适用于其他采用"包名白名单 + 桌面分组注册"的定制 Android 车机。
agent_created: true
---

# 红旗车机第三方 APK 适配

一汽红旗 H5 车机的实证结论与可直接复用的工具链。
本技能同时覆盖三件事：**能装**（白名单包名）、**能跑**（只改身份不重编译）、
**桌面有图标**（桌面注册 meta-data），外加贯穿始终的 **AOSP testkey 重签名**。

## 三个关卡互相独立

任何一关失败的表现都不同，排查时不要混为一谈：

| 关卡 | 失败表现 | 根因 | 对策 |
|---|---|---|---|
| 能装 | `INSTALL_FAILED_*`、解析包错误、签名冲突 | 包名不在白名单 / 签名不匹配 / minSdk 过高 | 用真实白名单包名 + testkey 签名 |
| 能跑 | 装上后闪退 | 代码包名与 manifest 失配、dex 被改坏 | 只改身份标识，绝不 apktool b 重编译 |
| 有图标 | 装得上、能启动，桌面找不到 | 缺 `<application>` 下的桌面注册 meta-data | 注入 4 项 meta-data + 重启车机 |

## 第一关：能装 —— 必须用真实放行的白名单包名

红旗车机魔改了 PackageManager，维护一份**包名白名单**，非名单包名直接拒绝安装。

### 实测放行的三个包名

| 包名 | 车机占用情况 | 选用建议 |
|---|---|---|
| `com.android.gallery3d` | 一般为空（图库在车机精简系统中未预装） | **首选** |
| `com.android.htmlviewer` | 一般为空 | 次选，可与首选交替做对照测试 |
| `com.android.statementservice` | 可能已被其他应用占用 | 避开，装了会覆盖已有应用 |

三者都是 AOSP 系统应用包名。车机是精简版 Android，这些应用通常并未实际预装，
包名"空着"正好可用。

### 三条硬规则

1. **不要编造包名。** 白名单是精确匹配，编出来的名字一样被拒。
   必须从"已经能在该车机上安装成功"的样本里取。取证方法见
   `references/whitelist-packages.md`。
2. **一个包名只能存在一个应用。** 要让两个应用共存，必须各占一个不同的包名。
   分配新包名前先确认没被占用，否则会把已有应用**覆盖**掉。
3. **签名要与样本一致**（见下文 testkey 一节），否则同名包会报签名冲突。

## 第二关：能跑 —— 只改身份，绝不重编译

**只改 `AndroidManifest.xml` 的 `package` 属性 + `resources.arsc` 的
`ResTable_package.name` 字段，不要重编译 dex / 资源。**

反例（常见错误做法）：用 apktool 全量 decode + `renameManifestPackage` 重建。
对 Compose / 多 dex / 带 .so 的应用很容易炸；且当**代码包名 ≠ manifest 包名**时
会把 smali 目录也一起改名，直接改坏。

改前必查：
```bash
grep -r "原包名" 解包目录 --include=*.smali
```
若不存在同名目录（如 manifest 包名 `com.example.player` 而代码全在
`com.example.core`），则改 manifest 包名对代码零影响。

**只替换"恰好等于原包名"的那一个字符串条目。** 清单里 `原包名.xxx`
（自定义权限名、ContentProvider authority、服务 action）必须保持原样——
这些常量同时硬编码在 dex 常量池里，单方面改清单会造成失配。

`resources.arsc` 必须同步，否则 apktool 解码会报
`Renamed manifest package found!`。好消息：`ResTable_package.name` 是
**固定 256 字节**字段，可原地无损改写，零结构风险。

## 第三关：有图标 —— 注入桌面注册 meta-data

红旗原厂 Launcher **不按标准 LAUNCHER 意图扫描桌面**，而是读应用
`<application>` 下的一组约定 `meta-data` 来构建入口。缺这组声明 →
装得上、能跑，但桌面不给图标（只能从系统管理后台启动）。

在 `</application>` 之前插入这 4 条：

```xml
<meta-data android:name="Group"    android:value="GROUP CARPLAY"/>
<meta-data android:name="Domain"   android:value="DOMAIN CARPLAY"/>
<meta-data android:name="Ability"  android:value="<目标应用自己的 MAIN/LAUNCHER Activity>"/>
<meta-data android:name="MoreApp"  android:value="true"/>
```

- `Group` / `Domain`：桌面分组标签，**照抄能显示的样本取值**。
- `Ability`：改成**目标应用自己的** MAIN/LAUNCHER Activity 全类名。
  工具支持 `--meta "Ability=@auto"` 自动探测填充，并保持声明顺序。
- `MoreApp`：值类型是**布尔（`dataType=0x12`）而不是字符串**，
  必须用 `--meta-bool`，不能用 `--meta`。

判定依据与"对照实验"验证法见 `references/desktop-registration.md`。

## 签名：必须用 AOSP testkey

红旗车机放行的样本用的都是 **AOSP 公开 testkey**（非泄露密钥）：

```
CN=Android, O=Android, L=Mountain View
SHA256 A4:0D:A8:0A:59:D1:70:CA:A9:50:CF:15:C1:8C:45:4D:47:A3:9B:26:98:9D:8B:64:0E:CD:74:5B:A7:1B:F5:DC
```

`scripts/testkey.jks` 已内置（别名 `testkey`，口令 `android`）。
自签证书会导致同名包报 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`，不要用。
密钥库丢失时的重建步骤见 `references/environment-setup.md`。

## 目录约定：脚本随技能，数据随项目

| 用途 | 位置 | 说明 |
|---|---|---|
| **脚本** | `<技能目录>/scripts/` | 由脚本自身位置自解析，技能装到哪都自洽，不硬编码 |
| **中间产物** | `<当前项目>/.hongqi-car-apk/work/` | 验证解包目录、未签名中间件、临时下载的工具 |
| **交付物** | `<当前项目>/.hongqi-car-apk/out/` | 各变体 APK、`原版/`（源样本备份）、`安装与测试说明.txt` |

两种目录都跟着「当前工作目录 / 当前项目」走，规则实现在 `scripts/_dirs.py`：
在哪个项目里跑，数据就落在哪个项目里，不污染技能安装目录，也**绝不写进其他项目
或其他 agent 的工作目录**。

解析顺序（命中即止）：

1. `$HQCAR_WORK_DIR` / `$HQCAR_OUT_DIR` 显式指定
2. **当前项目根** `/.hongqi-car-apk/` —— 「项目根」= 从 `$PWD` 逐级向上第一个含 `.git` / `AGENTS.md` / `package.json` / `pyproject.toml` 的目录
3. 无项目标记但当前目录安全 → `$PWD/.hongqi-car-apk/`
4. 当前目录不安全（`/`、`$HOME` 根、`/tmp`、`$TMPDIR`、其他 agent 的家目录、或技能目录内部）→ 退回 `<技能目录>/work/` 与 `<技能目录>/out/`

第 4 条是护栏：**在别人的仓库、其他 agent 的工作目录或 `/tmp` 里运行，
数据退回技能自己目录，绝不外溢。**

排查当前解析到哪：

```bash
python3 <技能目录>/scripts/_dirs.py        # 打印 skill / cwd / root / work / out
python3 <技能目录>/scripts/_dirs.py out    # 只打印交付目录
```

同组变体之间包名与签名相同，可互相覆盖安装，便于对照测试。

## 标准流程

```bash
SK=<技能目录>                      # 技能装在哪就用哪，脚本自身位置自解析
W=$(python3 $SK/scripts/_dirs.py work)     # 中间产物目录
O=$(python3 $SK/scripts/_dirs.py out)      # 交付目录

# 0) 侦查：读包名 / 启动 Activity / 已有桌面注册（不依赖 apktool）
python3 $SK/scripts/axml_meta.py 目标.apk --detect

# 1) 改包名 + 注入桌面注册（一步完成）
python3 $SK/scripts/axml_meta.py 原包.apk "$O/输出.apk" com.android.gallery3d \
  --meta "Group=GROUP CARPLAY" --meta "Domain=DOMAIN CARPLAY" \
  --meta "Ability=@auto" --meta-bool "MoreApp=true" --verbose

# 2) 验证（必做）：apktool 独立解码，解包目录放进中间产物目录
#    注：apktool.jar 未随技能打包（约 24 MB），首次用时按 references/environment-setup.md
#    的地址下载一次到 $W/tools/ 即可；第 0、1、3、4 步都不依赖它。
java -jar $W/tools/apktool.jar d -f -s -o "$W/verify" "$O/输出.apk"
#    判定：无 Exception / 输出 Regular manifest package...（不是 Renamed）
#          / 4 项 meta-data 落在 </application> 之前

# 3) 对齐 + 签名（uber-apk-signer 自带三平台 zipalign）
java -jar $SK/scripts/uber-apk-signer.jar -a "$O/输出.apk" \
  --ks $SK/scripts/testkey.jks --ksAlias testkey --ksPass android --ksKeyPass android -o "$W/signed"

# 4) 结构比对：相对原包只应变化 AndroidManifest.xml
#    （改包名时 resources.arsc 内容变化但长度不变）
```

一条龙（改包名 / 不改包名 + 注入 + 签名 + 自检）：
```bash
# 交付位置：默认 <交付目录>/<源文件名>-<包名>.apk（交付目录跟着当前项目走），
#           可用 -o 指定文件或目录，或设 $HQCAR_OUT_DIR 钉死。
bash scripts/build_variant.sh 原包.apk com.android.htmlviewer          # 改包名 + 注入桌面注册
bash scripts/build_variant.sh 原包.apk com.android.htmlviewer --no-meta # 只改包名（后台启动版）
bash scripts/build_variant.sh 现成白名单版.apk --keep-package           # 只注入，不改包名
bash scripts/build_variant.sh 原包.apk com.android.gallery3d -o 出.apk  # 指定完整输出路径
```

## 交付前验证清单

- [ ] apktool 解码无 `Unknown chunk type` / `Unknown event: -1`
- [ ] 输出 `Regular manifest package...` 而非 `Renamed manifest package found!`
- [ ] `package="<新包名>"` 正确
- [ ] 4 项 meta-data 均在，且 `MoreApp` 显示为 `<类型 0x12, 值 4294967295>`
- [ ] `classes*.dex`、`lib/**/*.so` 尺寸与原包完全一致
- [ ] `resources.arsc` 尺寸与原包一致（改包名时内容变、长度不变）
- [ ] 新增条目只有签名文件
- [ ] 签名 SHA256 前 8 位为 `A4:0D:A8:0A`

## 安装与排错

工程模式入口、adb 安装步骤、报错对照表、预期管理见
`references/h5-install-and-troubleshoot.md`。

**通用提醒：改完必须重启车机再判断桌面图标**——原厂 Launcher 对新装应用的
响应常有滞后，冷启动才重新扫描桌面条目。

## 已知坑

- **macOS 自带 BSD grep 不支持 `\|` 交替**，用它数 meta-data 会得到 0 的假阴性，
  改用 `grep -E` 或拆开写。
- 在大型 smali 解包目录上跑后台 `grep -rl` 容易被 SIGTERM(137)，
  优先用专用搜索工具。
- 二进制 AXML 的手工改写细节（`attributeStart` 基准、`stringsStart` 基准、
  字符串池计数同步等）见 `references/axml-binary-format.md`。

## 迁移到其他车型

方法完全通用，换车只需重新做两步取证：
1. 找一个"能在该车机上装成功"的 APK，解析其包名 → 它就是白名单条目；
2. 找一个"能出现在该车机桌面"的 APK，对比它与其他应用的 manifest 差集，
   找出该车型的桌面注册键名与取值。

脚本与判断逻辑无需改动。

## 附带资源

- `scripts/axml_meta.py` — 改包名 / 仅注入桌面注册 / 侦查，三合一
- `scripts/axml_rename.py` — AXML 字符串池改写库 + 只改包名的 CLI
- `scripts/dump_manifest.py` — 秒读包名与签名，不依赖 apktool
- `scripts/_dirs.py` — 两种目录（work / out）的解析与安全护栏；可单独运行排查
- `scripts/build_variant.sh` — 一条龙（改包名 + 注入 + testkey 签名 + 自检）；
  默认交付到 `<当前项目>/.hongqi-car-apk/out/`，支持 `--keep-package` / `--no-meta` / `-o`
- `scripts/testkey.jks` — AOSP testkey（别名 `testkey`，口令 `android`）
- `scripts/uber-apk-signer.jar` — 签名器，自带三平台 zipalign（缺失时脚本会自动下载）
- `references/whitelist-packages.md` — 白名单取证方法与包名占用矩阵
- `references/desktop-registration.md` — 桌面注册协议、判定依据、对照实验法
- `references/axml-binary-format.md` — 二进制 AXML 元素注入的字节级要点
- `references/h5-install-and-troubleshoot.md` — 工程模式、安装步骤、报错对照
- `references/environment-setup.md` — 工具链获取、testkey.jks 重建、"何时改包名也无用"
