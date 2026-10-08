#!/bin/zsh
# recipe-maker / _dirs.sh —— 统一的目录解析（分发版：正文与脚本内都不出现个人路径）
#
# 用法：在脚本里 **source** 本文件（不要直接执行）：
#     source "${0:A:h}/_dirs.sh"
#
# 暴露的变量：
#   RM_SKILL_DIR   本技能根目录（由本文件位置自解析，不硬编码）
#   RM_SCRIPT_DIR  = $RM_SKILL_DIR/scripts（脚本唯一正本）
#   RM_WORK_DIR    中间数据目录（mp4 / 直链 / 元信息 / 字幕 / 抽帧）
#   RM_NOTE_DIR    菜谱 md 落盘目录
#   RM_CONFIG      本次生效的配置文件路径（不存在时也打印路径，便于排查）
#
# ── 两种目录，按用途分开 ────────────────────────────────────────────────
#   脚本：永远随技能自身目录（RM_SCRIPT_DIR），复制/安装到哪都自洽。
#   数据：跟着「当前项目」走，不污染技能安装目录，也绝不写进别的技能/项目。
#
# ── 永久配置：把路径写进配置文件（推荐，不用每次 export）────────────────
#   配置文件位置（依次尝试，命中即止）：
#     ① $RECIPE_MAKER_CONFIG    显式指定别处的配置文件
#     ② <技能目录>/config.env   默认位置，与技能放一起
#
#   文件用 shell 语法，zsh 与 python 两侧都读它：
#       RECIPE_NOTE_DIR="/path/to/your/vault/your-recipes"
#       RECIPE_WORK_DIR="/path/to/work"      # 可选，一般不填
#
#   优先级：命令行环境变量 > 配置文件 > 自动解析。临时改一次只需内联即可覆盖。
#
# ⚠️ 不要写 ~/.zshrc：本技能脚本是非交互调用，zsh 只读 ~/.zshenv，从不读 .zshrc；
#    而且 python 脚本由 bash 直接启动，根本看不到 .zshrc 的导出。写在那里会静默失效。
#
# 硬约定：不写 /tmp、不写 $HOME 根、不写其他技能或项目的目录。

typeset -g RM_SCRIPT_DIR="${0:A:h}"
typeset -g RM_SKILL_DIR="${RM_SCRIPT_DIR:h}"

# ── 配置文件 ──────────────────────────────────────────────────────────
rm_config_path() {
  [[ -n "${RECIPE_MAKER_CONFIG:-}" ]] && { print -r -- "$RECIPE_MAKER_CONFIG"; return }
  print -r -- "$RM_SKILL_DIR/config.env"
}

typeset -g RM_CONFIG="$(rm_config_path)"

# 先把「命令行环境变量」暂存，source 之后再恢复 —— 保证 env > 配置文件的优先级
_rm_env_note="${RECIPE_NOTE_DIR:-}"
_rm_env_work="${RECIPE_WORK_DIR:-}"
_rm_env_out="${OUT:-}"
if [[ -f "$RM_CONFIG" ]]; then
  source "$RM_CONFIG"
fi
[[ -n "$_rm_env_note" ]] && RECIPE_NOTE_DIR="$_rm_env_note"
[[ -n "$_rm_env_work" ]] && RECIPE_WORK_DIR="$_rm_env_work"
[[ -n "$_rm_env_out"  ]] && OUT="$_rm_env_out"
unset _rm_env_note _rm_env_work _rm_env_out

# 归一化：引号里的 ~ 不会被 zsh 展开，这里手动展开，才能和 _dirs.py 的结果一致
rm_norm_tilde() {
  local name="$1" val="${(P)1}"
  [[ -z "$val" ]] && return
  [[ "$val" == "~"* ]] && typeset -g "$name=${HOME}${val#\~}"
}
rm_norm_tilde RECIPE_NOTE_DIR
rm_norm_tilde RECIPE_WORK_DIR
rm_norm_tilde OUT

# 从给定目录向上找项目根；找到打印路径并返回 0，否则返回 1
rm_project_root() {
  local d="${1:A}" m
  while :; do
    for m in .git AGENTS.md package.json pyproject.toml; do
      [[ -e "$d/$m" ]] && { print -r -- "$d"; return 0 }
    done
    [[ "$d" == "/" ]] && return 1
    d="${d:h}"
  done
}

# cwd 是否属于「不该落数据」的位置（根目录、家目录、临时目录）
rm_unsafe_pwd() {
  local d="${1:A}" t
  [[ "$d" == "/" || "$d" == "${HOME:A}" ]] && return 0
  for t in /tmp /private/tmp "${TMPDIR:-}"; do
    [[ -z "$t" ]] && continue
    t="${t:A}"
    [[ "$d" == "$t" || "$d" == "$t"/* ]] && return 0
  done
  return 1
}

rm_resolve_work() {
  local root
  [[ -n "${RECIPE_WORK_DIR:-}" ]] && { print -r -- "${RECIPE_WORK_DIR:A}"; return }
  [[ -n "${OUT:-}" ]] && { print -r -- "${OUT:A}"; return }
  if root="$(rm_project_root "$PWD")"; then print -r -- "$root/.recipe-maker/work"; return; fi
  if rm_unsafe_pwd "$PWD"; then print -r -- "$RM_SKILL_DIR/work"; return; fi
  print -r -- "${PWD:A}/.recipe-maker/work"
}

typeset -g RM_WORK_DIR="$(rm_resolve_work)"
typeset -g RM_NOTE_DIR="${RECIPE_NOTE_DIR:-$HOME/Documents/RecipeNotes}"

rm_ensure_dirs() { mkdir -p "$RM_WORK_DIR" "$RM_NOTE_DIR" }

# 排查用：zsh -c 'source scripts/_dirs.sh; rm_show_dirs'
rm_show_dirs() {
  print -r -- "skill  : $RM_SKILL_DIR"
  print -r -- "script : $RM_SCRIPT_DIR"
  if [[ -f "$RM_CONFIG" ]]; then
    print -r -- "config : $RM_CONFIG (已加载)"
  else
    print -r -- "config : $RM_CONFIG (未创建，用默认值)"
  fi
  print -r -- "work   : $RM_WORK_DIR"
  print -r -- "note   : $RM_NOTE_DIR"
}
