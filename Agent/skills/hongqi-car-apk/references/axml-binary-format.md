# 二进制 AXML 改写要点（改包名 / 注入元素）

自己实现或修补脚本时必须遵守的字节级约束。踩中任意一条，apktool 会立刻报
`Unknown chunk type at: (0x...) skipping...` + `Unknown event: -1`。

## 整体布局

```
[8 字节] ResChunk_header (根, type=0x0003 RES_XML_TYPE, headerSize=8, size=文件总长)
[字符串池 chunk]  type=0x0001
[资源映射 chunk]  type=0x0180（可跳过，不在 XML 节点遍历范围）
[XML 节点 chunk ...]  0x0100 start-namespace / 0x0102 start-element / 0x0103 end-element
```

遍历节点时用"按 `ResChunk_header.size` 顺序前进"的方式逐个 chunk 跳过，
只处理 `0x0102` / `0x0103`。

## 字符串池重建

```
stringsStart = header_size + 4*stringCount + 4*styleCount
```

**`header_size`（0x1C = 28）已经包含 `ResChunk_header` 的 8 字节，不要再 +8。**
这是最容易犯的错——加了 8 会让 chunk 头部错位。

其它约束：
- 每个字符串按 **4 字节对齐**补零；
- chunk 总长 = `header_size + 4*stringCount + 4*styleCount + len(字符串数据)`；
- 字符串池之后的全部数据**原样拼接**；
- 最后回填根 chunk（文件偏移 4）的 size。

若采用"只在末尾追加新字符串"的增量策略，则**既有条目的索引全部不变**，
所有已存在的节点引用无需修改。追加后**必须同步 `string_count`**，
否则 `struct.pack` 会报 `expected N items for packing (got M)`。

## START_ELEMENT（0x0102）构造

```
ResChunk_header: type=0x0102, headerSize=16, size
lineNumber(4)
comment(4)          => 无注释时填 0xFFFFFFFF
--- ResXMLTree_attrExt ---
ns(4)               无命名空间时 0xFFFFFFFF
name(4)             元素名字符串池索引
attributeStart(2)   填 20
attributeSize(2)    填 20
attributeCount(2)
idIndex(2)=0  classIndex(2)=0  styleIndex(2)=0
--- 属性区，紧接 attrExt ---
每个属性 20 字节
```

- `size = 16 + 20 + 20 * attributeCount`
- **`attributeStart` 是相对 `attrExt` 起始的偏移**（即 `chunk起始 + 16`），
  不是相对 chunk 起始。属性区绝对偏移 = `chunk偏移 + 16 + attributeStart`。
  这一点在**读取**时同样成立——解析属性时算错基准会读出乱值。
- 元素本身无命名空间时 `ns` 填 `0xFFFFFFFF`。

## 属性（20 字节）

```
ns(4)       属性命名空间（android 命名空间字符串池索引）
name(4)     属性名（local name）
rawValue(4) 原始字符串值索引（无则 0xFFFFFFFF）
Res_value: size(2)=8, res0(1)=0, dataType(1), data(4)
```

| 值类型 | dataType | rawValue | data |
|---|---|---|---|
| 字符串 | `0x03` | = 字符串池索引 | = 字符串池索引 |
| 布尔 true | `0x12` | `0xFFFFFFFF` | `0xFFFFFFFF` |
| 布尔 false | `0x12` | `0xFFFFFFFF` | `0` |

`android:name` / `android:value` / android 命名空间 URI
（`http://schemas.android.com/apk/res/android`）这些字符串**通常已存在于池中**，
直接复用其索引即可。

## END_ELEMENT（0x0103）

固定 24 字节：`headerSize=16`、`size=24`、
`lineNumber(4)`、`comment(4)=0xFFFFFFFF`、`ns(4)`、`name(4)`。

插入位置：找到 `name == "application"` 的 END_ELEMENT 字节偏移，
把新构造的 element 字节块插到它**之前**。

## 不需要改的部分

- `RES_XML_RESOURCE_MAP`：因为新增的字符串只作为**值**使用、不作文档属性名，
  资源映射无需改动。
- 插入元素后只需回填根 XML chunk（偏移 4）的 size。

## resources.arsc 的包名同步

`ResTable_package` 结构里的 `name` 是 **`char16_t name[128]`，固定 256 字节**，
不是字符串池引用——可以**原地无损改写**，零结构风险。

定位方式：在 `resources.arsc` 中遍历 chunk，找到
`RES_TABLE_PACKAGE_TYPE`（`0x0200`）的 chunk，
其包名字段偏移 = `chunk偏移 + 12`（chunk 头 8 字节 + id 4 字节）。

不同步的症状：apktool 解码时打印
`Renamed manifest package found! Replacing <新包名> with <旧包名>`。
**校验时必须确认输出的是 `Regular manifest package...`。**

## 改包名的精确范围

只替换**恰好等于原包名**的那一个字符串条目（正常情况下全表唯一）。
清单里 `原包名.xxx` 形式（自定义权限名、ContentProvider authority、
服务 action）必须保持原样——这些字符串同时硬编码在 dex 常量池里，
单方面改清单会造成清单与代码失配。

实现时可先断言"全表恰好 1 个条目等于原包名"，不等于 1 就终止，
避免误改。

## 验证手段（三条互相独立）

1. `apktool d -f -s` 独立解码 —— 不报错且输出 `Regular manifest package...`
2. 自带 `--detect` —— 回读包名 / 启动 Activity / `<application>` 级 meta-data
3. 结构比对 —— 相对原包只变化 `AndroidManifest.xml`；
   `classes*.dex`、`lib/**/*.so` 尺寸完全一致；`resources.arsc` 长度不变；
   只新增签名文件
