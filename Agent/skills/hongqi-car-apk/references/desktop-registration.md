# 桌面注册协议：让应用出现在红旗车机桌面

## 现象与结论

两组实测样本都能安装、都能从"系统管理后台"启动，但一组**桌面有图标**、
另一组**没有**。逐项排除后定位到唯一实质差异。

### 排除过程（对照表）

| 候选因素 | 不能上桌面的样本 | 能上桌面的样本 | 是否决定性 |
|---|---|---|---|
| 包名 | `com.android.statementservice` | `com.android.statementservice` | ✗ 完全重合 |
| 签名 | AOSP testkey | AOSP testkey（同一张证书） | ✗ 完全相同 |
| MAIN/LAUNCHER 入口 | **有** | 有 | ✗ 两边都有 |
| `<application>` 下 4 项 meta-data | **无** | **有** | ✓ 唯一实质差异 |

**结论：红旗原厂 Launcher 不按标准 LAUNCHER 意图扫描桌面图标，而是读应用
`<application>` 下的一组约定 `meta-data` 来构建桌面入口。**
缺这组声明 → 装得上、能跑，但桌面不给图标。

顺带排除的常见误判：
- 不是包名决定的（有包名完全重合的反例）；
- 不是签名决定的（两边同一张证书）；
- 不是缺 LAUNCHER 意图（不能显示的那组**也**声明了 MAIN/LAUNCHER）。

## 需要注入的 4 条声明

位置：`<application>` 直属子元素，紧邻 `</application>` 之前。
（实测样本中这 4 条就位于 `<application>` 的最后，且在 provider 等元素之后。）

```xml
<meta-data android:name="Group"    android:value="GROUP CARPLAY"/>
<meta-data android:name="Domain"   android:value="DOMAIN CARPLAY"/>
<meta-data android:name="Ability"  android:value="com.xxx.activity.MainActivity"/>
<meta-data android:name="MoreApp"  android:value="true"/>
```

| 键 | 语义推断 | 取值做法 |
|---|---|---|
| `Group` | 桌面分组标签 | **照抄能显示的样本**，不要自创 |
| `Domain` | 领域 / 分类标签 | **照抄能显示的样本**，不要自创 |
| `Ability` | 点击图标后启动的目标组件 | 填**目标应用自己的** MAIN/LAUNCHER Activity 全类名 |
| `MoreApp` | 标记为"更多应用"类别 | 布尔 `true` |

## 关键细节：`MoreApp` 是布尔型，不是字符串

侦查能显示的样本时会看到它是 `<类型 0x12, 值 4294967295>` ——
即 `TYPE_INT_BOOLEAN` + `true`，**不是**字符串 `"true"`（字符串是 `0x03`）。

aapt 在编译 `<meta-data android:value="true">` 时确实会把它转成布尔。
因此注入时必须写布尔型：

```bash
--meta-bool "MoreApp=true"      # 正确：dataType=0x12, rawValue=data=0xFFFFFFFF
--meta      "MoreApp=true"      # 错误：写成了字符串型
```

`Group` / `Domain` / `Ability` 三项是字符串型（`0x03`），用 `--meta` 即可。

## 声明顺序

照抄样本的顺序（Group → Domain → Ability → MoreApp）。
工具通过 `--meta "Ability=@auto"` 在**原位置**展开自动探测到的 Activity，
从而保持顺序一致，而不是追加到末尾。

## 对照实验：验证机制而不是一次全押

当推断只基于一份"能显示"的样本时，结论可能过拟合。稳妥做法是**同时发两组对照包**：

- 同一份原 APK 出一个"只改包名"（后台启动版）和一个"改包名 + 注入注册"（桌面显示版）；
- 两版同包名、同证书 → 后者可直接覆盖前者，**一次重启就能得出结论**。

判读：
- 显示 → 机制成立；
- 不显示 → 该车型的 `Group` / `Domain` 取值另有枚举，需要用户提供车机后台的应用列表
  截图再对齐取值。

做对照实验时**务必避开用户已经占用的白名单包名**，以免覆盖掉他们正在用的应用。

## 排查顺序

1. **重启车机**。原厂 Launcher 对新装应用的响应常有滞后，冷启动后会重新扫描一遍。
   绝大多数"装完不显示"在重启后即消失。
2. 换另一个包名版本再试（不同包名可能落到不同桌面分组）。
3. 仍不显示 → `Group` / `Domain` 取值需要与车机内部分组枚举对齐。
   请用户提供「系统管理后台」中可见应用的列表截图，据此调整重出。

## 注入实现

用 `scripts/axml_meta.py`，它在二进制 AXML 上做纯增量修改（字符串池只在末尾追加，
在 `</application>` 前插入 element chunk），dex / resources.arsc / 原生库一律不动。

```bash
SK=<技能目录>
O=$(python3 $SK/scripts/_dirs.py out)        # 交付目录（见 SKILL.md 目录约定）

# 改包名 + 注入桌面注册
python3 $SK/scripts/axml_meta.py 原包.apk "$O/输出.apk" com.android.gallery3d \
  --meta "Group=GROUP CARPLAY" --meta "Domain=DOMAIN CARPLAY" \
  --meta "Ability=@auto" --meta-bool "MoreApp=true" --verbose

# 不改包名、只注入（用于加工已有的白名单版 / 加固 APK）
python3 $SK/scripts/axml_meta.py 原包.apk "$O/输出.apk" --keep-package \
  --meta "Group=GROUP CARPLAY" --meta "Ability=@auto" --meta-bool "MoreApp=true"
```

字节级构造要点见 `axml-binary-format.md`。
