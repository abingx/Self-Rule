# work/ —— 中间数据目录（回退位置）

本目录**只放中间数据，不放脚本**。脚本的唯一正本在 `../scripts/`。

## 什么时候会用到这里

正常跑任务时，中间产物落在**当前项目**下的 `.recipe-maker/work/`（这样不会污染技能安装目录）。
只有下面两种情况才会回退到本目录：

- 当前目录**没有项目标记**（`.git` / `AGENTS.md` / `package.json` / `pyproject.toml`），
  且不在任何项目的子目录里；
- 当前目录本身是 `/`、`$HOME` 或临时目录（`/tmp`、`$TMPDIR`）——这些位置明确不该落数据。

也就是说：在别人的仓库、其他 agent 的工作目录或 `/tmp` 里运行，数据都会退到这里，
**绝不会写进别人的项目**。完整规则见 `../scripts/_dirs.sh` 与 `../scripts/_dirs.py`。

## 产物清单

| 文件 | 来源 | 说明 |
|---|---|---|
| `url_<code>.txt` | `grab.sh` | 视频直链（已剥 JSON 引号），`dl.sh` 直接读 |
| `meta_<code>.txt` | `grab.sh` | 元信息 + 全量评论 + 作者回复 |
| `grab_fail.log` | `grab.sh` | 失败/跳过记录，0 字节表示全部成功 |
| `<名>.mp4` | `dl.sh` | 下载的视频 |
| `subs_<名>.txt` | `ocr.py` | 去重后的画面字幕 |
| `chk/` | `ocr.py check` | 抽出的单帧，供逐字核对用量 |

## 覆盖目录

推荐写**配置文件**（zsh 与 python 读同一个文件，不用每次 export）：

```sh
# <技能目录>/config.env
RECIPE_NOTE_DIR="/path/to/your/vault/your-recipes"   # 菜谱 md 落盘目录
RECIPE_WORK_DIR="/path/to/work"                      # 可选，一般不填
```

优先级：**命令行环境变量 > 配置文件 > 自动解析**。临时改一次内联即可：

```zsh
RECIPE_WORK_DIR=/data/recipes zsh scripts/grab.sh <code>
```

**不要写进 `~/.zshrc`**：脚本是非交互调用，zsh 只读 `~/.zshenv` 从不读 `.zshrc`，
而 python 脚本由 bash 直接启动也看不到它——写在那里会静默失效。
（写 `~/.zshenv` 也只有 zsh 侧生效，python 侧仍不一致，所以一律推荐配置文件。）

排查当前解析结果（两行的 `work` / `note` 必须一致）：

```zsh
zsh -c 'source scripts/_dirs.sh; rm_show_dirs'
python3 scripts/_dirs.py
```

## 收尾

任务结束**只删媒体与中间文件**（`*.mp4`、`frames_*/`、`url_*.txt`；`meta_*.txt`、`subs_*.txt` 用完也可删），
保留目录本身。
