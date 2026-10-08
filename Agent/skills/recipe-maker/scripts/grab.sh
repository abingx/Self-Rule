#!/bin/zsh
# recipe-maker / grab.sh —— 抖音短链：抓元信息 + 评论 + 视频直链
#
# 用法:  zsh grab.sh <短链code1> [<短链code2> ...]
# 例:    zsh grab.sh eQB1VEI1Tlo 4OKp_vWSck8
#
# 产物（默认落在「当前项目/.recipe-maker/work」，见 _dirs.sh）:
#   url_<code>.txt    视频直链（已剥 JSON 引号，dl.sh 直接吃）
#   meta_<code>.txt   元信息 + 全量评论 + 作者回复（写 md 的「> 来源」行直接抄）
#   grab_fail.log     失败/跳过记录（0 字节 = 全部成功）
#
# 目录约定: 脚本随技能自身目录；数据随当前项目。可用 RECIPE_WORK_DIR / OUT 覆盖。
#
# 约定（浏览器环节归官方 agent-browser 技能）:
#   - eval 走 stdin（ev()），规避抖音选择器里的嵌套引号
#   - daemon 复用：多条链接一次传完；close 放 trap，异常/中断也会释放
#   - 单条失败只跳过，不中断整批
source "${0:A:h}/_dirs.sh"
AB=${AB:-$(command -v agent-browser)}
if [[ -z "$AB" ]]; then
  print -r -- "找不到 agent-browser，请先安装（见官方 agent-browser 技能），或用 AB=<路径> 指定。" >&2
  exit 2
fi
OUT="$RM_WORK_DIR"
PY=${PY:-$(command -v python3 || print -r -- /usr/bin/python3)}
mkdir -p "$OUT"
LOG="$OUT/grab_fail.log"; : > "$LOG"

ev() { print -r -- "$1" | $AB eval --stdin 2>/dev/null }

# eval 返回带引号的 JSON 串 -> 解出原样文本；undefined/null -> 空串
jx() {
  print -r -- "$(ev "$1")" | "$PY" -c '
import json, sys
s = sys.stdin.read().strip()
if s in ("", "undefined", "null"):
    print(""); raise SystemExit
try:
    print(json.loads(s))
except Exception:
    print(s.strip("\""))' 2>/dev/null
}

# close 放 finally：正常、出错、Ctrl-C 都要释放 daemon（否则留僵尸 + 泄漏 Chromium）
cleanup() { $AB close >/dev/null 2>&1 }
trap cleanup EXIT INT TERM

# 轮询等 video 元素就位（替代固定 sleep：快、且不会在慢网下抓空）
wait_video() {
  local i
  for i in {1..24}; do
    [[ "$(ev '!!document.querySelector("video")')" == "true" ]] && return 0
    sleep 0.5
  done
  return 1
}

# 按时长给抽帧间隔建议（对齐 SKILL.md 的表格）
step_hint() {
  awk -v d="$1" 'BEGIN{
    if (d == "" || d + 0 <= 0) print "1.0"
    else if (d + 0 <= 30)     print "0.5"
    else if (d + 0 <= 180)    print "1.0"
    else                      print "1.5"
  }'
}

for L in "$@"; do
  print -r -- "=============== $L ==============="
  META="$OUT/meta_$L.txt"
  if ! $AB open "https://v.douyin.com/$L/" >/dev/null 2>&1; then
    print -r -- "  !! open 失败，跳过" | tee -a "$LOG"; continue
  fi
  $AB wait --load load >/dev/null 2>&1
  if ! wait_video; then
    print -r -- "  !! 未出现 video 元素（链接失效 / 需登录？），跳过" | tee -a "$LOG"; continue
  fi

  title=$(jx 'document.title')
  author=$(jx 'document.querySelector("[data-e2e=\"user-info\"]")?.innerText.split("\n")[0]')
  publish=$(jx 'document.querySelector("[data-e2e=\"detail-video-publish-time\"]")?.innerText')
  dur=$(jx 'document.querySelector("video").duration')
  vpath=$(jx 'window.location.pathname')      # 别叫 path：zsh 的 $path 与 $PATH 绑定，赋值会毁掉命令查找
  src=$(jx 'document.querySelector("video").currentSrc')
  comments=$(jx '(()=>{const c=document.querySelector("[data-e2e=\"comment-list\"]");return c?c.innerText.replace(/\n+/g," | ").slice(0,6000):""})()')
  acmts=$(print -r -- "$comments" | tr '|' '\n' | grep '作者' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | head -30)
  acmt_n=$(print -r -- "$acmts" | grep -c .)
  step=$(step_hint "$dur")

  {
    print -r -- "code=$L"
    print -r -- "title=$title"
    print -r -- "author=$author"
    print -r -- "publish=$publish"
    print -r -- "duration=$dur"
    print -r -- "path=$vpath"
    print -r -- "share_url=https://www.douyin.com$vpath"
    print -r -- "suggest_frame_step=$step"
    print -r -- "src_len=${#src}"
    print -r -- "--- comments ---"
    print -r -- "$comments"
    print -r -- "--- author_comments ---"
    print -r -- "$acmts"
  } > "$META"

  if [[ -n "$src" ]]; then
    print -r -- "$src" > "$OUT/url_$L.txt"
    print -r -- "  src      : OK -> url_$L.txt"
  else
    : > "$OUT/url_$L.txt"
    print -r -- "  !! 直链为空（视频可能已删除 / 需登录 / 直播回放）" | tee -a "$LOG"
  fi

  print -r -- "  title    : $title"
  print -r -- "  author   : $author"
  print -r -- "  publish  : $publish"
  print -r -- "  duration : ${dur}s  (建议抽帧间隔 ${step}s)"
  print -r -- "  path     : $vpath"
  print -r -- "  comments : ${#comments} 字符，作者回复 $acmt_n 条（见 meta_$L.txt）"
done

if [[ -s "$LOG" ]]; then
  print -r -- ""
  print -r -- "== 有失败项，详见 $LOG =="
  cat "$LOG"
fi
