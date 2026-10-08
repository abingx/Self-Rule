#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读 work/lib_result.json → 生成交付物报告（HTML + TXT）。

    python3 render_lib.py

产出写 out/ 目录（`AMBS_OUT_DIR` 可改），文件名随目标区间自动命名，
例如默认的 `180-184bpm-scan.html` / `.txt`。

注意：HTML 模板含 CSS 的 `%`，一律用 `.replace()` 占位符，禁止 `%` 格式化。
"""
import json
import os

import _common as C

if not os.path.exists(C.RESULT_JSON):
    raise SystemExit(
        "缺少 %s。\n请先跑：  python3 %s\n再跑本脚本渲染报告。"
        % (C.RESULT_JSON, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "lib_report.py")))

R = json.load(open(C.RESULT_JSON, encoding="utf-8"))
A, B, Cb = R["A"], R["B"], R["C"]
D, NM, EDGE = R["D"], R["NM"], R["EDGE"]
LO, HI = R.get("LO", 180), R.get("HI", 184)
# 半速区间与 _common.half_range 同口径：半速值 b 须满足 LO <= 2b <= HI
HLO, HHI = R.get("HLO", (LO + 1) // 2), R.get("HHI", HI // 2)
# 极窄区间（如 183-183）推不出任何半速值，此时不展示双踩分组
HAS_HALF = HLO <= HHI
NTOTAL = R.get("NTOTAL") or (len(A) + len(B) + len(Cb) + len(D) + len(NM))
SRC_LABEL = R.get("SRC") or "Apple Music 资料库导出"


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def meta(track, extra=""):
    prim = " · ".join(x for x in (str(track.get("year") or ""), str(track.get("genre") or "")) if x)
    tail = "".join(x for x in (prim, extra) if x)
    return "<b>%s</b><i>%s</i>%s" % (
        esc(track["title"]), esc(track["artist"]),
        "<em>%s</em>" % esc(tail) if tail else "")


def badge(entry):
    return ('<span class="badge old">已交付</span>' if entry.get("delivered")
            else '<span class="badge new">新</span>')


rows_a = []
for e in A:
    warn = ""
    if e.get("live"):
        warn = ('<div class="warn">⚠️ 查到的《%s》只有 Live/重制版本命中，'
                '你库里是录音室版，两者不是同一次录音，建议开节拍器自测确认。</div>'
                % esc(e["track"]["title"]))
    rows_a.append('<div class="row"><span class="bpm">%s</span><span class="meta">%s</span>%s</div>%s'
                  % ("/".join(map(str, e["solo"])), meta(e["track"]), badge(e), warn))

rows_b = []
for e in B:
    rows_b.append('<div class="row"><span class="bpm">%s→%s</span><span class="meta">%s</span>%s</div>'
                  % (e["halves"][0], e["solo"][0],
                     meta(e["track"], "（同曲另有 %s）" % "/".join(map(str, e["halves"]))),
                     badge(e)))

rows_c = []
for e in sorted(Cb, key=lambda x: x["bpm"]):
    b = e["bpm"][0]
    rows_c.append('<div class="row"><span class="bpm">%d→%d</span><span class="meta">%s</span>%s</div>'
                  % (b, b * 2, meta(e["track"]), badge(e)))

edge_items = []
for e in sorted(EDGE, key=lambda x: (x["edge"][0], x["track"]["artist"])):
    for b in e["edge"]:
        if HLO <= b <= HHI + 3:
            note = "双踩 %d" % (b * 2)
        elif b < LO:
            note = "距 %d 差 %d" % (HI, HI - b)
        else:
            note = "超 %d" % (b - HI)
        edge_items.append('<li><span class="nb">%d</span><b>%s</b><i>%s</i>'
                          '<span class="ne">%s</span></li>'
                          % (b, esc(e["track"]["title"]), esc(e["track"]["artist"]), note))
edge_items = edge_items[:16]

nm_items = "".join('<li><b>%s</b><i>%s</i></li>' % (esc(e["track"]["title"]),
                                                   esc(e["track"]["artist"])) for e in NM)

n_hit = len(A) + len(B) + len(Cb)
n_new = sum(1 for e in A + B + Cb if not e.get("delivered"))

half_note = ("" if not HAS_HALF else
             " · 单拍 %d–%d 按双踩计为 %d–%d" % (HLO, HHI, LO, HI))

half_card = "" if not HAS_HALF else (
    '<div class="card">\n<h2>★ 双踩 %d–%d · 跑时按 %d–%d 双踩</h2>\n'
    '<div class="hint">原曲单拍 %d–%d，每拍踩两步即落在 %d–%d，实战最稳</div>\n%s\n</div>'
    % (HLO, HHI, LO, HI, HLO, HHI, LO, HI,
       "".join(rows_c) or '<div class="hint">无</div>'))

HTML = r'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>资料库 @@LO@@–@@HI@@ BPM 扫描</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1b1f24;--sub:#6b7280;--line:#e6e8ec;
--red:#c62828;--redbg:#fdecea;--green:#1b7f4b;--greenbg:#e8f5ee;--amber:#a5620a}
*{box-sizing:border-box}
body{margin:0;padding:32px 20px 56px;background:var(--bg);color:var(--ink);
font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",sans-serif}
.wrap{max-width:760px;margin:0 auto}
h1{font-size:24px;margin:0 0 6px;letter-spacing:-.3px}
.sub{color:var(--sub);font-size:13px;margin-bottom:22px}
.stats{display:flex;gap:10px;margin-bottom:26px;flex-wrap:wrap}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;min-width:104px}
.stat b{display:block;font-size:22px;line-height:1.2}
.stat span{font-size:12px;color:var(--sub)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin-bottom:18px}
.card h2{font-size:15px;margin:0 0 4px}
.card .hint{font-size:12.5px;color:var(--sub);margin-bottom:14px}
.row{display:flex;align-items:center;gap:14px;padding:12px 0;border-top:1px solid var(--line)}
.row:first-of-type{border-top:0}
.bpm{flex:0 0 86px;text-align:center;font-weight:700;font-size:14px;background:var(--redbg);color:var(--red);border-radius:9px;padding:6px 0}
.meta{flex:1;min-width:0}
.meta b{display:block;font-size:15px}
.meta i{display:block;font-style:normal;color:var(--sub);font-size:13px}
.meta em{display:block;font-style:normal;color:#9aa1ab;font-size:11.5px;margin-top:2px}
.badge{flex:0 0 auto;font-size:11.5px;border-radius:20px;padding:3px 10px;white-space:nowrap}
.badge.new{background:var(--redbg);color:var(--red)}
.badge.old{background:var(--greenbg);color:var(--green)}
.warn{background:#fff8e8;border:1px solid #f3e0b5;color:var(--amber);border-radius:10px;padding:10px 13px;font-size:12.5px;margin-top:12px}
ul.near,ul.nd{list-style:none;margin:0;padding:0;font-size:13.5px}
ul.near li,ul.nd li{display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid var(--line)}
ul.near li:first-child,ul.nd li:first-child{border-top:0}
.nb{flex:0 0 42px;text-align:center;font-weight:700;color:#8a8f98;background:#f1f2f4;border-radius:7px;padding:2px 0;font-size:12.5px}
.ne{margin-left:auto;color:#9aa1ab;font-size:12px}
.foot{color:var(--sub);font-size:12.5px;text-align:center;margin-top:26px}
</style></head><body><div class="wrap">
<h1>资料库 @@LO@@–@@HI@@ BPM 扫描</h1>
<div class="sub">源：Apple Music 导出清单 <code>@@SRC@@</code> · 判定：songbpm.com 逐曲实测@@HALFNOTE@@</div>

<div class="stats">
<div class="stat"><b>@@NTOTAL@@</b><span>资料库曲目</span></div>
<div class="stat"><b>@@GOTBPM@@</b><span>取到 BPM</span></div>
<div class="stat"><b>@@NHIT@@</b><span>命中 @@LO@@–@@HI@@</span></div>
<div class="stat"><b>@@NNEW@@</b><span>其中未交付过</span></div>
</div>

<div class="card">
<h2>★ 单拍 @@LO@@–@@HI@@ · 直接跟跑</h2>
<div class="hint">节拍与原曲一致，不需要双踩</div>
@@ROWSA@@
</div>

<div class="card">
<h2>★ 半速底 · 同曲另有 @@HLO@@–@@HHI@@</h2>
<div class="hint">原曲单拍就在目标区间，同时另有半速条目可切换</div>
@@ROWSB@@
</div>

@@HALFCARD@@
<div class="card">
<h2>差一点 · 出界备查</h2>
<div class="hint">不满足 @@LO@@–@@HI@@，列出供参考</div>
<ul class="near">@@EDGE@@</ul>
</div>

<div class="card">
<h2>无 BPM 数据</h2>
<div class="hint">songbpm 未收录，未能判定</div>
<ul class="nd">@@NM@@</ul>
</div>

<div class="foot">本清单只做筛选，加歌请在 Apple Music 内自行搜索添加。</div>
</div></body></html>
'''

html = (HTML.replace("@@LO@@", str(LO)).replace("@@HI@@", str(HI))
            .replace("@@HLO@@", str(HLO)).replace("@@HHI@@", str(HHI))
            .replace("@@SRC@@", esc(SRC_LABEL))
            .replace("@@NTOTAL@@", str(NTOTAL))
            .replace("@@GOTBPM@@", str(NTOTAL - len(NM)))
            .replace("@@NHIT@@", str(n_hit))
            .replace("@@NNEW@@", str(n_new))
            .replace("@@ROWSA@@", "".join(rows_a) or '<div class="hint">无</div>')
            .replace("@@ROWSB@@", "".join(rows_b) or '<div class="hint">无</div>')
            .replace("@@ROWSC@@", "".join(rows_c) or '<div class="hint">无</div>')
            .replace("@@EDGE@@", "".join(edge_items) or '<li class="hint">无</li>')
            .replace("@@NM@@", nm_items or '<li class="hint">无</li>')
            .replace("@@HALFNOTE@@", half_note)
            .replace("@@HALFCARD@@", half_card))

def tail(track, sep=" / "):
    """年份 / 流派 之类附加信息的文本尾巴；两者都空时返回空串。"""
    return sep.join(x for x in (str(track.get("year") or ""),
                                str(track.get("genre") or "")) if x)


T = []
T.append("资料库 %d–%d BPM 扫描结果" % (LO, HI))
T.append("源文件：%s（Apple Music 导出，%d 首）" % (SRC_LABEL, NTOTAL))
T.append("判定依据：songbpm.com 实测 BPM" + (
    "；单拍 %d–%d 为双踩（×2 落在 %d–%d）" % (HLO, HHI, LO, HI) if HAS_HALF else ""))
T.append("=" * 62)
T.append("")
T.append("【结论】%d 首中 %d 首取到 BPM，命中 %d–%d 共 %d 首（未交付过 %d 首），%d 首无数据。"
         % (NTOTAL, NTOTAL - len(NM), LO, HI, n_hit, n_new, len(NM)))
T.append("")
T.append("★ A 单拍 %d–%d（直接跟跑）" % (LO, HI))
for e in A:
    t = tail(e["track"], "，")
    T.append("  %s  %s - %s%s%s" % ("/".join(map(str, e["solo"])), e["track"]["title"],
                                    e["track"]["artist"],
                                    "（%s）" % t if t else "",
                                    "［已交付］" if e.get("delivered") else "［新］"))
    if e.get("live"):
        T.append("        注意：只有 Live/重制版本命中，你库里是录音室版，建议自测确认。")
T.append("")
T.append("★ B 半速底 %d–%d（同曲另有半速条目）" % (LO, HI))
for e in B:
    t = tail(e["track"])
    T.append("  %s（同曲 %s）  %s - %s%s%s"
             % ("/".join(map(str, e["solo"])), "/".join(map(str, e["halves"])),
                e["track"]["title"], e["track"]["artist"],
                "（%s）" % t if t else "",
                "［已交付］" if e.get("delivered") else "［新］"))
T.append("")
if HAS_HALF:
    T.append("★ C 双踩 %d–%d（跑时按 %d–%d 双踩，最实用）" % (HLO, HHI, LO, HI))
for e in sorted(Cb, key=lambda x: x["bpm"]):
    b = e["bpm"][0]
    t = tail(e["track"])
    T.append("  %d→%d  %s - %s%s%s"
             % (b, b * 2, e["track"]["title"], e["track"]["artist"],
                "（%s）" % t if t else "",
                "［已交付］" if e.get("delivered") else "［新］"))
T.append("")
T.append("· 差一点（不建议用，仅供备查）")
for e in sorted(EDGE, key=lambda x: (x["edge"][0], x["track"]["artist"])):
    for b in e["edge"]:
        note = ("双踩 %d" % (b * 2)) if HLO <= b <= HHI + 3 else (
            "距 %d 差 %d" % (HI, HI - b) if b < LO else "超 %d" % (b - HI))
        T.append("  %3d（%s）  %s - %s" % (b, note, e["track"]["title"], e["track"]["artist"]))
T.append("")
T.append("· 无 BPM 数据（未收录，未判定）")
T.append("  " + "；".join("%s - %s" % (e["track"]["title"], e["track"]["artist"]) for e in NM))
T.append("")
T.append("=" * 62)
T.append("说明：本清单只做筛选，加歌请在 Apple Music 内自行搜索添加。")

C.ensure_dirs()
stem = os.path.join(C.OUT, "%d-%dbpm-scan" % (LO, HI))
with open(stem + ".html", "w", encoding="utf-8") as fh:
    fh.write(html)
with open(stem + ".txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(T) + "\n")
print("已写出 %s.html / .txt" % stem)
print("命中 %d（新 %d）| 无数据 %d" % (n_hit, n_new, len(NM)))
