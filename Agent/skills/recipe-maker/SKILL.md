---
name: recipe-maker
description: 把美食视频（抖音、B站等）还原成结构化菜谱 md 笔记。当用户给出视频链接（v.douyin.com 短链、www.douyin.com/video/xxx、bilibili.com/video/BV... 或其他平台的美食内容链接）并要求"提取内容/生成菜谱/按模板生成 md/生成笔记"，或给出已有 .md 要求"按模板规范"时使用。覆盖：链接解析、文案与评论抓取、视频下载、口播转写、画面文字抽帧识别、按模板写 md。
agent_created: true
---

# 食谱制作：视频 → 结构化 md 笔记

把美食视频还原成结构化菜谱笔记（食材 / 备菜 / 制作 / 总结）。**支持多平台**：抖音、B站，以及任何能拿到视频文件或字幕的平台。

**平台分流（先判再动手）**：
- `v.douyin.com` / `www.douyin.com/video/xxx` → 走第 1~3 节（`grab.sh` + `dl.sh`）
- `bilibili.com/video/BV...` → 下载与评论走 **5A**，其余环节完全复用
- 其他平台 → 先用官方 `agent-browser` 技能打开页面，照第 1~3 节的字段清单抓元信息/评论，视频拿到手后照 4A/4B 处理

**非菜谱视频也能用这套流程。** 当用户只是问「看看这条视频说了什么」而不是要菜谱时，直接复用 `grab.sh` / `dl.sh` / `asr.py` / `ocr.py` 四件套，把口播+字幕还原成事件叙述即可，不必套菜谱模板、也不必落 md 文件。实测一条 308 秒的徒步 vlog：ASR（small）+ OCR（2 秒/帧）双通道各约 4 分钟并行跑完，字幕几乎条条准确，口播负责把对话串起来。此类视频通常**有硬字幕**，以 OCR 字幕为准、ASR 补语气与称呼，再读几张关键帧核对争议句。

## 目录约定：脚本随技能，数据随项目

**两种目录，各司其职** —— 规则实现在 `scripts/_dirs.sh`（zsh）和 `scripts/_dirs.py`（Python）里，两边算法一致：

| 用途 | 位置 | 说明 |
|---|---|---|
| **脚本** | `<技能目录>/scripts/` | 由脚本自身位置自解析（`${0:A:h}`），**技能装到哪都自洽，不硬编码** |
| **数据** | `<当前项目>/.recipe-maker/work/` | 中间产物（mp4 / 直链 / 元信息 / 字幕 / 抽帧） |
| **笔记** | 配置文件里的 `RECIPE_NOTE_DIR`，默认 `~/Documents/RecipeNotes/` | 最终菜谱 md |

### 把菜谱 md 固定输出到自己的笔记库（推荐做法）

**写配置文件，不要写 `~/.zshrc`**（原因见下）。就在**技能目录内**：

```
<技能目录>/config.env
```

参考 `config.example.env` 建一个（首次可直接复制），填一行即可：

```sh
RECIPE_NOTE_DIR="/Users/you/Library/Mobile Documents/iCloud~md~obsidian/Documents/YourVault/你的食谱目录"
```

这个文件是 shell 的 `KEY=VALUE` 语法，**zsh 脚本与 python 脚本读同一个文件**，
所以两侧永远一致，不需要每次 `export`。路径带空格或中文务必用引号；
支持 `~` 与 `$HOME` 两种写法。

> **本文件是私有的，不要提交/分发。** 技能目录自带的 `.gitignore` 已忽略 `config.env`，
> 所以它不会被 git 跟踪，也不会随技能打包外发；随技能分发的是 `config.example.env` 模板。

配置文件查找顺序（命中即止）：

1. `$RECIPE_MAKER_CONFIG` 指定的路径
2. **`<技能目录>/config.env`** ← 默认位置

确认已生效（两条命令的 `note` 必须相同）：

```zsh
zsh -c 'source <技能目录>/scripts/_dirs.sh; rm_show_dirs'
python3 <技能目录>/scripts/_dirs.py
```

`rm_show_dirs` 会打印实际加载的配置文件路径，以及是否「已加载」，一眼就能定位。

> **优先级**：命令行环境变量 > 配置文件 > 自动解析。
> 想临时改一次，直接内联覆盖即可：`RECIPE_NOTE_DIR=/tmp/out python3 $SK/ocr.py ...`

> ### 为什么不能写 `~/.zshrc`
>
> 实测（`ZDOTDIR` 隔离验证）：`zsh $SK/grab.sh` 是**非交互**调用，只读 `~/.zshenv`，
> **从不读 `~/.zshrc`**；而 agent 执行命令用的工具 shell 是 **bash**，谁都不读 `~/.zshrc`。
> 写在那里 → 读到空值，配置**静默失效**。
>
> 第二个坑：即使写 `~/.zshenv`，也只有 **zsh 脚本**看得到；
> `asr.py` / `ocr.py` 是从 bash 直起的 `python3`，读 `os.environ` 时拿不到 → **两侧目录悄悄分叉**。
> 配置文件走的是「脚本自己读文件」，绕开了这两个坑。

**数据目录解析顺序**（命中即止）：

1. `$RECIPE_WORK_DIR` 显式指定
2. `$OUT` 显式指定（兼容旧用法）
3. 配置文件里的 `RECIPE_WORK_DIR`
4. **当前项目根** `/.recipe-maker/work` —— 「项目根」= 从 `$PWD` 逐级向上第一个含 `.git` / `AGENTS.md` / `package.json` / `pyproject.toml` 的目录
5. 无项目标记、且 `$PWD` 是 `/`、`$HOME` 或临时目录（`/tmp`、`$TMPDIR`）→ `<技能目录>/work/`
6. 其余 → `$PWD/.recipe-maker/work`

第 5 条是关键护栏：**在别人的仓库、其他 agent 的工作目录或 `/tmp` 里运行，数据退回到技能自己的 `work/`，绝不写进别人的项目。** 同理，本技能也从不读写其他技能或其他项目的目录。

排查当前解析到哪：

```zsh
zsh -c 'source <技能目录>/scripts/_dirs.sh; rm_show_dirs'
python3 <技能目录>/scripts/_dirs.py
```

**现成脚本在 `scripts/`（唯一正本，不要复制到别处）。已验证可跑，别再重写内联版本**：

- `grab.sh <短链code...>` — 批量抓元信息 + 评论 + 直链。直链写 `url_<code>.txt`（**已剥 JSON 引号**）、元信息/全量评论/作者回复写 `meta_<code>.txt`、失败项写 `grab_fail.log`；顺带给建议抽帧间隔。`close` 放 `trap`，出错/中断也释放 daemon（走官方 `agent-browser` 技能：`eval --stdin` 规避引号地狱；`AB` 可覆盖，默认从 PATH 找 `agent-browser`）
- `dl.sh <code>:<输出名> ...` — 下载 mp4（自动带 Referer 与桌面 UA + 重试）。**校验必须是真 MP4**：直链过期返回 HTML 时删掉坏文件并提示重跑 grab.sh；有失败则退出码 1
- `ocr.py <video.mp4> [间隔秒] [保留帧目录]` — 抽帧 + OCR，打印并落盘 `subs_<名>.txt`。**默认不落盘**（一次 ffmpeg 解码 + JPEG 管道直喂 OCR，比逐帧起进程快约 1/3）；只有给了第 3 个参数才写帧图。`ocr.py check <video> <t1,t2,...>` 抽指定时间点帧供 Read 核对
- `asr.py <video.mp4> [small|medium] [prompt]` / `... slice <start> <dur> [size] [prompt]` / `... probe [size] [head秒]` — 整片转写、单段复核、**类型探针**（自动判口播型/字幕型并给出抽帧间隔与方言告警；无音轨视频直接提示转 OCR 而不报栈）

**标准跑法**——脚本用绝对路径即可，数据目录自动解析，`cd` 到哪里就跑在哪个项目里：

```zsh
SK=<技能目录>/scripts

zsh $SK/grab.sh <短链code>          # 直链 → <工作目录>/url_<code>.txt；元信息/评论/作者回复 → meta_<code>.txt
zsh $SK/dl.sh <code>:<名>           # mp4  → <工作目录>/<名>.mp4（自动校验真 MP4）
python3 $SK/asr.py <名>.mp4 probe   # 先探类型：口播型 or 字幕型 + 建议抽帧间隔
python3 $SK/asr.py <名>.mp4 small   # 口播型才转写
python3 $SK/ocr.py <名>.mp4 1.0     # 字幕型：不落帧图 → subs_<名>.txt
python3 $SK/ocr.py check <名>.mp4 183   # 克数冲突时抽单帧，用 Read 逐字定稿
```

需要钉死目录时，用**配置文件**（见上文「把菜谱 md 固定输出到自己的笔记库」）或临时内联：

```zsh
RECIPE_WORK_DIR=/data/recipes zsh $SK/grab.sh <code>      # 临时覆盖，只影响这一条命令
RECIPE_NOTE_DIR=/tmp/out python3 $SK/ocr.py <名>.mp4      # 同理，任何脚本都认
```

**依赖**（装到当前 Python 环境即可，脚本不绑定任何固定解释器）：

```zsh
python3 -m pip install faster-whisper imageio-ffmpeg            # ASR（自带静态 ffmpeg）
python3 -m pip install rapidocr-onnxruntime opencv-python numpy # OCR
python3 -m pip install yt-dlp                                   # B站下载（5A）
```

**任务结束只删媒体文件**（`*.mp4` / `frames_*/` / `url_*.txt`，`meta_*.txt` / `subs_*.txt` 用完也可一并删），**保留工作目录本身**。

**脚本可能没有可执行位**（克隆/同步后丢失）。调用时用 `zsh <脚本>`，或先 `chmod +x`，否则报 `permission denied`。

**这条链路不限于菜谱。** 健身/教程类视频同样适用：OCR 抽硬字幕拿「动作名 + 组数」，ASR 交叉补漏（OCR 会整帧漏掉某个标题，ASR 能补上），再针对性抽关键帧用 Read 逐字确认，比通读整段 OCR 输出更快更准。

## 工具路由：能用官方技能就不自己写

| 步骤 | 归谁做 | 说明 |
|---|---|---|
| 1/2/3 开页 · 元信息 · 评论 · 取直链 | **官方 `agent-browser` 技能** | 先加载该技能，再动手；本文件不再自述 CLI 用法 |
| 4A/4B ASR · 抽帧 OCR | 本技能 `scripts/asr.py` `ocr.py` | 官方无对应技能 |
| 5 写 md 笔记 | 本技能内置模板 | 落 `$RECIPE_NOTE_DIR` |
| 5A B 站下载/评论 | 本技能流程 + yt-dlp | 无官方技能；其中浏览器环节仍归 `agent-browser` |
| 收尾 close | **官方 `agent-browser` 技能** | 见下条「close 放 finally」 |

**不要猜 `agent-browser` 的用法**——CLI 自带随版本对齐的文档，比本文档更新：

```bash
agent-browser skills get core --full     # 完整命令参考 + 工作流模板
```

官方技能里三条与本流程直接相关的硬约定：

1. **daemon 复用**：一个任务只在开头 `open`、结尾 `close`，中间不要反复关开（`open` 会自动连上已有 daemon，`close` 关的是整个 daemon）。所以**多条链接一次传完**给 `grab.sh`，不要一条一跑。
2. **`close` 必须放 finally**：成功或失败都要关，否则留僵尸 daemon + 泄漏的 Chromium 进程（`agent-browser close --all` 可兜底清干净）。
3. **`eval` 传 JS 优先走 stdin**：`print -r -- '<js>' | agent-browser eval --stdin`，彻底绕开抖音选择器里的嵌套引号。实测 `eval` 返回带引号 JSON（`"Example Domain"`），要原样文本可用 `get title` 这类子命令。

## 关键坑（先读）

1. **WebFetch 抓抖音必然失败**（返回"抱歉出错了"）。必须走官方 `agent-browser` 技能；未安装时按该技能文档安装（`npm install -g agent-browser && agent-browser install`）。
2. **不要盲信 ASR**。抖音菜谱视频分两类：
   - **口播型**：有真人讲解 → whisper 转写效果好。
   - **BGM+画面文字型**：无口播，做法全写在画面文字上 → whisper 会输出"秋天""春天"这类幻觉（`no_speech_prob` 偏高）。**必须先判断类型**，否则浪费大量时间。
3. **判断技巧**：直接跑 `asr.py <video> probe`——只转片头就自动判型（命中 `謝謝觀賞 訂閱 打開小鈴鐺`/`字幕by索兰娅` 这类静音幻觉、或"单段横跨整窗口且仅几个字"的幻影段形态 → 判字幕型；否则判口播型），并顺带打印建议抽帧间隔与方言告警。手写判断也可以：文本连贯且与菜名相关 → 口播型；重复无意义词 → 文字型，转抽帧读字。
4. 中文 ASR 一定要 `language="zh"`，加 `initial_prompt` 提示菜名与环节可显著提升准确率。
5. **zsh 里 `set -- $var` 不做词分割**（默认无 `SH_WORD_SPLIT`）。批量循环里写 `for p in "name 1.0"; do set -- $p; ...` 会把 `$1` 变成整串 `name 1.0`，脚本报 `ValueError: could not convert string to float: './frames_name 1.0'`。改用 `${=p}` 显式分割，或干脆把每个视频的调用写成一条独立命令 / `{ ...; }` 分组。
6. **zsh 脚本里禁止用 `path` 当普通变量名**。`$path` 是和 `$PATH` 绑定的特殊数组，`path=$(...)` 会把 PATH 覆盖成一个元素，之后 `tr`/`grep`/`sleep`/`awk` 全线报 `command not found`（写 grab.sh 时真实踩到，冒烟测试才逼出来）。要存路径就叫 `vpath`/`vurl`。同名雷区还有 `status`（只读）、`argv`、`pipestatus`。
7. **ASR 会听错克数，OCR 也会漏行**，两者都不足为凭时按帧核对。实测：烧椒豆花滑肉的 `加入盐5克` ASR 听成「盐1克」，且该行 OCR 恰好没抓到，最终靠 `-ss 183` 抽帧读定；同一视频 `红花椒` ASR 说 1 克、OCR 说 3 克，抽帧确认 3 克。**凡是克数冲突，一律抽帧 Read 定稿。**（`ocr.py check <video> 183,215` 就是干这个的）

## 标准流程

### 1. 解析短链 + 抓元信息

> 本节命令归官方 `agent-browser` 技能。**优先直接跑 `scripts/grab.sh`**（已把本节 + 第 2 节合并成一条命令，并在结束时 `close`）；下面的裸命令只在临时补抓单个字段时用。

```bash
agent-browser open "https://v.douyin.com/XXXX/"      # 自动跳转到 /video/<id>
agent-browser wait --load load
agent-browser snapshot | grep -E "heading|发布时间" -A1   # 标题、文案、发布时间
```

**一条命令抓齐元信息（推荐，比 snapshot 快且全）**：

```bash
ev() { print -r -- "$1" | agent-browser eval --stdin }   # 选择器带引号时的通用写法
ev 'document.title'                                                          # 标题+文案
ev 'document.querySelector("[data-e2e=\"user-info\"]").innerText.split("\n")[0]'  # 作者昵称
ev 'document.querySelector("[data-e2e=\"detail-video-publish-time\"]")?.innerText' # 发布时间
ev 'document.querySelector("video").duration'                                # 时长（决定抽帧策略）
```

作者昵称在 `data-e2e="user-info"` 里，`innerText` 形如 `昵称粉丝6.2万获赞487.8万关注`，取 `.split('\n')[0]` 即昵称。
用 `document.querySelector('[data-e2e="comment-list"]').innerText` 抓评论，比 snapshot 更干净。

`eval` 返回的是**带引号的 JSON 串**（如 `"Example Domain"`），用前记得剥引号。选择器里本身带 `\"` 时不要硬套外层引号，按上面的 `ev()` 走 stdin。

### 2. 评论区（高价值，别跳过）

评论区常有作者补充的关键信息，甚至**精确到克数的完整配料表**（专业厨师账号尤其明显）。这条选择器自带 `\"`，按官方技能的建议用 stdin 传 JS，别硬套外层引号：

```bash
ev '(()=>{const c=document.querySelector("[data-e2e=\"comment-list\"]");return c?c.innerText.replace(/\n+/g," | ").slice(0,2500):"none"})()'
```

标记 `作者` 的评论即为作者本人回复，优先采纳。高赞长评论常是网友整理的完整配方，可与画面字幕里的用量交叉核对后采用。

### 3. 下载视频

> 优先直接跑 `scripts/dl.sh <code>:<名>`——它已经封装了下面这整段。

```bash
# 取直链（输出带 JSON 引号）
ev 'document.querySelector("video").currentSrc' > url.txt
URL=$(sed 's/^"//; s/"$//' url.txt)
curl -sL -H "Referer: https://www.douyin.com/" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36" \
  -o video.mp4 "$URL"
file video.mp4   # 必须显示 "ISO Media, MP4"
```

**必须带 Referer + 桌面 UA**，否则只下到 ~351 字节的 HTML 错误页。（`dl.sh` 已带 `--retry` 并校验产物是真 MP4，过期直链会直接报错而不是留个假 mp4。）

### 4A. 口播型 → whisper

**先探型再转写**：`asr.py <video> probe`（只转片头，自动给"口播型 / 字幕型"结论 + 抽帧间隔 + 方言告警），别一上来就整片跑。

```python
from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe("video.mp4", language="zh", vad_filter=False,
                                  beam_size=5, initial_prompt="以下是家常菜<菜名>的制作讲解…")
for s in segments:
    print(f"[{s.start:.1f}-{s.end:.1f}] {s.text}")
```

注意：`vad_filter=True` 有时会把整段语音全滤掉、输出 0 段 → 改用 `False`。

**方言视频**：川渝方言 + 专业术语会让 `small` 模型严重跑偏（如把"醪糟"听成"老抽"、"仔姜"听成"日江"）。自贡盐帮菜/老川菜账号尤其严重，实测误识模式可作对照表：**藕丁→牛丁、锅边醋→锅边煮、三奈→三奶、仔姜→姿姜、炙锅→香脂锅、烧洗干净→烧熄干净**。这类视频直接判定为"以 OCR 字幕为准"，ASR 只当辅助。两条补救路径，**优先第二条**：
1. 换 `medium` 模型（CPU 上 100 秒视频要几分钟）；
2. **用画面字幕核对**——这类视频的字幕与口播基本同步，按 5 秒抽帧读字幕，比 ASR 可靠得多。

判断依据：ASR 出现"三玉"(鳝鱼)、"日江"(仔姜)这类同音错字时，说明方言重、要在画面字幕上确认关键用料。

**短视频（≤30 秒）建议 small + medium 各跑一遍**：短素材跑 medium 的成本极低（实测 19 秒视频两个模型加起来 29 秒），而 medium 常能直接纠正 small 的方言错字。案例：湖南口播视频 small 听成「一个两公坨」，medium 正确输出「一个两公婆」，且两个模型都听对了「辣椒灰」这类方言词。一次拿到两版转写再和 OCR 三方对照，比只跑 small 更有底。

### 4B. 文字标注型 / 字幕核对 → 抽帧 + 本地 OCR（首选方案）

**先用 OCR，不要一上来就逐帧用眼睛读图。** 一次 OCR 全片可以把 30+ 张图的工作压缩到一次命令，准确率也高于人工快速扫读。

**首选直接跑 `ocr.py`，下面的内联版本只在需要改造时参考。** 现成脚本已经是升级版：一次 ffmpeg 解码 + JPEG 管道直喂 OCR（**默认不写帧图**，省磁盘也省 IO），结果同时打印并落盘到 `subs_<名>.txt`。

```python
import subprocess, imageio_ffmpeg
from rapidocr_onnxruntime import RapidOCR
ff = imageio_ffmpeg.get_ffmpeg_exe()   # 自带静态 ffmpeg，无需装系统 ffmpeg
ocr = RapidOCR()
seen = set()
for t in range(0, duration):            # 0.5-1 秒一帧，字幕短促时务必用 0.5 秒
    p = f"ocr/{t}.jpg"
    subprocess.run([ff, "-ss", str(t), "-i", "video.mp4", "-frames:v", "1",
                    "-q:v", "2", p], capture_output=True)
    r, _ = ocr(p)
    txt = " ".join(x[1] for x in r) if r else ""
    if txt and txt not in seen:         # 去重，只打印新出现的字幕
        seen.add(txt); print(f"[{t:>4}s] {txt}")
```

**OCR 只作为骨架，仍需用 Read 工具核对关键帧**（用量、易混词），因为 OCR 会串字：
- 实测串字案例：`青红辣椒鱼 料汁：薄盐生抽一点酱油一点玉米淀粉` —— 实为"下青红辣椒、鱼" + "料汁：薄盐生抽、一点酱油、一点玉米淀粉"两行被并成一行。
- 数字和单位最容易丢：`盐 1g` 可能被读成 `盐 l9`。涉及克数时，务必 Read 原图确认。

**OCR 会把贴片/水印文字一起读进来**，要人工剥离：
- 账号贴片水印会混进每一条字幕里，例如 `真好吃！ 记川菜馆 口蘑洗净去掉脚`、`@烧给女儿的菜 土豆切小块`、`COM 有机 兰红醇香味 … 再加入豆豉`（后者是一整条广告贴片，持续几十秒）。**看到同一串无意义文字反复出现，就是贴片，直接忽略。**
- 平台安全提示也会被读入：`安全警示 小心烫伤`、`高盟接烟 小心烫伤` 等，属于 UI 覆盖层，不是菜谱内容。
- 所以**去重后仍会有大量噪声行**，需要按时间顺序人工梳理成步骤。

**当 ASR 与 OCR 冲突时（OCR 没标但 ASR 听到了某步）**：把争议时间段单独切出来、用 `medium` 模型复核，比整片跑 medium 快得多。

```python
subprocess.run([ff,"-ss","40","-t","13","-i","video.mp4","-vn","-ac","1","-ar","16000","seg.wav","-y"],capture_output=True)
m = WhisperModel("medium", device="cpu", compute_type="int8")
m.transcribe("seg.wav", language="zh", vad_filter=False, initial_prompt="……（提示这一段的关键动作）")
```
实测：某视频字幕没标"勾水淀粉"，small 听成 `用水淀粉`，把该段切出来跑 medium 后确认是 `勾水淀粉`，从而定稿。

**抽帧密度要点**（按视频类型定，不要一律 0.5 秒）：
- **有口播的视频 → 1 秒一帧足够**：字幕与语音同步且每句持续显示，1 秒能抓全。
- **纯字幕型短视频（30 秒以内）→ 0.5 秒一帧**。实测 32 秒视频用 0.5 秒抓到 6 条字幕，用 2 秒只抓到 3 条。
- **长视频（3 分钟以上）→ 可放宽到 1.5 秒**，控制总帧数。
- **精确用量几乎只出现在字幕里**（例如"碗里加入生抽45g 老抽20g 蚝油50g 胡椒粉1g"），这类帧务必抓到。
- **不要做"画面去重"来省帧**：背景一直在动，底部区域像素差始终很大，去重会把 95% 的帧都留下，没有意义。
- 单次 Bash 里用一个 Python 循环批量处理多个视频，减少往返。实测 5 个视频（144/94/234/27/19 秒）一次跑完约 3.5 分钟。

**OCR 后台运行的坑（重要）**：**不要**用 `nohup ... &` 起后台任务——Bash 工具会话结束时该进程会被静默回收（表现为输出文件为空、连帧目录都没建）。要么前台跑（给足 timeout），要么用 Bash 工具的 `run_in_background` 参数。

**方言视频的 OCR 特征**：方言视频的字幕也照样是标准书面语，OCR 抓得比 ASR 准得多（实测川渝方言视频，ASR 满篇错字，OCR 字幕条条准确）。但 OCR 会有这些噪声，需人工还原：
- 繁体/异体字：「靑花椒」→ 青花椒；「跑山鸡洗干泽了」→ 洗干净了。
- 数字误识：「有一年7」「煮好7」→ 这里的 `7` 是「了」被误识，结合上下文还原。
- 相邻两行串联：如「牛肉虾仁」+「牛肉炒虾仁」并成一行，注意可能是标题卡与字幕叠加。
- 比例/用量被拆开：`1:51:6的样子` 实为「1:5 ~ 1:6」。

**抓评论的更短路径**：短链解析后拿到的 `/video/<id>` 中的 id 可直接拼 `https://www.douyin.com/video/<id>` 打开，比每次走短链快很多。

**视频分型与对应策略**（同一账号也可能两种都有）：
| 类型 | 特征 | 策略 |
|---|---|---|
| 口播型 | 有真人讲解，ASR 文本连贯 | whisper small 起步，方言重则靠字幕核对 |
| 字幕标注型 | 无解说、有背景音乐，字幕覆盖大部分步骤 | OCR 全片 + 抽帧核对 |
| 极简字幕型 | 无口播，全片只有 2-3 条字幕 | OCR 几乎无输出 → 必须按 1 秒（甚至 0.5 秒）抽帧、用 Read 逐帧读画面动作，**并用作者在评论区的回复补全细节** |
| 纯画面型 | 无解说、无字幕 | 只能靠画面推断，笔记里**必须注明"做法来自画面推断"**，不要臆造用量 |

**评论区是本流程的"第二信息源"，不要只抓一次**：
- 作者本人回复（带 `作者` 标记）经常就是在补全步骤与用量，例如"我烫了一分钟""滚油和生抽""关火了再放牛肉""盐只有最后加"。极简字幕型视频基本靠这些回复才能写全。
- 高赞长评论常是网友整理的完整配方（含克数），可与画面字幕交叉核对后采用。
- 网友的"避雷"反馈也很值钱（如"牛肉直接下滚汤会出大量血沫、汤会浑"），适合写进笔记的「总结」。

### 5. 写 md

落盘目录：配置文件里的 `RECIPE_NOTE_DIR`（默认 `~/Documents/RecipeNotes/`）。
要把笔记写进自己的 Obsidian 库，在 `<技能目录>/config.env` 里填一行即可
（配置方法见上文「把菜谱 md 固定输出到自己的笔记库」）：

```sh
RECIPE_NOTE_DIR="/Users/you/Library/Mobile Documents/iCloud~md~obsidian/Documents/YourVault/你的食谱目录"
```

**直接用下面这套骨架**（从大量实际笔记归纳固化；不要再 Read 已有笔记来"确认模板形态"）：

```markdown
> 来源：<原始链接> （<平台> @<作者>《<标题>》，发布于 YYYY-MM-DD）

## 📦 食材

**肉类**
- 五花肉（提前烧洗干净，冻硬一点更好切）

**蔬菜类**
- 花菜 1 颗

**配菜**
- 小米辣 3 个

**其他**
- 蒜、蒜苗

**调料**
- 生抽 3 勺
- 盐（含"毛毛盐"）、鸡精

## 🔪 备菜

1. 花菜清水加盐浸泡 5 分钟，捞出切块
2. 五花肉切薄片

## 🍳 制作

1. 锅烧热加油至六成热，中火把花菜炒到 9 成熟，盛出
2. 留底油煸五花肉，煸香后下小米辣、二荆条、蒜炒香
3. 加蚝油、生抽、味精、鸡精和花菜，翻炒几下出锅

## 💡 总结

**技术总结**

1. 花菜**不能加水**，加水口感极差、不脆。
2. …（只写「为什么这么做」，不复述步骤）

> 注：（可选）用量为画面推断 / 网友补充了 XX / 方言词还原说明
```

**骨架硬规则**（别发明新格式）：

1. **不加 H1 标题**——文件名（=菜名）就是标题；正文第一行必须是 `> 来源：`。
2. **`> 来源` 行**：`> 来源：<链接> （<平台> @<作者>《<标题>》，发布于 YYYY-MM-DD）`。抖音写「抖音 @作者」，B站写「B站 @UP主」；**作者/日期拿不到时只留链接**（如 `> 来源：https://www.bilibili.com/video/BV1yf42117oX/`）；**旧笔记没来源就整行省略**，不要编 URL、不要写"来源：无"。
3. **`## 📦 食材` 用 5 个分类小标题**：`**肉类**` / `**蔬菜类**` / `**配菜**` / `**其他**` / `**调料**`，按需增减或换名（也用过 `**主料**` / `**料汁**`）；分类下用 `- 条目`，**用量能写就写**（克/勺/个），推断出来的要注明是推断。
4. **`## 🔪 备菜` / `## 🍳 制作`** 均为有序列表 `1.`，一步一行；预处理（烧洗/焯水/腌制）排在制作开头。
5. **`## 💡 总结` 下必须有 `**技术总结**` 子标题**，编号列表写**为什么**（机理、易错点、火候原理）；评论区网友的"避雷"反馈放这里。
6. 可选末尾 `> 注：` 一行，说明推断用量、网友补充、方言词还原。
7. **空行规则**：每个 `##` 标题后空一行；分类标题 `**肉类**` 与其列表之间不空行；同列表内条目之间不空行。

**落盘前先 `ls` 确认目标文件是否已存在**。两个原因：
- Write 工具对「已存在但本回合未 Read」的文件会直接报错 `File has not been read yet`，白跑一次；
- 目标文件名可能已被**早先自动流程/并发产物**占用，此时应先 Read 看清是不是同一道菜，再决定覆盖还是改名。

文件名取菜名（与已有笔记重名时，加限定词区分）。注意**别和相似菜名混为一谈**——如 `青椒豆腐.md`（老豆腐 + 瘦肉煎炒）与 `青椒烧豆腐.md`（嫩豆腐烧）是两道不同的菜，写之前扫一眼目录里已有的相近菜名。

### 5A. B 站链接适配（用户给 bilibili.com 链接时）

流程完全复用（元信息 → 下载 → ASR/OCR → 写 md），只有下载和评论两处不同：

- **视频源是 MSE blob**，`video.currentSrc` 拿不到直链。用 yt-dlp（`pip install yt-dlp`）：
  ```bash
  python3 -m yt_dlp -f "bv*[height<=720]+ba/b[height<=720]/b" -o "video.%(ext)s" "<url>"
  ```
  无系统 ffmpeg 时不会自动 merge，**不必强行合并**：音频轨 (.m4a) 直接喂 whisper（PyAV 能解 m4a），视频轨 (.mp4) 直接抽帧 OCR，两条管线天然分开。
- **章节**很有用（多数美食 UP 有"买菜/做菜/吃饭"章节），一条命令拿全：`yt_dlp --print "%(chapters)s"`，可只对做菜段落跑 OCR 省时间。
- **评论**直接走 API（无需登录、无需浏览器）：
  ```bash
  curl -s -H "User-Agent: Mozilla/5.0 ..." "https://api.bilibili.com/x/v2/reply?type=1&oid=<aid>&sort=2&ps=20&pn=1"
  ```
  aid 从页面 `window.__INITIAL_STATE__.aid` 取；UP 的 mid 在 `data.upper.mid`，用于标记 UP 本人回复。
- 元信息：`%(title)s|%(uploader)s|%(upload_date)s` 可从 yt-dlp 直接打印；标题就是 `document.title`。
- 已验证案例：BV1sw4m1m7iQ（美食强·口蘑炒鸡腿肉，254s，ASR/OCR 双通道互相印证一次成型）。

### 5B. 大批量处理（10 个以上链接）

已验证一次跑通 24 个链接（合计约 35 分钟素材）。规模化时的关键差异：

**把每一步写成脚本文件再后台跑，不要用内联 for 循环。** 理由不再是「引号地狱」——官方技能的 `eval --stdin` 已经把 JS 放进 stdin，嵌套转义问题消失；写脚本仍更稳是因为**可重跑、可后台、失败可单独重试**。直接复用 `scripts/grab.sh` / `dl.sh`。

**脚本里一次抓齐 5 件事**（`grab.sh` 的实现，带 stdin 辅助函数，不必手写）：

```zsh
# grab.sh 内部：ev() 把 JS 走 stdin，规避引号地狱
ev() { print -r -- "$1" | $AB eval --stdin }

$AB open "https://v.douyin.com/$L/"        # 自动跳 /video/<id>
$AB wait --load load
ev 'document.title'
ev 'document.querySelector("[data-e2e=\"user-info\"]").innerText.split("\n")[0]'
ev 'document.querySelector("[data-e2e=\"detail-video-publish-time\"]")?.innerText'
ev 'document.querySelector("video").duration'
ev 'window.location.pathname'                     # 拿 video id，便于后补
ev '(()=>{const c=document.querySelector("[data-e2e=\"comment-list\"]");return c?c.innerText.replace(/\n+/g," | ").slice(0,900):"none"})()'
ev 'document.querySelector("video").currentSrc' > "url_$L.txt"
$AB close                                  # 全部链接抓完再关（daemon 复用，别一条一关）
```

> 上面是**早期内联版**，现在直接跑 `grab.sh` 即可——它把这 5 件事都做了，另外多出两项：直链剥引号（dl.sh 不用再 `sed`）、元信息/全量评论/**作者回复单独成段**落盘到 `meta_<code>.txt`，并给建议抽帧间隔；`close` 也从"脚本末尾"改成 `trap`（出错/中断同样释放 daemon），单条失败只跳过。

**耗时基准（24 个视频）**：元信息抓取 ~11 分钟（每个约 27 秒，**这是整条链路的瓶颈**）→ 下载 ~2.5 分钟 → ASR（2128 秒素材，small）~15 分钟 → OCR（1834 帧）~20 分钟。**ASR 和 OCR 可以各起一个 `run_in_background` 并行跑**，总耗时≈较长的那一边。

**抽帧密度按类型批量设**（在 jobs 列表里逐条指定，别一刀切）：
```python
jobs = [("key", 时长秒, 抽帧间隔),
        ("长口播视频", 315, 1.5),   # 口播 → 1.5s
        ("中长视频",   88, 1.0),    # 30~90s → 1.0s
        ("短视频",     27, 0.5),    # <30s 或极简字幕 → 0.5s
        ]
```

**必须预留复核能力**：默认就**不落帧图**（管道直喂），只需**保留 mp4 + `subs_*.txt`**；要核实某处细节时 `ocr.py check <video> <时间点>` 抽单帧、用 Read 逐字看即可——实测一轮核对 6 处细节就是这么做的。

### 5C. 规范化已有旧笔记（用户直接给 .md 路径、要求"按模板规范"）

旧笔记（多为早期手工记录）常见形态：只有 `## 备菜` + `## 制作`，可能还有 `## 制作前准备` 这种自造小标题，且**没有 `## 📦 食材` 和 `## 💡 总结`**。规范要点：

- **没有来源链接就整行省略 `> 来源`**——不要造 URL，也不要写"来源：无"。文件名即菜名，不加 H1 标题。
- 把 `## 制作前准备`、`## 预处理` 等自造小标题**并入 `## 🍳 制作`**，按原有先后顺序排成连续编号步骤（炸制/焯水这类预处理排在制作开头）。
- **`## 📦 食材` 从步骤正文归纳**（旧笔记往往没写食材表）。
- **原步骤的文字表述尽量保留**（是用户自己的口语笔记，只做排序补全、不改写）；口语化的关键提示（如"够装下肉片即可，一定不要多"）原样保留并写进总结，再补上理由。
- `## 💡 总结` 的「技术总结」写**为什么这么做**，不要复述步骤。
- 收尾提醒：若该食谱的整理结果被其他自动化流程引用（如食谱数据汇总脚本按"人工归纳"登记），规范化后要同步把它从该名单里移出。

### 6. 收尾

`close` 这一条归官方 `agent-browser` 技能，规则是 **`close` 放 finally**：任务成功或失败都要关，否则留僵尸 daemon + 泄漏的 Chromium 进程。`grab.sh` 末尾已自带 `close`（全部链接抓完之后才关，符合 daemon 复用）；若中途手动开过浏览器，收尾用 `agent-browser close --all` 兜底。

```bash
agent-browser close --all
rm -rf <工作目录>/.tmp      # 大批量任务的 tmp 可能到 1G 以上，务必清理
```

**收尾必须放在本回合最后一次 Bash 调用里，并且要真的看到目录消失或体积归零再结束回合。** 实测踩过坑：收尾命令和交付物生成挤在一起，会话在收尾前被切断 → 残留大量中间文件。收尾后补一句 `ls -la <工作目录>` 确认。

**删除会被两道闸拦下**，遇到时不要反复重试同一条命令：
- `SAFE_DELETE_BULK_CONFIRM_REQUIRED`：**单回合删除目标超过 50 个文件即拦截**。抽帧目录（100+ 张 jpg）嵌套在任务目录里极易触发。
- 沙箱 `Operation not permitted`：沙箱内 `rm` 直接失败。
- 应对顺序：① 直接删**整个任务目录**（顶层一个目标）最省事；② 若被拦，改成**分批**（每批 ≤40 个文件），或对单条 `rm` 走一次免沙箱授权；③ 仍失败就明确告知用户"清理未完成 + 残留路径与体积"，不要假装清完。

**并发会话可能共用工作目录**：同工作区可能有别的会话/自动化在不同任务名子目录下跑。**删别人的目录前先看对应笔记是否已落盘**，确认是废弃中间产物再删；只清理自己这一轮的目录最稳妥。
