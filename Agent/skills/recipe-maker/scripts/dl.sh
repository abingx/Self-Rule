#!/bin/zsh
# recipe-maker / dl.sh —— 按 grab.sh 存下的直链下载 mp4
#
# 用法: zsh dl.sh <code>:<输出名> [<code>:<名> ...]
# 例:   zsh dl.sh eQB1VEI1Tlo:jiandou 4OKp_vWSck8:donggua
# 依赖: 同一工作目录下的 url_<code>.txt（grab.sh 生成），两侧目录必须一致
# 校验: 必须落到真 MP4（ISO Media）。直链有时效，过期会返回 HTML 错误页，
#       本脚本会识别并删除坏文件、给出「重跑 grab.sh」提示，而不是留下 351 字节假 mp4。
# 退出码: 全部成功 0；有失败 1（便于批量链路提前发现）
source "${0:A:h}/_dirs.sh"
OUT="$RM_WORK_DIR"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
oks=0; fails=0

for pair in "$@"; do
  if [[ "$pair" != *:* ]]; then
    print -r -- "  !! 参数格式应为 <code>:<名>，收到：$pair"; fails=$((fails + 1)); continue
  fi
  L="${pair%%:*}"; N="${pair##*:}"
  uf="$OUT/url_$L.txt"
  if [[ ! -s "$uf" ]]; then
    print -r -- "$N: 缺 $uf —— 先跑 grab.sh $L"; fails=$((fails + 1)); continue
  fi
  URL=$(sed -e 's/^"//' -e 's/"$//' "$uf")
  if [[ -z "$URL" || "$URL" == "null" || "$URL" == "undefined" ]]; then
    print -r -- "$N: 直链为空 —— 重跑 grab.sh $L"; fails=$((fails + 1)); continue
  fi

  dst="$OUT/$N.mp4"
  if ! curl -fSL --retry 3 --retry-delay 1 --connect-timeout 10 --max-time 600 \
       -H "Referer: https://www.douyin.com/" -H "User-Agent: $UA" \
       -o "$dst" "$URL" 2>/dev/null; then
    print -r -- "$N: curl 下载失败（网络 / 直链被拒）"; rm -f "$dst"; fails=$((fails + 1)); continue
  fi

  info=$(file -b "$dst")
  if [[ "$info" != *"ISO Media"* && "$info" != *"MP4"* && "$info" != *"QuickTime"* ]]; then
    print -r -- "$N: 下载到的不是视频（$info）→ 直链多半已过期，重跑 grab.sh $L"
    rm -f "$dst"; fails=$((fails + 1)); continue
  fi
  print -r -- "$N: OK  $(ls -lh "$dst" | awk '{print $5}')  $info"
  oks=$((oks + 1))
done

print -r -- "-- dl.sh: 成功 $oks / 失败 $fails --"
[[ $fails -eq 0 ]] || exit 1
