---
name: yayarun-daily-summary
description: "拉取跑鸭·RunYay 里用户的跑步数据，清理过期卡片，产出单文件离线 HTML 卡片，并推送 Bark 通知到 iPhone。当用户说「拉取跑鸭/今日跑步」「跑步概况」「生成跑步卡片」「跑步日报/总结」「清理跑鸭旧文件」「发 bark 通知」时使用。用户只要求其中某一步时（如只清理旧文件、只重发通知），只执行对应步骤，不要跑全链路。"
---

# 跑鸭跑步卡片全流程

一条链路跑完：**取数 → 清理旧文件 → 渲染卡片 → 推通知**，产物落在 `~/Documents/YaYaRun`。

**只读**。本 skill 不修改训练计划；用户要改计划时走跑鸭 MCP 的计划写入工具。

> 单步细节见 `scripts/` 内脚本的 docstring。本文件讲整条链路怎么串、有哪些坑。
> 下文 `<技能目录>` 一律用**绝对路径**（当前为 `~/.config/magpie/library/skills/yayarun-daily-summary`）；
> `<项目目录>/.yayarun-daily-summary/_work/latest.json` 是取数落盘位置，
> **不要依赖当前工作目录，也不要写进技能目录**（见下方「中间产物位置」）。

**范围**：用户只说「清理旧文件」→ 只跑第 2 步；「重发通知」→ 只跑第 4 步；不要顺手取数/渲染/推送。

## 前置：确认日期口径（最常出错的一步）

**「今日跑步」未必存在。** 跑鸭里最新一次跑步经常是昨天甚至更早。开工前先确认：

```
runyay_get_run_summaries(startDate=<今天>, endDate=<今天>)
```

- **返回非空** → 用今天这条。
- **返回空** → 今天没跑。**不要**默默改用最新一条，先问用户：「今天没有记录，最新一条是 `<日期>` 的 `<距离>`，用它吗？」

整个链路里的「日期」始终指**卡片对应的那次跑步的日期**，不是当前日期。卡片文件名、Bark 正文、周几全部以它为准。

`startTimeInSeconds` 形如 `"20260929053122"`（`YYYYMMDDHHMMSS`），用它取日期比自己算可靠。
`fetch_data.py` 会把它解析进 `_meta.runDate`，并在最新跑步不是今天时**打印 `[注意]`**——看到就回到上面的确认流程。

## 第 1 步：取数

三次 MCP 调用，可并行发：

1. `runyay_get_latest_run_summary`（无参）→ 最新一次跑步 `summary`
2. `runyay_get_run_summaries(startDate=<今天-6天>, endDate=<今天>, pageSize=100)` → 近 7 天列表（含今天；`fetch_data.py --days 7` 同口径）
3. `runyay_get_run_segments(activityId=<activityId>)` → 分段明细

坑：

- `activityId` **必须带 `-file` 后缀**（或 `manual_v2_*`）；传纯数字报 `-32000 跑步记录不存在`。
- `segments` 为**空数组**时**照常渲染**：卡片给出一个占位区块，绝不静默留空。服务端对最新一次常「当时为空、隔次可取到」，所以空返回不等于没分段，**不要连发重试**；稍后重新取数并重渲染即可补上。
- `weatherTemperature` / `weatherHumidity` 实测恒为 `0`，属无效值 —— 如实留空或标注，**不要**当 0℃ / 0% 展示。

拿到后**原样落盘**到 `<项目目录>/.yayarun-daily-summary/_work/latest.json`（覆写式，不累积，脚本用临时文件+替换写入），**不要手工裁剪字段**：曾精简 `recent` 把 `activityId` 弄丢导致后续取不了分段。`segments` 有 20+ 条时手工转写必错。

推荐用脚本（自带 MCP 握手：session id + initialized 通知，SSE 按 id 取响应，网络错误/5xx 自动重试）：

```
python3 <技能目录>/scripts/fetch_data.py --days 7
python3 <技能目录>/scripts/fetch_data.py --self-test     # 改动传输层后先跑这个
```

若走平台原生 MCP 工具取数，**按上面字段口径**组装同样结构的 JSON（顶层 `latest` / `segments` / `recent`）再喂给下一步。

## 第 2 步：清理七天前的文件

按**修改时间**判断，只清理 `~/Documents/YaYaRun` **顶层**、文件名以 `run-summary-` 开头的文件：

```
python3 <技能目录>/scripts/cleanup_old.py --days 7            # 先看
python3 <技能目录>/scripts/cleanup_old.py --days 7 --apply    # 再删（加 --trash 可移入废纸篓）
```

默认 dry-run，**必须先看再删**。

坑：

- **没有可删文件是正常结果**，不要为了「完成任务」放宽阈值去删还在窗口内的文件。报告「无文件超期」即可。
- 子目录、隐藏文件、符号链接一律不动。
- 要清理**非本链路**文件才加 `--all`，且必须先向用户确认预览列表。
- `--days` 小于 1、`--dir` 指向 `/` 或家目录会被脚本拒绝。

## 第 3 步：渲染卡片

```
python3 <技能目录>/scripts/render_card.py <项目目录>/.yayarun-daily-summary/_work/latest.json ~/Documents/YaYaRun/run-summary-<日期>.html
```

产出**单文件离线 HTML**：内联 CSS，**无 SVG、无 JS**，除品牌 Logo 外零外部依赖（Logo 加载失败会自动隐藏）。
**退出码非 0 = 自检未过，旧文件不会被覆盖，此时不要进入第 4 步。**

必需元素：

- Hero 区含距离 / 时长 / 配速 / 心率，以及**品牌名与 Logo**
- **不再渲染任何图表**：配速曲线 / 心率曲线 / 心率区间条 / 步频功率柱状**均已移除**，
  预期 `<svg>` 数为 **0**（脚本自检会打印 `图表 N 张`）。要加回图表须先向用户确认。
- 分段明细表：**按训练类型分组**（段=连续同类型组，灰底+类型配色+整行加粗+组均值；
  子段=组内各圈，常规字重，首列为该段距离）
- 页脚标注 **`数据来源：跑鸭·RunYay`**（品牌规范要求）

品牌规范（来自 `runyay_get_brand_context`）：主色 `#1AA9F8`，Logo `https://yayarun.cn/images/smalllogo.jpg`，
界面用品牌色（表头、类型标签、强调色），页脚带署名。

**分段表约定**（用户明确要求，改动前先确认）：

- 列为 **距离 / 用时 / 配速 / 心率 / 步频 / 功率 / 触地 / 步幅 / 垂直振幅 / 爬升**；
  **没有「距离 (m)」列**，**不显示「尾段」标记**。
- 「用时」是**该段自身时长**，不是累计。
- 一级分组按 `intervalType`（热身 / 训练 / 间歇 / 恢复 / 缓和 / 休息 / 其他）切成**连续段**，
  保持实际训练顺序，**不做"按类型归并"** —— 归并会把间歇课的多个训练圈凑成一堆、打乱节奏；
- **段（父行）**= 连续同类型组：灰底 + **整行加粗**，第一列**只放类型名**
  （热身 / 训练 / 恢复 / 缓和…，**不显示组序号、组距离、段数**），
  其余列放该组汇总 —— **用时是求和项（该组合计，不是平均值）**；
  功率 / 触地 / 步幅 / 垂直振幅 / 爬升取**算术平均**（缺该字段的段不参与平均，全缺显示 `—`）；
  配速按"总时长÷总距离"加权。
- **子段（子行）**= 组内各圈：整行**常规字重**，第一列放**该段距离**（`1.02 km`，不再有组内序号），
  其余列是该圈自身数据。
- **不是**按公里拆分。间歇跑的"1 公里"与"1 圈"不是一回事，硬按公里切会串数据。

**分段版面面向手机**（主要在 iPhone 14 竖屏 390×844 预览）：
窄屏（`MOBILE_MAX_W=480`）下**表格保持表格形态 + 横向滚动**（`table.seg { min-width: 560px }`），
**不要改成卡片堆叠** —— 那会破坏父行/子行的分组关系。极小屏（≤360px）再收一档间距与字号。

坑：

- **配速原始值单位是「分钟/公里」**（`5.311` → `5'19"`），不是秒/公里。脚本内部字段叫 `paceMinPerKm`；
  展示统一走 `fmt_pace`，别直接 `:.0f`。
- **接口不返回 `distanceMeters`**。DISTANCE 与 LAP 两套分段**都缺**，脚本用
  `(时长/60) / 配速(分钟每公里) × 1000` 反推 —— 反推合计与摘要距离一致（实测 9798.2 m vs 9798.21 m）。
- **DISTANCE 与 LAP 两套分段字段互补**：DISTANCE 有配速/心率/爬升，缺功率、触地、步幅、垂直振幅；
  LAP 有这些。脚本以 DISTANCE 为骨架、按 `segmentIndex` 用 LAP 回填，**仅当同序号 LAP 的距离/时长在 ±5% 内才回填**
  （手动分圈时序号对不上，宁可留空也不串数据，并在 stderr 给出警告）。
  分段类型同时认 `segmentType` 与 `segmentCategory`；两者都不认识时会告警，不会静默当成"无分段"。
- **间歇课走另一条路径**：LAP 的 `intervalType` 出现**多于一种取值**时（如 9/28：warmup×2 / work×8 /
  recovery×3 / cooldown×3），判定 `isInterval=True`，直接以 **LAP 为骨架**、按类型分组，
  **不再做 DISTANCE↔LAP 回填**（两套序号体系不同，16 段 vs 11 段）。全是 `work` 的普通跑步
  （如 9/29 的 11 段）**不算**间歇课，仍走上面的回填路径。
- **间歇课的措辞要跟着换**：段号不是公里。分段表按「热身/训练/恢复/缓和」父行分组、
  子行只写**该段距离**（不写「第 N 公里」，也不写全局段号），
  训练解读改用「训练段 N 组…恢复段 M 组（配速），快慢差 X 秒/公里」，并**跳过心率漂移**
  （热身/冲刺/恢复交替，首末段对比无生理意义）。
- **步频放大**：脚本对 `>= 400` 的步频除以 100（摘要与分段都处理）。注意 `1.8E2` 只是 `180` 的科学计数法写法，解析后就是 180，不需要处理。
- **不足 1 km 的尾段**：只有**最后一段**才可能被标「尾段」，且**不参与**最快/最慢/极差/心率漂移统计。
  间歇课不打这个标记（每段本来就长短不一）。
- **`segments: []` 时不能直接 `min()/max()`**；空分段走占位分支，其余部分照常渲染。
- **垂直振幅比**要 **×100** 再当百分比显示（`0.079218` → `7.9%`）。
- **缺字段**（手动记录、无跑步动力学的设备）：卡片显示 `—`，对应"训练解读"条目自动省略，不会崩溃也不会出现 `None`。
- **训练解读全部由本次数据驱动**（强度档位、配速极差档位、心率漂移、经济性），阈值是经验值，写在 `_insights()` 里，可按个人口径调。不要在模板里写死具体数字或时长。
- `userMaxHeartRate` 接口缺失时兜底用 `DEFAULT_MAX_HR`（脚本顶部常量，个人值，需要时自行改）。
- 落盘后**自检**：标签闭合、可见文本里无 `None`/`NaN` 泄漏（`render_card.py` 会打印结果，并报告 `图表 0 张`）。
- 若环境里有 headless 浏览器可以做视觉截图核验；若不可用（本机 Brave headless 实测会挂起），**如实说明未做视觉验证**，不要假装看过。
- 未实测的假设：分段缺 `avgPace` 时用 `avgSpeed` 兜底，脚本按 km/h 换算；若发现接口给的是 m/s，需要改 `normalize()` 里的那一行。

## 第 4 步：推 Bark 通知

```
python3 <技能目录>/scripts/push_bark.py --file run-summary-<日期>.html --date <日期> --dry-run
python3 <技能目录>/scripts/push_bark.py --file run-summary-<日期>.html --date <日期>
python3 <技能目录>/scripts/push_bark.py --self-test
```

脚本用 Bark 的 **`POST /push` + JSON 请求体**（`device_key / title / body / group / icon / url`）：

1. key：先读环境变量 `BARK_API_KEY_iPhone14`，没有再读 `~/.zshrc`（**取最后一条**、shlex 解析：支持引号与行尾注释；
   值含 `$VAR` / `$(...)` 会明确报错；**不用 `sed`**）。
2. shortcuts 回调：`shortcuts://run-shortcut?name=<名>&input=text&text=<文件名>`，`name` 与 `text` 各 URL 编码一次。
3. 回调作为 JSON 字段 `url` **原样传**。旧的 GET 拼接写法才需要把 `url` 整体再编码一次
   （否则回调被 `&` 截断、通知照发点了没反应）——**如果你改回 GET 路径写法，这个坑会复活**。

坑：

- **日期用跑步日期**，不是今天（脚本不会回落到今天：拿不到日期直接报错）。
- 卡片文件不存在时脚本拒绝推送（避免推出一个点了打不开的通知）。
- key 只出现在请求体里，不在 URL / 命令行 / 日志中；dry-run 与报错同样只显示掩码（`VLYP****9LXN`）。**任何输出都不得出现完整 key。**
- 带 key 只允许发往 https（本机 localhost 测试除外）；自建 Bark 服务用 `--api-base https://…` 或环境变量 `BARK_API_BASE`。
- 不做自动重试：POST 超时时服务端可能已收到，重试会重复弹通知；失败先看报错再决定。
- 退出码：`0`=成功 / `1`=失败 / `3`=仅 dry-run。
- 未对真实 Bark 服务做联调（只在本地假服务上验证了请求格式）；首次使用先 `--dry-run` 再实发，确认手机收到、点击能触发快捷指令。

## 凭据与安全

**跑鸭 token 取自 `~/.config/magpie/library.json`** 的 `mcp[]` 数组，取 `name` 匹配 `yayarun`
（也认 `runyay`/`yaya`，支持 `RunYay-MCP` 这类写法）的那一条，token 取自其
`headers.Authorization`（带不带 `Bearer ` 前缀都能识别）。

- 优先级：**`~/.config/magpie/library.json` → 环境变量 `RUNYAY_MCP_URL` / `RUNYAY_MCP_TOKEN`**。
  出现 `[警告] 回退环境变量` 说明配置文件里没找到跑鸭条目（文件缺失、解析失败、或没有跑鸭条目）。
- 支持两种写法：magpie 的 `mcp[]` 数组（主），以及 claude 风格的 `mcpServers` 对象（兼容）。
- 这是**公共技能**，由 magpie 统一分发（库在 `~/.config/magpie/library/skills/`，
  DSH 通过 `~/.dsh/skills/<name>` 软链引用）。
- 要让脚本用上新凭据，改 `~/.config/magpie/library.json` 即可 —— 脚本每次运行都现读，无需重启。
- 该文件权限为 `644`（对同组/其他用户可读），脚本会打 `[警告]` 提示 `chmod 600`。
- Bark key 存在 `~/.zshrc`（明文）；更稳妥的做法是放进 macOS 钥匙串并导出成环境变量。
- 任何脚本、日志、汇报里都不得出现完整 token / key。

## 完成后汇报

- 清理：删了哪些、或**明确说「无文件超期」**
- 卡片：路径 + 数据来源日期（若与「今天」不一致要讲清楚）；渲染时出现的 `[警告]`（如 LAP 未回填）要转述
- 通知：Bark 返回码，以及**日期取得是跑步日而非今天**
- 未做的验证要如实说明（如没做视觉核验、没联调真实 Bark）

## 中间产物位置

取数结果默认写到**当前项目**内的 `<项目目录>/.yayarun-daily-summary/_work/latest.json`，
**不写进技能目录**。原因：本技能由 magpie 托管（库在 `~/.config/magpie/library/skills/`），
是公共只读资产；把中间产物写进去既污染库，也可能在 magpie 同步时被清掉。

- 项目根判定：从 CWD 向上找带 `.git` 或 `.yayarun-daily-summary` 的目录；找不到就用 CWD 本身。
- 可用 `--work-dir <目录>` 或 `--out <文件>` 显式覆盖。
- 若确实需要落在旧的技能内路径，显式传 `--out <技能目录>/_work/latest.json` 即可。

## 脚本清单

| 脚本 | 作用 | 自检 |
|---|---|---|
| `scripts/fetch_data.py` | MCP 取数 → `<项目目录>/.yayarun-daily-summary/_work/latest.json` | `--self-test`（本地假 MCP 服务） |
| `scripts/cleanup_old.py` | 清理超期文件（默认 dry-run） | 先 dry-run |
| `scripts/render_card.py` | JSON → 单文件离线 HTML | 内置自检，退出码反映结果 |
| `scripts/push_bark.py` | 组装并推送 Bark 通知 | `--self-test`（本地假 Bark） |