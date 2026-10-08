"""whisper 转写（中文视频）—— 转写 / 单段复核 / 类型探针。

用法（旧写法全部兼容）:
    python asr.py <video.mp4> [small|medium] [prompt]           # 整片转写
    python asr.py <video.mp4> slice <start> <dur> [size] [prompt]   # 只转一段，复核争议句
    python asr.py <video.mp4> probe [size] [head_seconds]       # 只转片头，自动判口播型/字幕型

probe 会打印：时长、建议抽帧间隔、类型判定、疑似方言误识词。
判定为「字幕型」时别再烧 ASR，直接走 OCR。

提示:
- vad_filter 必须 False，否则可能整段被滤空。
- 川渝等方言账号优先用 medium，并用画面字幕(OCR)交叉核对。
- 克数冲突（ASR vs OCR）一律抽帧 Read 定稿。
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

try:
    import imageio_ffmpeg
    from faster_whisper import WhisperModel
except ImportError as e:  # 依赖缺失时给出可复制的修复命令
    sys.exit(f"缺少依赖 {e.name}，先装：python3 -m pip install faster-whisper imageio-ffmpeg")

ff = imageio_ffmpeg.get_ffmpeg_exe()
SIZES = ("tiny", "base", "small", "medium", "large-v3")

# whisper 对静音/纯乐音的固定幻觉（小铃铛、字幕组署名那套）——命中即判定无口播
HALLUCINATIONS = ("謝謝觀賞", "谢谢观赏", "感謝觀看", "感谢观看", "訂閱", "订阅", "小鈴鐺", "小铃铛",
                  "字幕由", "字幕by", "字幕BY", "字幕組", "字幕组", "志願者", "志愿者",
                  "索兰娅", "明镜与点点", "amara", "subtitle", "ming pao", "请点赞", "点赞关注")
# 已实测的方言误识模式（SKILL.md「关键坑」）——命中即提醒以 OCR 为准
DIALECT_WRONG = ("三玉", "日江", "姿姜", "三奶", "香脂锅", "烧熄", "牛丁", "两公坨")


def duration(path):
    """用 ffmpeg -i 的 stderr 拿时长（imageio-ffmpeg 不带 ffprobe）。"""
    out = subprocess.run([ff, "-hide_banner", "-i", path],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def step_hint(d):
    if not d or d <= 0:
        return "1.0"
    return "0.5" if d <= 30 else ("1.0" if d <= 180 else "1.5")


NO_AUDIO_HINT = ("该视频没有音轨（纯字幕型）。别用 ASR，直接跑 ocr.py 抽画面字幕。")


def has_audio(path):
    out = subprocess.run([ff, "-hide_banner", "-i", path],
                         capture_output=True, text=True).stderr
    return "Audio:" in out


def audio_slice(src, start, dur, dst):
    r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-ss", str(start), "-t", str(dur),
                        "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-y", dst],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) < 1024:
        msg = (r.stderr or "").strip().splitlines()
        sys.exit(f"切音频失败：{msg[-1] if msg else 'ffmpeg 未产出音频'}\n→ {NO_AUDIO_HINT}")


def transcribe(path, size="small", prompt="", start=None, dur=None, report=False):
    """转写并逐段打印；start 非空时先切音频（临时 wav 无论成功失败都删）。"""
    if not has_audio(path):
        sys.exit(NO_AUDIO_HINT)
    src, tmp = path, None
    try:
        if start is not None:
            fd, tmp = tempfile.mkstemp(prefix=".asr_seg_", suffix=".wav",
                                       dir=os.path.dirname(os.path.abspath(path)) or ".")
            os.close(fd)
            audio_slice(path, start, dur, tmp)
            src = tmp
        model = WhisperModel(size, device="cpu", compute_type="int8")
        segs, _ = model.transcribe(src, language="zh", vad_filter=False,
                                   beam_size=5, initial_prompt=prompt or None)
        segs = list(segs)
        for s in segs:
            tail = f"   <no_speech {s.no_speech_prob:.2f}>" if report and s.no_speech_prob > 0.6 else ""
            print(f"[{s.start:6.1f}-{s.end:6.1f}] {s.text}{tail}", flush=True)
        return segs
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def probe(path, size="small", head=10.0):
    """只转片头，自动判型 —— 把「先跑 10 秒判断类型」这条人工经验固化成代码。"""
    dur = duration(path)
    win = min(head, dur or head)
    segs = transcribe(path, size, start=0.0, dur=win, report=True)
    text = "".join(s.text for s in segs)
    max_ns = max((s.no_speech_prob for s in segs), default=1.0)
    span = (segs[-1].end - segs[0].start) if segs else 0.0

    hits = [w for w in HALLUCINATIONS if w.lower() in text.lower()]
    reasons = []
    if hits:
        reasons.append(f"命中静音幻觉词：{'、'.join(hits)}")
    if max_ns > 0.5:
        reasons.append(f"no_speech_prob 最高 {max_ns:.2f}")
    # 幻影段形态：整段只吐一条、却横跨大半个窗口，且文本极短（纯 BGM/音效常见）
    if len(segs) == 1 and span >= win * 0.7 and len(text.strip()) <= 20:
        reasons.append(f"单段横跨 {span:.0f}s/{win:.0f}s 且仅 {len(text.strip())} 字 —— 典型幻影段")
    elif any(text.count(x) >= 3 for x in ("秋天", "春天", "谢谢", "谢谢大家", "字幕")):
        reasons.append("同一短语重复 ≥3 次 —— 疑似幻觉")

    verdict = ("字幕型 / 无口播 → 别再烧 ASR，直接跑 ocr.py 抽画面字幕" if reasons
               else "口播型（文本连贯，可继续 ASR）")

    print("\n=== probe ===", file=sys.stderr)
    print(f"duration: {dur:.1f}s   建议抽帧间隔: {step_hint(dur)}s   size: {size}", file=sys.stderr)
    print(f"判定: {verdict}", file=sys.stderr)
    for r in reasons:
        print(f"  · {r}", file=sys.stderr)
    dia = [w for w in DIALECT_WRONG if w in text]
    if dia:
        print(f"  · 疑似方言误识：{'、'.join(dia)} → 以 OCR 字幕为准，或整段换 medium", file=sys.stderr)
    if dur and dur <= 30:
        print("  · 短视频（≤30s）：建议 small + medium 各跑一遍，成本极低且常能互相纠正", file=sys.stderr)
    return verdict


def main():
    ap = argparse.ArgumentParser(description="whisper 中文转写 / 复核 / 探针", add_help=True)
    ap.add_argument("video")
    ap.add_argument("rest", nargs="*", help="[size] [prompt] | slice <start> <dur> [size] [prompt] | probe [size] [head]")
    a = ap.parse_args()
    v, rest = a.video, a.rest

    if rest and rest[0] == "probe":
        probe(v, rest[1] if len(rest) > 1 else "small",
              float(rest[2]) if len(rest) > 2 else 10.0)
        return 0

    if rest and rest[0] == "slice":
        if len(rest) < 3:
            sys.exit("用法: python asr.py <video.mp4> slice <start> <dur> [size] [prompt]")
        transcribe(v, rest[3] if len(rest) > 3 else "small",
                   rest[4] if len(rest) > 4 else "",
                   start=float(rest[1]), dur=float(rest[2]))
        return 0

    # 兼容旧写法：size 可省，prompt 可单独出现
    if rest and rest[0] in SIZES:
        size, prompt = rest[0], (rest[1] if len(rest) > 1 else "")
    else:
        size, prompt = "small", (rest[0] if rest else "")
    d = duration(v)
    print(f"# {os.path.basename(v)}  {d:.1f}s  建议抽帧间隔 {step_hint(d)}s  size={size}", file=sys.stderr)
    transcribe(v, size, prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
