#!/bin/zsh
# recipe-maker / dl.sh —— 按 grab.sh 存下的直链下载 mp4（单轨 / DASH 双轨自动分流）
#
# 用法: zsh dl.sh <code>:<输出名> [<code>:<名> ...]
# 例:   zsh dl.sh eQB1VEI1Tlo:jiandou 4OKp_vWSck8:donggua
# 依赖: 同一工作目录下的 url_<code>.txt（普通直链）或 durl_/aurl_<code>.txt（DASH 双轨），
#       均由 grab.sh 生成；两侧目录必须一致。
# 校验: 必须落到真 MP4（ISO Media）。直链有时效，过期会返回 HTML 错误页，
#       本脚本会识别并删除坏文件、给出「重跑 grab.sh」提示，而不是留下 351 字节假 mp4。
# 分流: 有 durl_<code>.txt（新版抖音 MSE/blob 回落产物）时，自动下载视频轨+音频轨并
#       ffmpeg -c copy 合并；否则按 url_<code>.txt 单轨下载。
# 退出码: 全部成功 0；有失败 1（便于批量链路提前发现）
source "${0:A:h}/_dirs.sh"
OUT="$RM_WORK_DIR"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
PY=${PY:-$(command -v python3 || print -r -- /usr/bin/python3)}
oks=0; fails=0

# 找 ffmpeg：优先 imageio_ffmpeg 自带静态版（与 asr.py/ocr.py 同源），否则退回 PATH
# 隔离 runtime 的 python3 可能没装 imageio_ffmpeg → 依次试 $RECIPE_PYTHON / envs/default
rm_ffmpeg() {
  local py
  for py in "${RECIPE_PYTHON:-}" "$HOME/.workbuddy/binaries/python/envs/default/bin/python" "$PY"; do
    [[ -n "$py" && -x "$py" ]] || continue
    "$py" -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null && return
  done
  command -v ffmpeg
}

# 校验产物是真 MP4；非真则删文件、返回 1
rm_check_mp4() {
  local f="$1" info
  info=$(file -b "$f")
  if [[ "$info" != *"ISO Media"* && "$info" != *"MP4"* && "$info" != *"QuickTime"* ]]; then
    print -r -- "  × 下载到的不是视频（$info）"; rm -f "$f"; return 1
  fi
  print -r -- "  ✓ $(ls -lh "$f" | awk '{print $5}')  $info"
  return 0
}

rm_curl() {  # $1=url $2=输出
  curl -fSL --retry 3 --retry-delay 1 --connect-timeout 10 --max-time 600 \
    -H "Referer: https://www.douyin.com/" -H "User-Agent: $UA" -o "$2" "$1" 2>/dev/null
}

for pair in "$@"; do
  if [[ "$pair" != *:* ]]; then
    print -r -- "  !! 参数格式应为 <code>:<名>，收到：$pair"; fails=$((fails + 1)); continue
  fi
  L="${pair%%:*}"; N="${pair##*:}"
  uf="$OUT/url_$L.txt"
  df="$OUT/durl_$L.txt"; af="$OUT/aurl_$L.txt"
  dst="$OUT/$N.mp4"

  # ── DASH 双轨分支（grab.sh 检测到 blob:MSE 时落的文件）──────────────────
  if [[ -s "$df" ]]; then
    DURL=$(sed -e 's/^"//' -e 's/"$//' "$df")
    AURL=$([[ -s "$af" ]] && sed -e 's/^"//' -e 's/"$//' "$af")
    if [[ -z "$DURL" || "$DURL" == "null" ]]; then
      print -r -- "$N: DASH 视频轨为空 —— 重跑 grab.sh $L"; fails=$((fails + 1)); continue
    fi
    print -r -- "$N: DASH 双轨模式（blob:MSE 回落）"
    vt="$OUT/${N}_v.mp4"; at="$OUT/${N}_a.mp4"
    if ! rm_curl "$DURL" "$vt"; then
      print -r -- "$N: 视频轨 curl 失败（直链可能已过期，回页面重抓）"; rm -f "$vt"; fails=$((fails + 1)); continue
    fi
    if ! rm_check_mp4 "$vt"; then
      print -r -- "$N: 视频轨不是真 MP4 → 直链多半已过期，重跑 grab.sh $L"; fails=$((fails + 1)); continue
    fi
    FF="$(rm_ffmpeg)"
    if [[ -z "$FF" ]]; then
      print -r -- "$N: 找不到 ffmpeg（pip install imageio-ffmpeg 或装系统 ffmpeg）"; rm -f "$vt"; fails=$((fails + 1)); continue
    fi
    if [[ -n "$AURL" && "$AURL" != "null" ]] && rm_curl "$AURL" "$at" && rm_check_mp4 "$at"; then
      if "$FF" -y -loglevel error -i "$vt" -i "$at" -c copy -movflags +faststart "$dst"; then
        print -r -- "$N: OK  合并完成 $(ls -lh "$dst" | awk '{print $5}')"
        oks=$((oks + 1))
      else
        print -r -- "$N: ffmpeg 合并失败，仅保留视频轨"
        mv -f "$vt" "$dst"; oks=$((oks + 1))
      fi
      rm -f "$at"
    else
      print -r -- "$N: 音频轨缺失/失败——仅保留无声视频轨（无音轨素材属正常）"
      rm -f "$at"
      mv -f "$vt" "$dst"; oks=$((oks + 1))
    fi
    rm -f "$vt"
    continue
  fi

  # ── 普通单轨分支 ────────────────────────────────────────────────────
  if [[ ! -s "$uf" ]]; then
    print -r -- "$N: 缺 $uf —— 先跑 grab.sh $L"; fails=$((fails + 1)); continue
  fi
  URL=$(sed -e 's/^"//' -e 's/"$//' "$uf")
  if [[ -z "$URL" || "$URL" == "null" || "$URL" == "undefined" ]]; then
    print -r -- "$N: 直链为空 —— 重跑 grab.sh $L"; fails=$((fails + 1)); continue
  fi
  if ! rm_curl "$URL" "$dst"; then
    print -r -- "$N: curl 下载失败（网络 / 直链被拒）"; rm -f "$dst"; fails=$((fails + 1)); continue
  fi
  if ! rm_check_mp4 "$dst"; then
    print -r -- "$N: → 直链多半已过期，重跑 grab.sh $L"; fails=$((fails + 1)); continue
  fi
  oks=$((oks + 1))
done

print -r -- "-- dl.sh: 成功 $oks / 失败 $fails --"
[[ $fails -eq 0 ]] || exit 1

