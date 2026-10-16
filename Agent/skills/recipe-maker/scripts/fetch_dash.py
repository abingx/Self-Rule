#!/usr/bin/env python3
"""抖音 DASH 双轨直链 -> 合并 mp4。

用法:
  python3 fetch_dash.py <video_url|url文件> <audio_url|url文件> [out.mp4]

背景（2026-10-16 实测）:
  新版抖音 Web 播放走 MSE，`video.currentSrc` 返回 `blob:https://www.douyin.com/...`，
  grab.sh 抓到的直链无效、dl.sh 必然失败（curl 拿到 HTML）。
  真实分片地址可从页面 performance entries 里取，无需 cookie、无需签名：

    print -r -- '(()=>{const a=performance.getEntriesByType("resource").map(x=>x.name);
      return JSON.stringify(a.filter(n=>n.indexOf("douyinvod")>=0))})()' \
      | agent-browser eval --stdin > urls_raw.json

  结果里 `media-video-avc1` 是视频轨、`media-audio-und-mp4a` 是音频轨，各取一条传给本脚本。

注意: 分片直链带时效签名，抓到后请立即下载。

常态下无需手动跑本脚本：grab.sh 已自动检测 blob:MSE 并落 durl_/aurl_<code>.txt，
dl.sh 会自动下载双轨并 ffmpeg 合并。本脚本仅作手动兜底 / 单独调试单条链接时使用。
"""
import subprocess
import sys
from pathlib import Path

import requests

HEADERS = {
    "Referer": "https://www.douyin.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
    ),
}


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def resolve(arg: str) -> str:
    """参数既可以是 URL，也可以是放着 URL 的文件路径。"""
    if arg.startswith("http"):
        return arg
    p = Path(arg)
    if p.is_file():
        return p.read_text().strip()
    raise SystemExit(f"[x] 既不是 URL 也不是文件: {arg}")


def grab(url: str, out: Path) -> bool:
    r = requests.get(url, headers=HEADERS, stream=True, timeout=60)
    r.raise_for_status()
    with open(out, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    ok = b"ftyp" in out.open("rb").read(12)
    print(f"[{'ok' if ok else 'x'}] {out.name} {out.stat().st_size / 1e6:.2f}MB mp4={ok}")
    return ok


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    vurl, aurl = resolve(sys.argv[1]), resolve(sys.argv[2])
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("video.mp4")
    vt, at = out.with_name(out.stem + "_v.mp4"), out.with_name(out.stem + "_a.mp4")
    if not grab(vurl, vt):
        print("[x] 视频轨下载失败（直链可能已过期，回页面重新抓）")
        return 1
    if not grab(aurl, at):
        print("[x] 音频轨下载失败（无音频的素材可只保留视频轨）")
        vt.replace(out)
        return 0
    subprocess.run(
        [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(vt), "-i", str(at),
         "-c", "copy", "-movflags", "+faststart", str(out)],
        check=True,
    )
    vt.unlink(missing_ok=True)
    at.unlink(missing_ok=True)
    print(f"[ok] 合并完成 {out} {out.stat().st_size / 1e6:.2f}MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
