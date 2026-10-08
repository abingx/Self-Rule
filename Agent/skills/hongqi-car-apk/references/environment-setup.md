# 环境准备、密钥重建与能力边界

## 工具链

```bash
SK=<技能目录>
W=$(python3 $SK/scripts/_dirs.py work)     # 中间产物目录（工具缓存放这里）
mkdir -p "$W/tools"

# JDK（macOS Homebrew；先确认 brew 前缀是 /usr/local 还是 /opt/homebrew）
ls /usr/local/opt/openjdk/bin/java /opt/homebrew/opt/openjdk/bin/java 2>/dev/null

# apktool —— 仅用于改前改后的"验证解码"，不用于重建
curl -sL -o "$W/tools/apktool.jar" \
  https://github.com/iBotPeaches/Apktool/releases/download/v2.11.1/apktool_2.11.1.jar

# uber-apk-signer —— 自带 mac/linux/win 三平台 zipalign，一次完成对齐+签名+校验
# （随技能已打包一份，缺失时 build_variant.sh 会自动下到 $W/tools/）
curl -sL -o "$W/tools/uber-apk-signer.jar" \
  https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar
```

- **不需要 Android build-tools**：uber-apk-signer 内置 zipalign（运行时解包到临时目录）。
  若确要下载，注意 Google 仓库里文件名是 `build-tools_rXX-macosx.zip`，
  写成 `-mac.zip` 会 404。
- **不需要 androguard**：本技能自带 AXML 解析器，够用。
  且 `pip install androguard` 在部分环境会因 `mutf8` 包报 `EEXIST: ... mkdir` 失败。

### 哪些是随技能打包的

| 组件 | 是否打包 | 说明 |
|---|---|---|
| `axml_*.py` / `dump_manifest.py` / `_dirs.py` / `build_variant.sh` | 是 | 纯 Python / Bash，无外部依赖 |
| `testkey.jks` | 是 | AOSP testkey，直接可用 |
| `uber-apk-signer.jar` | 是（约 3 MB） | 签名必需；若丢失，`build_variant.sh` 会自动下到中间产物目录 |
| `apktool.jar` | 否（约 24 MB） | 仅"验证解码"一步需要，首次按上面的地址下载一次 |

环境变量可覆盖脚本里的默认路径：`JAVA_HOME`、`PY`、`HQCAR_WORK_DIR`、`HQCAR_OUT_DIR`
（后两者见 SKILL.md「目录约定」）。

## 重建 testkey.jks

`scripts/testkey.jks` 已内置（别名 `testkey`，口令 `android`），正常无需重建。
若该文件丢失，按以下步骤从 AOSP 官方仓库取回并转换
（testkey 的私钥由 Google 公开发布，**不是泄露密钥**）：

```bash
# 1) 下载（googlesource 返回 base64 编码）
curl -s -o testkey.pk8.b64 \
  "https://android.googlesource.com/platform/build/+/refs/heads/main/target/product/security/testkey.pk8?format=TEXT"
curl -s -o testkey.x509.pem.b64 \
  "https://android.googlesource.com/platform/build/+/refs/heads/main/target/product/security/testkey.x509.pem?format=TEXT"

# 2) base64 解码
python3 -c "import base64;open('testkey.pk8','wb').write(base64.b64decode(open('testkey.pk8.b64','rb').read()))"
python3 -c "import base64;open('testkey.x509.pem','wb').write(base64.b64decode(open('testkey.x509.pem.b64','rb').read()))"

# 3) PKCS#8 DER -> PEM
openssl pkcs8 -inform DER -nocrypt -in testkey.pk8 -out testkey.key.pem

# 4) 必须先验公私钥配对（无输出才算通过）
diff <(openssl rsa -in testkey.key.pem -pubout) \
     <(openssl x509 -in testkey.x509.pem -pubkey -noout)

# 5) 转成 JKS
openssl pkcs12 -export -in testkey.x509.pem -inkey testkey.key.pem \
  -name testkey -out testkey.p12 -passout pass:android
keytool -importkeystore -srckeystore testkey.p12 -srcstoretype PKCS12 \
  -srcstorepass android -destkeystore testkey.jks -deststorepass android \
  -destkeypass android -alias testkey -noprompt

# 6) 核对指纹必须为 A4:0D:A8:0A:59:D1:70:CA:A9:50:CF:15:C1:8C:45:4D:47:A3:9B:26:98:9D:8B:64:0E:CD:74:5B:A7:1B:F5:DC
keytool -list -v -keystore testkey.jks -storepass android -alias testkey
```

## 查看任意 APK 的签名证书

```bash
keytool -printcert -jarfile 样本.apk
```
若 SHA256 是 `A4:0D:A8:0A...`（CN=Android, O=Android, L=Mountain View），
即 AOSP testkey，说明该样本可用于反推车机放行规则。

## 自签证书的适用场景

只有当样本用的是**拿不到私钥的私有证书**、或车机确实不校验签名时，才退而自签：

```bash
keytool -genkeypair -v -keystore my.jks -alias <alias> \
  -keyalg RSA -keysize 2048 -validity 10950 \
  -storepass <pw> -keypass <pw> -dname "CN=Personal Mod, C=CN"
```

注意：自签证书**无法覆盖**用另一密钥签名的同名应用，只能先卸载旧版再装。

## 何时改包名也无用（要如实告知用户）

1. **编造的新包名不在白名单里** —— 改包名本身不创造白名单资格，必须用真实放行的
   包名。这是最常见的失败原因。
2. **车机校验的是签名而非包名**（白名单里带 signInfo）—— 需要样本同款密钥
   （通常是 testkey）；若样本用的是拿不到私钥的私有证书，改包名无解。
3. **应用的 `minSdkVersion` 高于车机 Android 版本** —— 需另行降 minSdk，
   且降了也可能在运行时缺 API（不少投屏/桌面类应用要求 Android 9+）。
4. **车机把 APK 限定必须装在 `/system/app`** —— 需要 root，本方案不覆盖。

## 其它环境提示

- **macOS 自带 BSD grep 不支持 `\|` 交替**。用 `grep 'a\|b'` 数 meta-data
  会得到 0 的假阴性，改用 `grep -E` 或拆开写。
- 在大型 smali 解包目录上跑后台 `grep -rl` 容易被 SIGTERM(137) 杀掉，
  优先用专门的文件搜索工具。
