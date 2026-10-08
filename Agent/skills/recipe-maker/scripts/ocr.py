"""抽帧 + OCR 提取画面字幕（默认不落盘，JPEG 经管道直喂 OCR）。

用法:
    python ocr.py <video.mp4> [抽帧间隔秒=1.0] [保留帧目录]   # 给了目录才落帧图
    python ocr.py check <video.mp4> <t1[,t2,...]> [输出目录]   # 抽指定时间点帧，供 Read 逐字核对

建议间隔：纯字幕短视频(<30s) 0.5s；口播型 1.0s；长视频(>3min) 1.5s
输出：
    stdout 去重后的字幕行（贴片水印/安全提示需人工剔除）
    <工作目录>/subs_<name>.txt  同上内容落盘（长任务 stdout 被截断也不丢）
    「工作目录」= 当前项目下的 .recipe-maker/work，见 _dirs.py

实现要点（相对旧版的差别）：
- 抽帧由「每帧起一次 ffmpeg -ss」改为「一次 ffmpeg 全解码 + fps 滤镜」，帧数越多提速越明显；
- 默认不写帧图（管道 → cv2 解码 → OCR），省磁盘 + 省 IO；要留档用第 3 个参数指定目录；
- 去重前先归一化（去空白/标点），比整串精确匹配少漏掉 90% 的滚动重排噪声。
"""
import os
import re
import subprocess
import sys
import tempfile
from fractions import Fraction

try:
    import cv2
    import imageio_ffmpeg
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
except ImportError as e:
    sys.exit(f"缺少依赖 {e.name}，先装：python3 -m pip install rapidocr-onnxruntime imageio-ffmpeg")

import _dirs

ff = imageio_ffmpeg.get_ffmpeg_exe()
_NORM = re.compile(r"[\s\u3000,.，。！!？?、:：;；·…—\-_|/\\()（）\[\]【】]+")


def duration(path):
    out = subprocess.run([ff, "-hide_banner", "-i", path],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _fps_arg(step):
    fr = Fraction(1 / step).limit_denominator(1000)
    return (f"{fr.numerator}/{fr.denominator}" if fr.denominator != 1 else str(fr.numerator)), float(fr)


def frames(video, step=1.0, keep_dir=None):
    """按 step 秒抽帧，逐帧 yield (时间秒, BGR ndarray)。

    keep_dir 为空 → 管道流式（不落盘）；给定 → 帧图写到该目录再读回（便于事后 Read 核对）。
    """
    fps_arg, fps = _fps_arg(step)
    if keep_dir:
        os.makedirs(keep_dir, exist_ok=True)
        for f in os.listdir(keep_dir):
            if f.endswith(".jpg"):
                os.unlink(os.path.join(keep_dir, f))
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-i", video,
                        "-vf", f"fps={fps_arg}", "-q:v", "2",
                        f"{keep_dir}/%06d.jpg"], check=True)
        for n, f in enumerate(sorted(os.listdir(keep_dir)), start=1):
            img = cv2.imread(os.path.join(keep_dir, f))
            if img is not None:
                yield (n - 1) / fps, img
        return

    cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", video,
           "-vf", f"fps={fps_arg}", "-q:v", "2",
           "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
    errf = tempfile.TemporaryFile()          # stderr 落地临时文件，避免管道写满导致死锁
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errf)
    buf, idx = b"", 0
    try:
        while True:
            chunk = p.stdout.read(1 << 16)
            if not chunk:
                break
            buf += chunk
            while True:                      # 按 JPEG SOI/EOI 切帧
                i = buf.find(b"\xff\xd8")
                if i < 0:
                    buf = buf[-1:]           # 只留可能被截断的标记首字节
                    break
                j = buf.find(b"\xff\xd9", i + 2)
                if j < 0:
                    buf = buf[i:]            # 丢掉 SOI 之前的残留，等下一批数据
                    break
                jpg, buf = buf[i:j + 2], buf[j + 2:]
                img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    yield idx / fps, img
                idx += 1
    finally:
        p.stdout.close()
        p.wait()
        errf.seek(0)
        err = errf.read().decode(errors="ignore").strip()
        errf.close()
        if p.returncode not in (0, None) and err:
            print(f"[warn] ffmpeg: {err[:300]}", file=sys.stderr)


def run(video, step=1.0, keep_dir=None):
    """OCR 全片，返回去重后的 [(时间, 文本)]。"""
    ocr = RapidOCR()
    dur = duration(video)
    print(f"# {os.path.basename(video)}  {dur:.1f}s  step={step}s  "
          f"frames≈{int(dur / step) + 1}  keep_frames={'是 ' + keep_dir if keep_dir else '否'}", file=sys.stderr)

    seen, out, n_frame, n_hit = set(), [], 0, 0
    for t, img in frames(video, step, keep_dir):
        n_frame += 1
        try:
            r, _ = ocr(img)
        except Exception as e:
            r = None
            print(f"[warn] OCR 失败 @{t:.1f}s: {e}", file=sys.stderr)
        txt = " ".join(x[1] for x in r) if r else ""
        key = _NORM.sub("", txt)
        if len(key) < 2 or key in seen:      # 归一化后去重，同时丢掉纯标点/单字噪声
            continue
        seen.add(key)
        n_hit += 1
        out.append((t, txt))
        print(f"[{t:>6.1f}s] {txt}", flush=True)

    subs = os.path.join(_dirs.work_dir(), f"subs_{os.path.splitext(os.path.basename(video))[0]}.txt")
    os.makedirs(os.path.dirname(subs), exist_ok=True)
    with open(subs, "w") as fh:
        for t, txt in out:
            fh.write(f"[{t:>6.1f}s] {txt}\n")
    print(f"# 抽帧 {n_frame}，有效字幕 {n_hit} 条（旧版按整串精确去重，条数通常更多但含大量重排噪声）",
          file=sys.stderr)
    print(f"# 落盘: {subs}", file=sys.stderr)
    return out


def check(video, timestamps, outdir=None):
    """抽指定时间点的帧到磁盘，用于 Read 逐字核对用量/易混字。"""
    outdir = outdir or os.path.join(_dirs.work_dir(), "chk")
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for t in timestamps:
        p = os.path.join(outdir, f"{t}.jpg")
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-ss", str(t), "-i", video,
                        "-frames:v", "1", "-q:v", "2", "-y", p], capture_output=True)
        paths.append(p)
    print("\n".join(paths))                  # 直接给出可 Read 的绝对路径
    print(f"# checked {len(paths)} frames -> {outdir}", file=sys.stderr)
    return paths


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(2)
    if a[0] == "check":
        if len(a) < 3:
            sys.exit("用法: python ocr.py check <video.mp4> <t1[,t2,...]> [输出目录]")
        check(a[1], [float(x) for x in a[2].replace(",", " ").split()], a[3] if len(a) > 3 else None)
    else:
        run(a[0], float(a[1]) if len(a) > 1 else 1.0, a[2] if len(a) > 2 else None)
