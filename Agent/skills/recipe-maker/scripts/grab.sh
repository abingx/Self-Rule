#!/bin/zsh
# recipe-maker / grab.sh —— 抖音短链：抓元信息 + 评论 + 视频直链
#
# 用法:  zsh grab.sh <短链code1> [<短链code2> ...]
# 例:    zsh grab.sh eQB1VEI1Tlo 4OKp_vWSck8
#
# 产物（默认落在「当前项目/.recipe-maker/work」，见 _dirs.sh）:
#   url_<code>.txt    视频直链（已剥 JSON 引号，dl.sh 直接吃）
#   durl_<code>.txt   （仅 blob 回落时）DASH 视频轨直链
#   aurl_<code>.txt   （仅 blob 回落时）DASH 音频轨直链
#   meta_<code>.txt   元信息 + 全量评论 + 作者回复（写 md 的「> 来源」行直接抄）
#   grab_fail.log     失败/跳过记录（0 字节 = 全部成功）
#
# 目录约定: 脚本随技能自身目录；数据随当前项目。可用 RECIPE_WORK_DIR / OUT 覆盖。
#
# 约定（浏览器环节归官方 agent-browser 技能）:
#   - eval 走 stdin（ev()），规避抖音选择器里的嵌套引号
#   - daemon 复用：多条链接一次传完；close 放 trap，异常/中断也会释放
#   - 单条失败只跳过，不中断整批
#
# MSE/blob 回落（2026-10 起新版抖音 Web 实测）:
#   新版播放走 MSE，video.currentSrc 返回 blob:https://www.douyin.com/...，
#   直链是废的（curl 拿到 HTML）。此时本脚本自动从页面 performance entries
#   过滤 douyinvod，分别取一条 avc1（视频轨）与一条 mp4a（音频轨）真直链，
#   写 durl_/aurl_<code>.txt（url_ 置空），交给 dl.sh 下载后 ffmpeg -c copy 合并。
#   无需 cookie、无需签名；直链带时效，请立即跑 dl.sh。
#   ⚠️ performance 只记录已发生的请求：页面刚打开、视频未播放时一条都没有。
#      所以首次为空会自动 video.play()（静音）并轮询重试，最多等 ~5 秒。
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

# MSE 回落：从页面 performance entries 里取 DASH 双轨真直链（抖音新版 Web）
# 打印两行（视频轨 / 音频轨），任一缺失则该行为空。行序固定：① avc1 ② mp4a
#
# 关键：performance 只记录「已发生」的请求。页面刚 open 完、视频没播 → 一条
# douyinvod 都没有。所以首次为空时必须主动 play() 一次再重试（实测必需）。
DASH_JS='(()=>{const a=performance.getEntriesByType("resource").map(x=>x.name);
  const f=k=>a.filter(n=>n.indexOf("douyinvod")>=0&&n.indexOf(k)>=0)[0]||"";
  return f("avc1")+"\n"+f("mp4a")})()'

dash_parse() {
  "$PY" -c '
import json, sys
s = sys.stdin.read().strip()
try:
    s = json.loads(s)
except Exception:
    s = s.strip("\"")
lines = [l.strip() for l in s.split("\n")]
while len(lines) < 2:
    lines.append("")
print(lines[0])
print(lines[1])' 2>/dev/null
}

grab_dash() {
  local out dv
  out="$(ev "$DASH_JS" | dash_parse)"
  dv="$(print -r -- "$out" | sed -n 1p)"
  if [[ -n "$dv" ]]; then print -r -- "$out"; return 0; fi

  # 首次为空 → 主动播放（静音，避免被浏览器自动播放策略拦下），等分片请求出现
  ev '(()=>{const v=document.querySelector("video");if(!v)return "no-video";
    v.muted=true;const p=v.play();if(p&&p.catch)p.catch(()=>{});
    return "playing"})()' >/dev/null
  local i
  for i in {1..10}; do            # 最多等 ~5 秒，分片一到就提前退出
    sleep 0.5
    out="$(ev "$DASH_JS" | dash_parse)"
    dv="$(print -r -- "$out" | sed -n 1p)"
    [[ -n "$dv" ]] && break
  done
  print -r -- "$out"
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

  if [[ -n "$src" && "$src" != blob:* ]]; then
    print -r -- "$src" > "$OUT/url_$L.txt"
    rm -f "$OUT/durl_$L.txt" "$OUT/aurl_$L.txt"   # 普通直链，清掉旧的 DASH 双轨
    print -r -- "  src      : OK -> url_$L.txt"
  elif [[ "$src" == blob:* ]]; then
    : > "$OUT/url_$L.txt"                          # blob 直链是废的，置空让 dl.sh 走 DASH
    dash="$(grab_dash)"
    dv="$(print -r -- "$dash" | sed -n 1p)"
    da="$(print -r -- "$dash" | sed -n 2p)"
    print -r -- "$dv" > "$OUT/durl_$L.txt"
    print -r -- "$da" > "$OUT/aurl_$L.txt"
    if [[ -n "$dv" ]]; then
      print -r -- "  src      : blob:MSE → DASH 回落 OK（视频轨 $(print -r -- "$dv" | wc -c | tr -d ' ')B / 音频轨 $(print -r -- "$da" | wc -c | tr -d ' ')B）-> durl_/aurl_$L.txt"
      [[ -z "$da" ]] && print -r -- "  !! 未取到音频轨（无音轨素材可忽略）" | tee -a "$LOG"
    else
      print -r -- "  !! blob:MSE 回落失败——未找到 douyinvod 资源（视频可能未真正播放 / 需先点一下播放）" | tee -a "$LOG"
    fi
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
