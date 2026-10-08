---
name: apple-music-library-bpm-scan
description: Scan a user's local Apple Music library export and report which tracks match a target BPM range (e.g. 180-184 BPM running cadence playlists). Use this skill when the user asks whether songs already in their Apple Music library / 资料库 / 播放列表 satisfy a BPM range, or hands over an exported library file (音乐.txt / Music Library.xml) to be filtered by tempo. Covers why the on-disk Music library cannot be read directly, the exact export-file format, the songbpm.com lookup pipeline to reuse, and the artist-name alias traps that silently yield zero matches.
agent_created: true
---

# Apple Music Library BPM Scan

Filter a user's own Apple Music library down to the tracks that match a target BPM
range. Typical shape: "看看我的音乐资料库里还有没有满足 180–184 BPM 的歌".

The pipeline is **generic and stateless**: it ships with no library data, no cached
lookups and no artist history. Every run rebuilds from the user's own export file.

## 目录约定：脚本随技能，数据随项目

| 用途 | 位置 | 说明 |
|---|---|---|
| **脚本** | `<技能目录>/scripts/` | 由脚本自身位置自解析，技能装到哪都自洽，不硬编码 |
| **数据** | `<当前项目>/.apple-music-bpm-scan/work/` | 候选清单、BPM 库、请求缓存、中间 JSON |
| **交付物** | `<当前项目>/.apple-music-bpm-scan/out/` | 最终 `180-184bpm-scan.html` / `.txt` 报告 |

规则实现在 `scripts/_dirs.py`。**两种目录都跟着当前工作目录 / 当前项目走**，
所以「在哪个项目里跑，数据就落在哪个项目里」，不污染技能安装目录，
也绝不写进其他项目或其他 agent 的工作目录。

解析顺序（命中即止）：

1. `$AMBS_WORK_DIR` / `$AMBS_OUT_DIR` 显式指定
2. `<技能目录>/config.env` 里的同名键
3. **当前项目根** `/.apple-music-bpm-scan/` —— 「项目根」= 从 `$PWD` 逐级向上第一个含 `.git` / `AGENTS.md` / `package.json` / `pyproject.toml` 的目录
4. 无项目标记但当前目录安全 → `$PWD/.apple-music-bpm-scan/`
5. 当前目录不安全（`/`、`$HOME` 根、`/tmp`、`$TMPDIR`、`~/.dsh` 等其他 agent 的家目录、或技能目录内部）→ 退回 `<技能目录>/work/` 与 `<技能目录>/out/`

第 5 条是关键护栏：**在别人的仓库、其他 agent 的工作目录或 `/tmp` 里运行，
数据退回到技能自己目录，绝不外溢。**

排查当前解析到哪：

```bash
python3 <技能目录>/scripts/_dirs.py
```

它打印 skill / script / config / cwd / root / work / out，一眼就能定位。

### 需要钉死目录时（可选）

想让报告固定落到某个目录（例如自己的笔记库），在**技能目录内**建 `config.env`：

```bash
cp <技能目录>/config.example.env <技能目录>/config.env
```

```sh
AMBS_OUT_DIR="~/Documents/BPM扫描"
# AMBS_WORK_DIR="~/bpmdata/work"      # 一般不用填
# AMBS_BPM_RANGE="180-184"            # 换步频目标改这里
# AMBS_EXPORT="~/Downloads/音乐.txt"  # 曲库导出文件位置
```

这是 shell 的 `KEY=VALUE` 语法，Python 脚本直接读（**不执行 shell**，只有 `~` 与
`$HOME` 会被识别）。`config.env` 是私有配置，技能自带的 `.gitignore` 已忽略它，
**不要提交、不要外发**；随技能分发的是 `config.example.env` 模板。

优先级：**命令行环境变量 > config.env > 自动解析**。临时改一次直接内联覆盖即可：

```bash
AMBS_OUT_DIR=/tmp/out python3 <技能目录>/scripts/render_lib.py
```

## Dependencies (opencc)

`opencc` 用于繁→简归一化；缺了它 `綠光` 与 `绿光` 相似度只有 0.5，会被阈值滤掉。
它已**内置**在 `scripts/_pylibs/`，由 `scripts/_boot.py` 自动加载（每个用到 opencc
的脚本都会先 `import _boot`）。所以裸 `python3` 即可，**不要**设 `PYTHONPATH`、
也不要指向任何外部 venv。

验证（任选其一，都应打印 `ok`）：

```bash
python3 -c "import sys; sys.path.insert(0,'<技能目录>/scripts'); import _boot, opencc; print('ok')"
cd <技能目录>/scripts && python3 -c "import _boot, opencc; print('ok')"
```

若失败，重装到内置目录：

```bash
python3 -m pip install --target <技能目录>/scripts/_pylibs opencc-python-reimplemented
```

其余依赖只用标准库。

## Step 0: get the export file

**This is the only viable route — the on-disk library cannot be read directly.**

Music → 文件 → 资料库 → 导出… (File → Library → Export…). It lands as a text file,
conventionally `~/Downloads/音乐.txt`. That file is **not** a permanent fixture — it only
exists after the user exports. Check it first:

```bash
ls -la ~/Downloads/音乐.txt
```

If absent, stop and ask the user to export; do not try to script the Music app.

脚本按这个顺序自动找导出文件：显式 CLI 参数 → `$AMBS_EXPORT` → 当前目录 →
`work/` → `~/Downloads`，匹配
`音乐.txt` / `Music Library.txt` / `音乐 .txt` / `Music Library.xml` / `音乐.xml`。
都找不到就带可操作提示退出。要明确指定：

```bash
python3 <技能目录>/scripts/lib_fetch.py /path/to/音乐.txt
```

### Dead ends — do NOT spend time on these

| Route | Result |
|---|---|
| `~/Music/Music/Music Library.musiclibrary/Library.musicdb` | Apple-proprietary **encrypted** container. Magic `hfma`, entropy ≈ 7.997, no `SQLite format 3` / `ZTRACK` / even a `name` byte sequence. Embedded zlib streams do not decompress. |
| AppleScript `tell application "Music" to get ...` | Fails with `-10004 权限违例`. A sandboxed agent shell has no `appleevent-send`, so TCC never prompts. (`tell application "Music" to get name` succeeds because it triggers no real event — it is not evidence that scripting works.) |
| `…/com.apple.MusicKit/downloaded_catalog_data/MusicCatalogData.db` | SQLite, but only catalog cache (`catalog_song`, usually 0 rows). No user library. |
| `~/Music/Music/Previous Libraries.localized/*.musiclibrary` | Same `hfma` container. |

## Export file format (verified)

- **UTF-16LE with BOM, CR line terminators, tab-separated, 31 columns, header row first.**
- **There is no BPM column** — every track must be looked up externally.
- Columns used: `0 名称 / 1 艺人 / 3 专辑 / 6 流派 / 9 类型 / 11 时长(秒) / 16 年份`.
  Column positions can shift slightly between macOS versions; unreadable columns
  degrade to empty strings rather than raising.
- Decoding is handled by `_common.load_lib()`; if you parse it yourself, note that
  the file is UTF-16 and CR-terminated:

  ```python
  txt = open(path, 'rb').read().decode('utf-16')
  txt = txt.replace('\r\n', '\n').replace('\r', '\n')
  ```

  Splitting on `\n` alone yields one giant line otherwise.

## Script layout — which file does what

| 文件 | 角色 | 说明 |
|---|---|---|
| `fetch_bpm.py` | **抓取入口（可执行）** | 候选筛选 + 合并进 `bpm_all.csv`；`--force` / `--all` |
| `songbpm.py` | **抓取内核（库）** | 查询 / 解析 / 匹配 / 别名判定；**无 `main()`，不能直接跑** |
| `lib_fetch.py` | 入口 | 从导出文件挑出待抓候选 → `work/cand_lib.txt` |
| `lib_scan.py` | 入口 | 用本地 BPM 库分桶判定，写 `work/lib_recs.json` |
| `lib_report.py` | 入口 | 完整报告 + 在线补抓，写 `work/lib_result.json` |
| `render_lib.py` | 入口 | 渲染交付物 HTML / TXT |
| `probe.py` | 工具 | 人工核查：打印某查询的全部 songbpm 结果 |
| `refetch.py` | 工具 | 清理 `NO_MATCH` 占位行，让别名修正生效 |
| `_aliases.py` | 数据 | 通用艺人别名表（`ALIAS` / `QUERY_ALIAS`） |
| `_dirs.py` | 基础设施 | work / out 目录解析与安全护栏 |
| `_common.py` | 基础设施 | 导出解析、归一化、CSV 读写 |
| `_boot.py` | 基础设施 | 自举内置 `_pylibs/` 里的 opencc |

## Workflow

All scripts anchor to their own location, so **they can be called from anywhere** —
the data directory follows the current working directory. Run them with absolute
paths or `cd` into the project you want the data to land in.

```bash
SK=<技能目录>/scripts
```

1. **Generate the pending list**
   ```bash
   python3 $SK/lib_fetch.py [导出文件]
   ```
   Writes `work/cand_lib.txt` as `歌名|歌手` lines, skipping tracks already present in
   `work/bpm_all.csv`. It strips `(...)` / `[...]` suffixes such as `(Live)`、
   `(电影…插曲)`、`[第5期 ver.]` so the lookup query is clean, and takes the first artist
   only when the field contains `&` / `feat.` / `、` (`伍佰 & China Blue` → `伍佰`).

2. **Fetch BPM** — `fetch_bpm.py` is the **only entry point**
   ```bash
   python3 $SK/fetch_bpm.py            # 默认读 work/cand_lib.txt
   python3 $SK/fetch_bpm.py 候选.txt   # 或显式指定
   python3 $SK/fetch_bpm.py --force    # 忽略「已抓过」，候选全部重跑（仍走缓存）
   python3 $SK/fetch_bpm.py --all      # 连库内已有曲目一起整体重抓（别名大改后用）
   ```
   6 threads; roughly 45 s for 70 tracks, ~21 min for 950. Merges new rows into
   `work/bpm_all.csv`. Zero-result tracks get a `NO_MATCH` placeholder row so they are
   not retried forever. Re-run this as many times as you like — it is incremental.

   The scraper itself lives in `scripts/songbpm.py`, a **library with no `main()`**.
   It is imported by `fetch_bpm.py`, `lib_report.py` and `probe.py`; running it
   directly just points you at `fetch_bpm.py`. The split is deliberate: the fetch
   kernels (query / parse / match / aliases) are reusable, while candidate selection
   and CSV merging belong to the entry point.

3. **Classify**
   ```bash
   python3 $SK/lib_scan.py [导出文件]
   ```
   Joins each library track back to its BPM rows (exact match → cleaned-title match →
   title-only fallback) and buckets:
   - **A** single target-range hit with no half-tempo sibling → true fast track, direct cadence
   - **B** target-range hit *and* a half-tempo sibling for the same recording → half-speed base
   - **C** only the half-tempo value → double-step (the practical majority)
   - **X** everything else, for an out-of-range appendix

   Writes `work/lib_recs.json`. Half-tempo values are derived so that `2 × half` always
   lands inside the target range.

4. **Full report**
   ```bash
   python3 $SK/lib_report.py [导出文件]   # 写 work/lib_result.json，并补抓缺的 BPM
   python3 $SK/render_lib.py             # 出 out/180-184bpm-scan.html + .txt
   ```
   `lib_report.py` tops up missing BPMs online (reusing the shared cache, never
   rewriting `bpm_all.csv`). `render_lib.py` reads `lib_result.json` and writes both
   deliverables. The HTML template contains CSS `%`, so `render_lib.py` uses
   placeholder `.replace()`, **never** `%`-formatting.

### Changing the target range

The whole pipeline keys off one setting. Default is `180-184` (half-tempo `90-92`):

```bash
AMBS_BPM_RANGE=175-179 python3 $SK/lib_report.py
AMBS_BPM_RANGE=175-179 python3 $SK/render_lib.py   # → out/175-179bpm-scan.html
```

Output filenames follow the range automatically.

### Optional: marking earlier deliveries

If you have already given the user a list of tracks, record them in
`work/delivered.txt` as `歌名|歌手` (one per line). The report then labels those
tracks `已交付` instead of `新`, so repeat runs highlight only genuinely new finds.
This file is optional and **never ships with the skill**; nothing is hardcoded.

## Alias traps that produce silent zero matches

`artist_match()` only consults `_ALIAS_NORM.get(q_artist)`, so an artist missing from the
alias table yields `no match` and looks like the track is not in songbpm. Extend
`scripts/_aliases.py` before concluding anything:

- 迪克牛仔 = **`Dick and Cowboy`** (not `Dick Cowboy`)
- 杨乃文 = **`Naiwen Yang`** (not `Faith Yang`)
- 大张伟 = **`Wowkie Da`** (not `Wowkie Zhang`)
- 李贞贤 = **`이정현`** — Japanese/Korean artists are indexed under native script
- 大黒摩季 = `Maki Ohguro`; 五条人 = `Wutiaoren`; 麻园诗人 = `Mayuan Poet`

Also expect `NO_MATCH` placeholder rows in `bpm_all.csv`: the incremental fetcher skips
them forever. After fixing an alias, delete those rows and re-run the fetcher, or the
fix will never take effect:

```bash
python3 $SK/refetch.py                 # 先看哪些艺人有占位行
python3 $SK/refetch.py 迪克牛仔 杨乃文   # 删掉这些艺人的占位行
python3 $SK/fetch_bpm.py              # 再抓一次
```

## Verification and reporting discipline

- Use a raw probe that prints **all 5** songbpm results for a query before declaring a
  miss (`python3 $SK/probe.py "艺人 歌名"`). songbpm returns at most 5 results per
  search, so read all of them. Confirm the hit artist is the original performer, not a
  cover.
- When only a **Live / remix** recording carries the matching BPM, say so explicitly and
  tell the user it does not validate their studio-album track — a 4:26 Live and a 4:36
  studio take are different recordings.
- Report already-delivered tracks separately from new finds; users re-export after adding
  songs, so overlap with earlier lists is normal.
- Expect a very low hit rate: a 140-track personal library yielded 5 matches. State the
  count of tracks that had no BPM data at all rather than silently dropping them.
- Deliver a plain-text copy alongside the HTML card: the user hand-copies titles into
  Apple Music. **Never automate adding songs** — no UI automation, no AppleScript.

See `references/songbpm-pipeline.md` for the underlying scraper details, caching scheme,
and known songbpm limitations.
