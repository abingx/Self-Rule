# songbpm.com 查询流水线参考

本文档记录 `songbpm.com` 抓取器的实现细节、缓存机制与硬限制，供重建或调试
BPM 查询能力时参考。实现落在 `scripts/songbpm.py`（内核库），入口是
`scripts/fetch_bpm.py`。

## 网络层

- 端点：`POST https://songbpm.com/searches`，表单字段 `query`。
- 必需请求头：`User-Agent`（桌面 Chrome）、`Origin: https://songbpm.com`、
  `Referer: https://songbpm.com/`、`Content-Type: application/x-www-form-urlencoded`。
- 成功判据：响应体包含 `BPM results for`，否则视为失败并重试。
- 重试：最多 4 次，间隔 `1.5 + attempt * 1.5` 秒。
- 缓存：以 `md5(query)[:16].html` 落盘到 `work/bpm_cache/`，文件 >1KB 即复用，
  不产生新请求。文件名只留哈希、不含原始查询串。缓存只影响速度，删掉后重跑
  会重新联网抓取；不影响正确性。

## 并发与吞吐

- **6 线程最稳**（`songbpm.WORKERS`）。8 线程会被限流，约 15% 请求超时。
- 实测：953 首约 21 分钟、0 报错；70 首约 45 秒。

## 解析规则

- 结果块：`<a class="hover:bg-foreground/5…" href="/@…">` 包裹的卡片。
- 每张卡片取两个 `<p>`：`ps[0]` = artist，`ps[1]` = title。
- BPM 与时长分别由 `>BPM</span><span>(\d+)</span>`、`>Duration</span><span>([\d:]+)</span>` 提取。
- 版本标记正则命中 `Live / Remastered / Acoustic / Demo / Remix / Instrumental /
  Karaoke / 伴奏 / 現場 / 现场 / 版`，命中则记为「非录音室版本」。

## 匹配规则（关键）

1. **查询顺序必须是「艺人 空格 歌名」**。反过来写命中率极低，且会大量匹配到翻唱。
2. 相似度：`difflib.SequenceMatcher` 对归一化后的歌名，阈值 0.5 才纳入候选。
3. 归一化：`opencc` 繁→简 + `unicodedata.normalize('NFKC')` + 去空白与标点。
   **不做繁简转换时 `綠光` 与 `绿光` 相似度仅 0.5，会被阈值滤掉。**
4. 原唱判定 `artist_match()`：先做子串双向包含，再查 `_aliases.ALIAS`。
   ⚠️ 只能查 `q_artist` 这一项。曾误写成遍历整个别名表，导致
   郁可唯→Hebe Tien、江语晨→Tanya Chua 这类跨歌手误配被判为原唱。
5. 中文名查不到时，用 `_aliases.QUERY_ALIAS` 里的英文/罗马音名重查。华语艺人几乎
   全部按英文名建库，不加别名会整批 `no match`。
6. 繁体补查：同一查询会再用 `opencc` 转成繁体试一次（`to_traditional`），
   因为库内歌名常以繁体收录（《雙截棍》）。

## songbpm 的硬限制（决定打法）

- 每次搜索**只返回 5 条结果**。
- **不支持按 BPM 浏览**：`/bpm/180`、`/tempo/180`、`bpm:180` 均无效。
- 只能逐曲「艺人 歌名」查询 → 想扩大产出只能扩候选池。
- 部分艺人库里根本没有（0 结果），这是真缺失，不是别名问题。
- 存在条目重复（同一首歌两个 slug），分析时按 slug 去重。
- 同一录音常同时收录 `y` 与 `2y` 两个条目，因此单拍命中要再分「真快拍 / 半速底」
  两类 —— 这正是 `lib_scan.py` 的 A / B 桶与 `lib_report.py` 分级逻辑的来源。

## 增量抓取的两个陷阱

1. 「0 结果候选不落行」会导致后续每轮无休止重抓。
   必须先写一行 `slug=NO_MATCH` 的占位记录表示「已查无匹配」。
2. 占位行一旦写入就**永久跳过**。别名表更新后必须显式删掉这些行再重抓，
   否则修正永远不生效：

   ```bash
   python3 refetch.py            # 列出有占位行的艺人
   python3 refetch.py <艺人…>     # 删除，然后重跑 fetch_bpm.py
   ```

## 已交付集合的排除逻辑

可选文件 `work/delivered.txt`（`歌名|歌手` 每行一条），由 `lib_report.py` 读取：

- 歌手名必须**子串双向匹配**，不能要求完全相等，否则漏掉
  「痛仰」vs「痛仰乐队」这类差异。
- 该文件**不随技能分发**，缺失时报告照常生成，只是不标注「已交付」。

## 目录与缓存位置

所有运行时数据都在 `_dirs.work_dir()` 下（默认 `<项目根>/.apple-music-bpm-scan/work/`）：

| 文件 / 目录 | 内容 |
|---|---|
| `bpm_all.csv` | BPM 库，增量累积；`NO_MATCH` 行代表「查过、无结果」 |
| `bpm_cache/` | 原始响应缓存，纯提速用，可安全删除 |
| `cand_lib.txt` | 由 `lib_fetch.py` 生成的待抓候选 |
| `lib_recs.json` | `lib_scan.py` 的中间结果 |
| `lib_result.json` | `lib_report.py` 的中间结果，供 `render_lib.py` 渲染 |
| `delivered.txt` | 可选，此前已交付曲目 |

交付物（HTML / TXT）写在 `_dirs.out_dir()` 下。查看实际路径：
`python3 scripts/_dirs.py`。
