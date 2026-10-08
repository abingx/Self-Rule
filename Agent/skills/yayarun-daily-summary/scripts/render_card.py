#!/usr/bin/env python3
"""跑鸭·RunYay 跑步卡片生成器：JSON -> 单文件离线 HTML（内联 CSS，无外部依赖）。

用法：render_card.py <输入.json> <输出.html>

单位约定（重要）：接口 averagePace / avgPace 的原始单位是 **分钟/公里**
（5.311 = 5'19"/km），内部字段统一叫 paceMinPerKm，展示时才转成 m'ss"。

版面（卡片主要在 iPhone 14 竖屏 390×844 上预览）：
  - **无图表**（配速曲线 / 心率区间 / 步频功率均已按需求移除）。
  - 分段明细表版式对齐跑鸭 App「训练分段」：父行=连续同类型组（灰底 + 类型配色），
    子行=组内各圈（缩进序号）。窄屏保持表格形态、横向滚动，
    不要改成卡片堆叠 —— 那会破坏父行/子行的分组关系。
  - 字号整体对齐 ~/Documents/YaYaRun/run-summary-2026-09-25.html 的口径
    （表格 12px、小节标题 14px、页脚 11.5px）。
  - 处理刘海/Home 指示条安全区、iOS 文字缩放、-webkit-tap-highlight 等。

间歇课：LAP 的 intervalType 多于一种取值时按**连续段**分组（热身→训练→恢复→…），
保持实际训练顺序；同一类型可能出现多组，统计时要合并该类型的所有组。

退出码：0=成功且自检通过 / 1=输入错误或自检发现问题
"""
import json
import sys
import html
import re
from datetime import datetime
from pathlib import Path

BRAND_PRIMARY = "#1AA9F8"
BRAND_DARK = "#0B6FB0"
BRAND_LIGHT = "#E8F6FE"
ATTRIBUTION = "数据来源：跑鸭·RunYay"

MOBILE_MAX_W = 480               # 窄屏断点


# ---------------------------------------------------------------- 格式化

def fmt_pace(min_per_km) -> str:
    """分钟/公里 -> m'ss"：5.311 -> 5'19\""""
    if not min_per_km:
        return "—"
    total = int(round(min_per_km * 60))
    return f"{total // 60}'{total % 60:02d}\""


def fmt_duration(seconds) -> str:
    if seconds is None:
        return "—"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_num(value, digits=0, suffix=""):
    if value is None:
        return "—"
    return f"{value:,.{digits}f}{suffix}"


def val(value, digits=0):
    """卡片数值：缺失显示 —，绝不泄漏 None。"""
    return "—" if value is None else f"{value:.{digits}f}"


def esc(text) -> str:
    return html.escape(str(text), quote=True)



def seg_table(groups):
    """分段明细表（版式对齐跑鸭 App「训练分段」，但保留本卡片自己的 10 列）。

    - 每个**连续同类型组**一行父行（灰底）：段列放「序号 + 类型名」，
      其余指标列放该组汇总（总用时 / 组均配速 / 组均心率 / 组均步频）；
      总距离以副标题形式跟在类型名后面（本表无「距离」列）。
    - 组内每圈一行子行：缩进的圈序号 + 该圈各项数据。
    - 列序：段 / 用时 / 配速 / 心率 / 步频 / 功率 / 触地 / 步幅 / 垂直振幅 / 爬升
    - **无「距离 (m)」列**，「用时」是该段自身时长（非累计），不显示「尾段」标记
    - 每个单元格带 data-label，窄屏下切换成「每段一张小卡」的堆叠布局
    """
    # (标签, 取值函数, 单位) —— 单位供窄屏 data-label 用
    cols = [
        ("用时", lambda s: fmt_duration(s.get("durationSeconds")), ""),
        ("配速", lambda s: fmt_pace(s.get("paceMinPerKm")), "/km"),
        ("心率", lambda s: fmt_num(s.get("avgHeartRate")), "bpm"),
        ("步频", lambda s: fmt_num(s.get("cadence")), "spm"),
        ("功率", lambda s: fmt_num(s.get("power")), "W"),
        ("触地", lambda s: fmt_num(s.get("contactTimeMs"), 1), "ms"),
        ("步幅", lambda s: fmt_num(s.get("strideCm"), 2), "cm"),
        ("垂直振幅", lambda s: fmt_num(s.get("verticalOscillationCm"), 1), "cm"),
        ("爬升", lambda s: fmt_num(s.get("elevationGain"), 1), "m"),
    ]
    n_metric = len(cols)

    def label_of(label, unit):
        # 单位自带斜杠的（配速的 /km）不要再拼一个斜杠，否则出现 "配速//km"
        return f"{label}{unit}" if unit.startswith("/") else (f"{label}/{unit}" if unit else label)

    out = []
    for gi, g in enumerate(groups, start=1):
        st = g["stats"]
        # 父行：段列 = 序号 + 类型名（+距离副标题）；指标列 = 该组汇总
        out.append(f'''<tr class="g" data-t="{esc(g['type'])}">
  <td class="c-gidx" data-label="组"><span class="g-no">{gi}</span>
    <span class="t-{esc(g['type'])} g-name">{esc(g['label'])}</span>
    <span class="g-sub">{st['distanceMeters'] / 1000:.2f} km · {st['count']} 段</span></td>
  <td data-label="总用时">{fmt_duration(st['durationSeconds'])}</td>
  <td data-label="组均配速">{fmt_pace(st['paceMinPerKm'])}</td>
  <td data-label="组均心率">{fmt_num(st.get('avgHeartRate'))}</td>
  <td data-label="组均步频">{fmt_num(st.get('avgCadence'))}</td>
  <td colspan="{n_metric - 4}"></td>
</tr>''')
        # 子行：组内第 n 圈（序号从 1 起，不沿用全局 segmentIndex，避免"第 9 段"出现在第 2 组里）
        for si, s in enumerate(g["segments"], start=1):
            tds = "".join(
                f'<td data-label="{esc(label_of(label, unit))}">{fn(s)}</td>'
                for label, fn, unit in cols)
            out.append(f'''<tr class="s">
  <td class="c-sidx" data-label="段">{si}</td>
  {tds}
</tr>''')
    return "\n".join(out)


DEFAULT_MAX_HR = 181           # 接口没给 userMaxHeartRate 时的个人兜底值
ACTIVITY_LABELS = {"or": "户外跑"}


def _insights(s, km, full, hr_pct, max_hr):
    """训练解读：文案与判定全部由本次数据驱动，缺数据的条目直接省略（原版是写死的模板文案）。

    间歇训练（isInterval）时，"段号"不等于"公里"，配速极差与心率漂移的措辞要跟着换，
    否则会出现"最快第 3 km"这种与事实不符的描述。
    """
    out = []
    avg_hr, mx = s.get("avgHeartRate"), s.get("maxHeartRate")
    is_interval = bool(s.get("isInterval"))

    if avg_hr and hr_pct is not None:
        if hr_pct < 70:
            title, cls, tail = "低强度有氧", "good", "整体处于轻松有氧区间。"
        elif hr_pct < 80:
            title, cls, tail = "中等强度", "warn", "接近节奏跑强度，安排恢复时留意疲劳。"
        else:
            title, cls, tail = "强度偏高", "alert", "强度较高，注意后续恢复。"
        peak = f"，峰值 {mx} bpm" if mx else ""
        out.append((title, f"平均心率 {avg_hr} bpm，约为最大心率（{max_hr}）的 {hr_pct:.0f}%{peak}。{tail}", cls))

    if is_interval:
        # 间歇课看"训练段 vs 恢复段"的对比，比看整体配速极差有意义得多。
        # 分组改成"连续段"后同一类型会出现多组（训练→恢复→训练…），
        # 必须把该类型的**所有组**合起来算，不能只取最后那组。
        all_groups = s.get("segmentGroups") or []

        def merge(t):
            segs = [x for g in all_groups if g["type"] == t for x in g["segments"]]
            return _agg_stats(segs) if segs else None

        ws = merge("work") or merge("interval")
        rs = merge("recovery")
        if ws and ws["count"] and ws.get("paceMinPerKm"):
            msg = (f"训练段 {ws['count']} 组，共 {ws['distanceMeters'] / 1000:.2f} km，"
                   f"平均配速 {fmt_pace(ws['paceMinPerKm'])}/km")
            if ws.get("avgHeartRate"):
                msg += f"，平均心率 {ws['avgHeartRate']} bpm"
            if rs and rs.get("paceMinPerKm"):
                msg += (f"。恢复段 {rs['count']} 组（{fmt_pace(rs['paceMinPerKm'])}/km），"
                        f"快慢差 {abs((rs['paceMinPerKm'] - ws['paceMinPerKm']) * 60):.0f} 秒/公里")
            out.append(("间歇训练结构", msg + "。", "good"))
    elif len(full) >= 2:
        fast = min(full, key=lambda x: x["paceMinPerKm"])
        slow = max(full, key=lambda x: x["paceMinPerKm"])
        spread_s = (slow["paceMinPerKm"] - fast["paceMinPerKm"]) * 60
        # 经验阈值：整公里配速极差 ≤15s 稳定、≤30s 略有起伏，否则波动较大
        title, cls = (("配速控制稳定", "good") if spread_s <= 15 else
                      ("配速略有起伏", "warn") if spread_s <= 30 else ("配速波动较大", "warn"))
        out.append((title, f"整公里中最快第 {fast['km']} km（{fmt_pace(fast['paceMinPerKm'])}），"
                           f"最慢第 {slow['km']} km（{fmt_pace(slow['paceMinPerKm'])}），"
                           f"极差 {spread_s:.0f} 秒/公里（已排除不足 1 km 的尾段）。", cls))

    hr_full = [x for x in full if x.get("avgHeartRate")]
    # 间歇课不适合谈"心率漂移"：热身/冲刺/恢复交替，首末段对比无生理意义
    if len(hr_full) >= 2 and hr_full[0]["avgHeartRate"] and not is_interval:
        a, b = hr_full[0]["avgHeartRate"], hr_full[-1]["avgHeartRate"]
        drift = (b - a) / a * 100
        mins = (s.get("durationSeconds") or 0) / 60
        out.append(("心率漂移可控" if drift < 8 else "心率漂移偏大",
                    f"首公里 {a} bpm → 末个整公里 {b} bpm，漂移 {drift:+.1f}%（{mins:.0f} 分钟跑程）。"
                    f"首公里含热身，仅作参考。", "good" if drift < 8 else "warn"))

    cad, gct, vor = s.get("avgCadence"), s.get("avgContactTimeMs"), s.get("verticalOscillationRatio")
    parts, oks = [], []
    if cad is not None:
        parts.append(f"步频 {cad:.0f} spm（{'已达' if cad >= 180 else '低于'} 180 参考线）"); oks.append(cad >= 180)
    if gct is not None:
        parts.append(f"触地时间 {gct:.0f} ms（{'较短' if gct <= 245 else '偏长'}）"); oks.append(gct <= 245)
    if vor:
        parts.append(f"垂直振幅比 {vor * 100:.1f}%")
    if parts:
        out.append(("跑步经济性" + ("良好" if all(oks) else "有提升空间") if oks else "跑步动力学",
                    "，".join(parts) + "。180 spm / 245 ms 仅为常见参考线，因人而异。",
                    "good" if oks and all(oks) else "warn"))

    vo2, rhr = s.get("vo2Max"), s.get("restingHeartRate")
    if vo2 or rhr:
        bits = ([f"设备估算最大摄氧量 {vo2} ml/kg/min"] if vo2 else []) + \
               ([f"静息心率 {rhr} bpm"] if rhr else [])
        out.append(("体能参考", "，".join(bits) + "。", "good"))
    return out


def build(d: dict) -> str:
    s = d
    avg_pace = s.get("avgPaceMinPerKm")
    dist_km = (s.get("distanceMeters") or 0) / 1000
    max_hr = s.get("userMaxHeartRate") or DEFAULT_MAX_HR
    avg_hr = s.get("avgHeartRate")
    hr_pct = avg_hr / max_hr * 100 if avg_hr else None

    km = s["segments"]
    has_segments = bool(km)
    # 分段按训练类型分组（普通跑步为单组），表格与统计都基于它
    groups = s.get("segmentGroups") or group_segments(km)
    # 间歇训练：段号是"第几圈/第几组"，不是公里
    is_interval = bool(s.get("isInterval"))
    # 统计一律排除不足 1 km 的尾段，否则尾段短跑/心率飙升会污染极差与漂移
    full = [x for x in km if not x.get("partial") and x.get("paceMinPerKm")]

    if hr_pct is None:
        hr_verdict = ""
    elif hr_pct < 70:
        hr_verdict = "轻松有氧区间"
    elif hr_pct < 80:
        hr_verdict = "中等强度，接近节奏跑"
    else:
        hr_verdict = "强度偏高，注意恢复"

    cards = [
        ("距离", f"{dist_km:.2f}", "km", "总里程"),
        ("用时", fmt_duration(s.get("durationSeconds")), "", "净运动时长"),
        ("平均配速", fmt_pace(avg_pace), "/km", "全程均值"),
        ("平均心率", val(avg_hr), "bpm", f"最大 {val(s.get('maxHeartRate'))} bpm"),
        ("步频", val(s.get("avgCadence")), "spm", "每分钟步数"),
        ("步幅", val(s.get("avgStrideCm"), 1), "cm", "平均步幅"),
        ("触地时间", val(s.get("avgContactTimeMs")), "ms", "越低越经济"),
        ("垂直振幅", val(s.get("avgVerticalOscillationCm"), 1), "cm",
         f"比率 {val((s.get('verticalOscillationRatio') or 0) * 100 or None, 1)}%"),
        ("功率", val(s.get("avgPower")), "W", "平均输出"),
        ("卡路里", val(s.get("activeKilocalories")), "kcal", "活动消耗"),
        ("爬升", val(s.get("elevationGain")), "m", "累计上升"),
        ("步数", fmt_num(s.get("steps")), "步", "总步数"),
    ]
    stat_html = "\n".join(
        f'''<div class="stat">
  <div class="stat-label">{esc(label)}</div>
  <div class="stat-value">{esc(value)}<span class="stat-unit">{esc(unit)}</span></div>
  <div class="stat-note">{esc(note)}</div>
</div>''' for label, value, unit, note in cards)

    insight_html = "\n".join(
        f'''<div class="insight {cls}">
  <div class="insight-head">{esc(title)}</div>
  <div class="insight-body">{esc(body)}</div>
</div>''' for title, body, cls in _insights(s, km, full, hr_pct, max_hr))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    activity_id = s.get("activityId") or "—"
    type_label = ACTIVITY_LABELS.get(s.get("activityType"), "跑步")

    # ---- 分段区块：只有「分段明细」表（已按要求移除配速曲线 / 心率区间两个板块）----
    if has_segments:
        n_groups = len(groups)
        group_hint = (f"{n_groups} 个训练分段" if n_groups > 1 else f"{len(km)} 个分段")
        head_cells = "".join(f"<th>{h}</th>" for h in
                             ("段", "用时", "配速", "心率", "步频", "功率 (W)",
                              "触地 (ms)", "步幅 (cm)", "垂直振幅 (cm)", "爬升 (m)"))
        sections_html = f'''
  <section>
    <h2>分段明细<span class="hint">{group_hint}</span></h2>
    <div class="table-scroll">
  <table class="seg">
    <thead><tr>{head_cells}</tr></thead>
    <tbody>
{seg_table(groups)}
    </tbody>
  </table>
    </div>
  </section>'''
    else:
        sections_html = f'''
  <section>
    <h2>分段明细<span class="hint">本次暂无分段数据</span></h2>
    <div class="placeholder">本次未返回分段数据，分段明细暂不可用。<br>
      活动 ID <code>{esc(activity_id)}</code> —— 服务端对最新一次跑步常「当时为空、隔次可取到」，稍后重新拉取并重新渲染即可补上。</div>
  </section>'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="{BRAND_PRIMARY}">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="跑步概况">
<meta name="format-detection" content="telephone=no">
<title>跑步数据卡片 · {esc(s["dateLabel"])} · 跑鸭·RunYay</title>
<style>

  :root {{
    --brand: {BRAND_PRIMARY};
    --brand-dark: {BRAND_DARK};
    --brand-light: {BRAND_LIGHT};
    --ink: #0E2433;
    --muted: #5B7183;
    --line: #E1E9F0;
    --bg: #F4F8FB;
    --radius: 20px;
    /* iPhone 刘海/灵动岛与 Home 指示条安全区 */
    --sat: env(safe-area-inset-top, 0px);
    --sab: env(safe-area-inset-bottom, 0px);
    --sal: env(safe-area-inset-left, 0px);
    --sar: env(safe-area-inset-right, 0px);
  }}
  * {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }}
  body {{
    margin: 0;
    padding: calc(18px + var(--sat)) calc(14px + var(--sar))
             calc(34px + var(--sab)) calc(14px + var(--sal));
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB",
                 "Microsoft YaHei", "Segoe UI", sans-serif;
    background: var(--bg); color: var(--ink);
    -webkit-font-smoothing: antialiased;
    -webkit-tap-highlight-color: transparent;
    overflow-wrap: break-word;
  }}
  .wrap {{ max-width: 1060px; margin: 0 auto; }}

  /* 长数字（配速 5'19"、心率 139）在 iOS 上默认可能被当成电话号码高亮/换行，统一处理 */
  .num, .stat-value, .hero-metric .v, td, th {{ font-variant-numeric: tabular-nums; }}
  a, code {{ -webkit-text-size-adjust: 100%; }}

  .hero {{
    background: linear-gradient(135deg, var(--brand-dark) 0%, var(--brand) 62%, #6FD0FF 100%);
    border-radius: 24px; padding: 22px 20px 20px; color: #fff;
    box-shadow: 0 14px 34px rgba(26,169,248,.26);
    position: relative; overflow: hidden;
  }}
  .hero::after {{
    content: ""; position: absolute; right: -60px; top: -60px;
    width: 200px; height: 200px; border-radius: 50%;
    background: rgba(255,255,255,.11);
  }}
  .brand {{ display: flex; align-items: center; gap: 8px; font-weight: 700;
           font-size: 12px; letter-spacing: .3px; opacity: .96;
           position: relative; z-index: 1; }}
  .brand img {{ width: 18px; height: 18px; border-radius: 5px; background: #fff; padding: 2px; }}
  .hero h1 {{ margin: 11px 0 4px; font-size: 22px; letter-spacing: -.3px;
             position: relative; z-index: 1; }}
  .hero .sub {{ font-size: 13px; opacity: .93; line-height: 1.55; position: relative; z-index: 1; }}
  /* 宽屏（>480px）：指标卡自适应多列，避免两列被拉得过宽 */
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 13px; margin-top: 18px; }}
  .hero-metrics {{ display: flex; flex-wrap: wrap; gap: 34px; margin-top: 22px;
                  position: relative; z-index: 1; }}
  .hero-metric .v {{ font-size: 24px; font-weight: 700; line-height: 1.08;
                    letter-spacing: -.5px; }}
  .hero-metric .v small {{ font-size: 12.5px; font-weight: 600; margin-left: 3px; opacity: .9; }}
  .hero-metric .k {{ font-size: 11.5px; opacity: .88; margin-top: 4px; letter-spacing: .3px; }}
  .chip {{ display: inline-block; margin-top: 18px; padding: 8px 14px; border-radius: 999px;
          background: rgba(255,255,255,.2); font-size: 12px; line-height: 1.4;
          position: relative; z-index: 1; }}

  .stat {{ background: #fff; border: 1px solid var(--line); border-radius: 13px;
          padding: 11px 12px 10px; box-shadow: 0 2px 8px rgba(14,36,51,.045); }}
  .stat-label {{ font-size: 12px; color: var(--muted); letter-spacing: .2px; }}
  .stat-value {{ font-size: 20px; font-weight: 700; margin-top: 4px; line-height: 1.1; }}
  .stat-unit {{ font-size: 11.5px; font-weight: 600; color: var(--muted); margin-left: 3px; }}
  .stat-note {{ font-size: 11px; color: var(--muted); margin-top: 3px; line-height: 1.4; }}

  section {{ background: #fff; border: 1px solid var(--line); border-radius: var(--radius);
            padding: 17px 14px 14px; margin-top: 14px;
            box-shadow: 0 2px 10px rgba(14,36,51,.045); }}
  h2 {{ font-size: 14px; margin: 0 0 3px; letter-spacing: -.1px; }}
  h2 .hint {{ display: block; font-size: 12px; color: var(--muted); font-weight: 400;
             margin: 3px 0 0; }}

  .legend {{ display: flex; gap: 8px 14px; flex-wrap: wrap; font-size: 12px;
            color: var(--muted); margin-top: 9px; line-height: 1.5; }}
  .legend i {{ display: inline-block; width: 11px; height: 11px; border-radius: 3px;
              margin-right: 6px; vertical-align: -1px; }}

  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }}
  th, td {{ padding: 9px 8px; text-align: right; border-bottom: 1px solid var(--line); }}
  th {{ font-size: 11px; color: var(--muted); font-weight: 600; white-space: nowrap;
       background: #FAFCFE; }}
  th:first-child, td:first-child {{ text-align: left; }}
  /* 列序：段 / 用时 / 配速 / 心率 / 步频 / 功率 / 触地 / 步幅 / 垂直振幅 / 爬升 */
  .strong, td:nth-child(3) {{ font-weight: 700; color: var(--brand-dark); }}
  .c-idx {{ font-weight: 600; }}
  .table-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}

  /* ---- 分段明细：父行(组) + 子行(圈)，版式对齐跑鸭 App「训练分段」 ---- */
  table.seg {{ font-size: 12px; }}
  table.seg th {{ font-size: 11px; padding: 0 9px 7px 0; }}
  table.seg td {{ padding: 5px 9px 5px 0; border-bottom: 1px solid #F2F5F9; }}
  table.seg td:first-child {{ padding-left: 2px; }}
  /* 父行：灰底加粗；第一列放「序号 + 类型名 + 组小计」 */
  tr.g td {{ background: #F7F9FC; font-weight: 700; border-top: 1px solid #EDF1F7;
            border-bottom: 1px solid #EDF1F7; white-space: nowrap; }}
  tr.g .c-gidx {{ white-space: normal; }}
  tr.g .g-no {{ color: #3B82F6; font-size: 11.5px; font-weight: 700; margin-right: 5px; }}
  tr.g .g-name {{ font-size: 12.5px; }}
  tr.g .g-sub {{ display: block; font-weight: 500; font-size: 10.5px; color: var(--muted);
                margin-top: 1px; }}
  /* 子行：白底常规字重，序号缩进弱化 */
  tr.s td {{ background: #fff; color: #334155; }}
  tr.s .c-sidx {{ color: #B6C2D2; font-size: 11px; font-weight: 500; padding-left: 9px; }}
  /* 按训练类型着色（对齐 App：热身蓝 / 训练橙 / 恢复绿 / 冷身青） */
  .t-warmup {{ color: #3B82F6; }}
  .t-work, .t-interval {{ color: #F59E0B; }}
  .t-recovery {{ color: #10B981; }}
  .t-cooldown {{ color: #14B8A6; }}
  .t-rest, .t-other {{ color: #64748B; }}
  tr.g .t-warmup, tr.g .t-work, tr.g .t-interval,
  tr.g .t-recovery, tr.g .t-cooldown {{ font-weight: 700; }}

  .insights {{ display: grid; grid-template-columns: 1fr; gap: 10px; margin-top: 12px; }}
  .placeholder {{ margin-top: 11px; padding: 15px 16px; border-radius: 13px;
                 background: #F7FBFE; border: 1px dashed #BFD9EA; color: var(--muted);
                 font-size: 13px; line-height: 1.7; }}
  .placeholder code {{ background: #EAF4FB; padding: 1px 6px; border-radius: 6px;
                      font-size: 12px; color: var(--brand-dark); word-break: break-all; }}
  .insight {{ border-radius: 14px; padding: 13px 14px; border-left: 3.5px solid var(--brand);
             background: #F8FCFF; }}
  .insight.warn {{ border-left-color: #F0A73B; background: #FFFBF3; }}
  .insight.alert {{ border-left-color: #E25C5C; background: #FFF7F7; }}
  .insight-head {{ font-weight: 700; font-size: 13.5px; margin-bottom: 5px; }}
  .insight-body {{ font-size: 12.5px; line-height: 1.65; color: #3A5468; }}

  footer {{ text-align: center; margin-top: 20px; font-size: 11.5px; color: var(--muted);
           line-height: 1.9; }}
  footer .src {{ font-weight: 600; color: var(--brand-dark); }}

  /* ================= iPhone 竖屏（≤480px）=================
     要点：
     1) 11 列宽表在 390px 下溢出 312px —— 改为「每公里一张小卡」的堆叠布局，取消横向滚动；
     2) 用 data-label 保留字段名，信息不丢失；
     3) 字号与触控区按 iOS 习惯放大。 */
  @media (max-width: 480px) {{
    body {{ padding-left: calc(12px + var(--sal)); padding-right: calc(12px + var(--sar)); }}
    section {{ padding: 16px 13px 13px; }}
    .hero {{ padding: 20px 17px 18px; border-radius: 22px; }}
    .hero h1 {{ font-size: 20px; }}
    .hero-metric .v {{ font-size: 22px; }}

    /* 指标卡固定 2 列：390px 宽下比 auto-fit 更省纵向空间、留白更均匀 */
    .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px; margin-top: 16px; }}
    /* 首屏四项核心指标排成整齐的 2×2，不必再往下滚就能看全 */
    .hero-metrics {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 16px 12px; margin-top: 20px; }}

    /* 分段表：保持表格形态（与 App「训练分段」一致），窄屏横向滚动。
       不要改成卡片堆叠 —— 那会破坏父行/子行的分组关系。 */
    .table-scroll {{ overflow-x: auto; margin: 0 -3px; padding-bottom: 2px; }}
    table.seg {{ min-width: 560px; font-size: 12px; }}
    table.seg th {{ padding: 0 9px 7px 0; }}
    table.seg td {{ padding: 5px 9px 5px 0; }}
    tr.g .g-name {{ font-size: 12px; }}
    tr.g .g-sub {{ font-size: 10px; }}
  }}

  /* 极小屏（iPhone SE 等 320~360px）再收一档 */
  @media (max-width: 360px) {{
    .grid {{ gap: 8px; }}
    .stat {{ padding: 11px 12px 10px; }}
    .stat-value {{ font-size: 19px; }}
    .hero-metric .v {{ font-size: 21px; }}
  }}

  /* 横屏 / iPad：回到两列指标卡与紧凑表格 */
  @media (min-width: 481px) {{
    h2 .hint {{ display: inline; margin-left: 8px; }}
  }}

  @media (prefers-reduced-motion: reduce) {{
    * {{ animation: none !important; transition: none !important; }}
  }}
  @media print {{
    body {{ background: #fff; }}
    section, .stat, .hero {{ box-shadow: none; }}
  }}
</style>
</head>
<body>
<div class="wrap">

  <div class="hero">
    <div class="brand">
      <img src="https://yayarun.cn/images/smalllogo.jpg" alt="跑鸭 RunYay" onerror="this.style.display='none'">
      <span>跑鸭 · RunYay</span>
    </div>
    <h1>跑步数据卡片</h1>
    <div class="sub">{esc(s["startTime"])} 起跑 · {esc(type_label)} · {esc(s.get("deviceName") or "—")}</div>
    <div class="hero-metrics">
      <div class="hero-metric"><div class="v">{dist_km:.2f}<small>km</small></div><div class="k">总距离</div></div>
      <div class="hero-metric"><div class="v">{fmt_duration(s.get("durationSeconds"))}</div><div class="k">运动时长</div></div>
      <div class="hero-metric"><div class="v">{fmt_pace(avg_pace)}<small>/km</small></div><div class="k">平均配速</div></div>
      <div class="hero-metric"><div class="v">{val(avg_hr)}<small>bpm</small></div><div class="k">平均心率</div></div>
    </div>
    {f'<div class="chip">心率强度 {hr_pct:.0f}% HRmax · {esc(hr_verdict)}</div>' if hr_pct is not None else ""}
  </div>

  <div class="grid">
{stat_html}
  </div>

{sections_html}

  <section>
    <h2>训练解读</h2>
    <div class="insights">
{insight_html}
    </div>
  </section>

  <footer>
    <div class="src">{esc(ATTRIBUTION)}</div>
    <div>活动 ID {esc(activity_id)} · 卡片生成于 {now}</div>
    <div>本文件为完全离线单文件卡片，除品牌 Logo 外不依赖任何外部资源。</div>
  </footer>

</div>
</body>
</html>
'''


# ---------------------------------------------------------------- 输入适配

def _norm_cadence(v):
    """部分接口把步频放大 100 倍（18000 -> 180）；>=400 视为放大后除以 100。
    注意 1.8E2 只是 180 的科学计数法写法，JSON 解析后就是 180，无需处理。"""
    if v is None:
        return None
    return v / 100.0 if v >= 400 else v


# 训练分段类型：显示名与排序权重（热身 → 训练 → 恢复 → 冷身 → 其他）
INTERVAL_LABELS = {
    "warmup": ("热身", 0),
    "work": ("训练", 1),
    "interval": ("间歇", 1),
    "recovery": ("恢复", 2),
    "cooldown": ("冷身", 3),
    "rest": ("休息", 4),
    "other": ("其他", 9),
}


def _agg_stats(segs):
    """组的汇总：段数 / 总距离 / 总时长 / 组均配速 / 组均心率 / 组均步频。

    组平均配速用"总时长÷总距离"算，比各段配速取平均更贴合实际（各段长短不一）。
    """
    dist = sum(s.get("distanceMeters") or 0 for s in segs)
    dur = sum(s.get("durationSeconds") or 0 for s in segs)
    pace = (dur / 60.0) / (dist / 1000.0) if dist > 0 and dur > 0 else None
    hrs = [s["avgHeartRate"] for s in segs if s.get("avgHeartRate")]
    cads = [s["cadence"] for s in segs if s.get("cadence")]
    return {
        "count": len(segs),
        "distanceMeters": dist,
        "durationSeconds": dur,
        "paceMinPerKm": pace,
        "avgHeartRate": round(sum(hrs) / len(hrs)) if hrs else None,
        "avgCadence": round(sum(cads) / len(cads)) if cads else None,
    }


def group_segments(km):
    """把分段按训练类型切成**连续段**，返回 [{type,label,segments,stats}...]。

    与"按类型归并"不同：这里保持**原始发生顺序**，只把**连续同类型**的圈合并成一组
    （对齐跑鸭 App「训练分段」的父行/子行版式）。例如 9/28：
        热身(2) → 训练(2) → 恢复 → 训练(2) → 恢复 → 训练(2) → 恢复 → 训练(2) → 冷身(3)
    按类型归并会把这 8 个"训练"圈凑成一堆，打乱实际训练节奏，看不出组间恢复。

    没有 intervalType（普通跑步）时全部落在同一组，行为与改动前一致。
    """
    groups = []
    for seg in km:
        t = seg.get("intervalType") or "other"
        if groups and groups[-1]["type"] == t:
            groups[-1]["segments"].append(seg)
        else:
            groups.append({"type": t, "label": INTERVAL_LABELS.get(t, (t, 9))[0],
                           "segments": [seg]})
    for g in groups:
        g["stats"] = _agg_stats(g["segments"])
    return groups


def normalize(raw: dict) -> dict:
    """接受两种输入：本 skill 的规范化结构，或跑鸭 MCP 的原始返回。

    原始返回可能是：
      - {"summary": {...}, "segments": [...]}            (get_run_segments)
      - {"found": true, "summary": {...}}                (get_latest_run_summary)
      - {...summary 顶层字段..., "segments": [...]}
    统一转成 build() 需要的形状。
    """
    warnings = []
    if "segments" in raw and isinstance(raw.get("segments"), list) \
            and "startTime" in raw and "avgPaceMinPerKm" in raw:
        raw.setdefault("_warnings", warnings)
        return raw                                    # 已是规范化结构

    summary = raw.get("summary") or raw.get("latest") or raw
    segs_raw = raw.get("segments") or summary.get("segments") or []

    if not summary or "distanceInMeters" not in summary:
        raise SystemExit("[错误] 输入里找不到跑步摘要（summary/latest）")

    # startTimeInSeconds: "20260929053122" -> "2026-09-29 05:31:22"
    st = str(summary.get("startTimeInSeconds") or "")
    if len(st) >= 14 and st.isdigit():
        start_time = (f"{st[0:4]}-{st[4:6]}-{st[6:8]} "
                      f"{st[8:10]}:{st[10:12]}:{st[12:14]}")
        date_label = f"{st[0:4]}-{st[4:6]}-{st[6:8]}"
    else:
        start_time = st or "—"
        date_label = st[:10] if len(st) >= 10 else "—"

    # 跑鸭一次返回 DISTANCE(按公里) 与 LAP(按圈) 两套分段，二者互补：
    #   DISTANCE 段有配速/心率/爬升，但 power / 触地 / 步幅 / 垂直振幅 常为 null；
    #   LAP 段恰好有这些跑步动力学字段。因此以 DISTANCE 为骨架，用序号对齐的
    #   LAP 段回填缺失项，避免步频/功率图整块空白。
    def _kind(s):
        """同时看 segmentType 与 segmentCategory（文档与样例里两个字段都出现过）。"""
        tags = {str(s.get("segmentType", "")).upper(), str(s.get("segmentCategory", "")).upper()}
        if "DISTANCE" in tags:
            return "DISTANCE"
        if tags & {"LAP", "TRAINING"}:
            return "LAP"
        return None

    laps = [s for s in segs_raw if _kind(s) == "LAP"]
    dists = [s for s in segs_raw if _kind(s) == "DISTANCE"]

    # 训练分段（间歇课）判定：LAP 段带 intervalType，且**不同取值多于一种**时才认为
    # 这是有结构的训练课（如 9/28：warmup×2 / work×8 / recovery×3 / cooldown×3）。
    # 全是 "work" 的普通跑步（如 9/29 的 11 段）不算 —— 那种情况 LAP 与 DISTANCE
    # 是同一份数据的两种切法，需要按序号回填而不是分组。
    lap_intervals = [str(s.get("intervalType") or "").strip().lower() for s in laps]
    distinct = {t for t in lap_intervals if t}
    is_interval = len(laps) > 1 and len(distinct) > 1

    base = laps if is_interval else (dists or laps)
    if segs_raw and not base:
        # 有分段但类型全不认识：不能静默当成"无分段"
        warnings.append(f"收到 {len(segs_raw)} 条分段但无法识别类型，已按无分段处理；请检查 segmentType/segmentCategory")

    def _lap_matches(d_seg, l_seg):
        """按序号回填的前提是"一圈 == 一公里"。间歇跑/手动分圈时序号对不上，宁可不填也不串数据。"""
        dd, ld = d_seg.get("distanceMeters"), l_seg.get("distanceMeters")
        if dd and ld:
            return abs(dd - ld) / dd <= 0.05
        dt, lt = d_seg.get("durationInSeconds"), l_seg.get("durationInSeconds")
        if dt and lt:
            return abs(dt - lt) / dt <= 0.05
        return len(laps) == len(dists)

    by_lap_index = {s.get("segmentIndex"): s for s in laps}

    skipped = []
    km = []
    for s in base:
        # 间歇训练时 base 就是 LAP 本身，不再做 DISTANCE↔LAP 回填（序号体系不同）
        fill = ({} if is_interval
                else by_lap_index.get(s.get("segmentIndex"), {}) if base is dists else {})
        if fill and not _lap_matches(s, fill):
            skipped.append(s.get("segmentIndex"))
            fill = {}

        def pick(*keys):
            for src in (s, fill):
                for k in keys:
                    v = src.get(k)
                    if v is not None:
                        return v
            return None

        pace = pick("avgPace")
        if pace is None:
            spd = pick("avgSpeed")
            # 假设 avgSpeed 为 km/h（60/spd = 分钟/公里）。若接口实为 m/s 应改为 16.6667/spd —— 未经实测，见 SKILL.md
            pace = 60.0 / spd if spd else None

        dur = pick("durationInSeconds")
        dist = pick("distanceMeters")
        if dist is None and pace and dur:
            # 实测接口经常不返回 distanceMeters（DISTANCE/LAP 两侧都可能缺），
            # 用 配速(分钟/公里) × 时长 反推，保证分段表与图表不缺列。
            dist = (dur / 60.0) / pace * 1000.0

        km.append({
            "km": s.get("segmentIndex"),
            "intervalType": (str(s.get("intervalType") or "").strip().lower() or None),
            "distanceMeters": dist,
            "durationSeconds": dur,
            "paceMinPerKm": pace,
            "avgHeartRate": pick("avgHeartRate"),
            "cadence": _norm_cadence(pick("avgCadence")),
            "power": pick("avgPower"),
            "contactTimeMs": pick("averageGroundContactTime"),
            "strideCm": pick("averageStrideLength"),
            "verticalOscillationCm": pick("averageVerticalOscillation"),
            "elevationGain": pick("elevationGain"),
        })

    if skipped:
        warnings.append(f"{len(skipped)} 段（序号 {skipped[0]}…{skipped[-1]}）与 LAP 分圈对不上，"
                        "未回填功率/触地/步幅/垂直振幅（可能是间歇/手动分圈）")

    # 只有"最后一段"才可能是尾段；中间段偏短多半是暂停/数据问题，不能贴"尾段"标签。
    # 间歇训练下不适用：每段本来就长短不一，标"尾段"没有意义。
    if km and not is_interval and km[-1].get("distanceMeters") and km[-1]["distanceMeters"] < 950:
        km[-1]["partial"] = True

    dur_s, dist_m = summary.get("durationInSeconds"), summary.get("distanceInMeters")
    avg_pace = summary.get("averagePace")
    if avg_pace is None and dur_s and dist_m:
        avg_pace = (dur_s / 60.0) / (dist_m / 1000.0)  # 摘要缺配速时反推（分钟/公里）

    loc = {}
    if summary.get("startLatitude"):
        loc = {"lat": summary["startLatitude"], "lon": summary.get("startLongitude")}

    return {
        "source": "跑鸭·RunYay",
        "activityId": summary.get("activityId"),
        "activityType": summary.get("activityType", "or"),
        "startTime": start_time,
        "dateLabel": date_label,
        "durationSeconds": summary.get("durationInSeconds"),
        "distanceMeters": summary.get("distanceInMeters"),
        "avgPaceMinPerKm": avg_pace,
        "avgHeartRate": summary.get("averageHeartRate"),
        "maxHeartRate": summary.get("maxHeartRate"),
        "avgCadence": _norm_cadence(summary.get("averageRunCadence")),
        "avgContactTimeMs": summary.get("averageContactTime"),
        "avgPower": summary.get("averagePower"),
        "avgStrideCm": summary.get("averageStrideLength"),
        "avgVerticalOscillationCm": summary.get("averageVerticalOscillation"),
        "verticalOscillationRatio": summary.get("averageVerticalOscillationRatio"),
        "steps": summary.get("steps"),
        "activeKilocalories": summary.get("activeKilocalories"),
        "elevationGain": summary.get("totalElevationGain"),
        "deviceName": summary.get("deviceName"),
        "restingHeartRate": summary.get("restingHeartRate"),
        "userMaxHeartRate": summary.get("userMaxHeartRate"),
        "vo2Max": summary.get("vo2Max"),
        "location": loc,
        "segments": km,
        # 按 intervalType 分组（普通跑步为单组）；渲染与统计都以它为准
        "segmentGroups": group_segments(km),
        "isInterval": is_interval,
        "_warnings": warnings,
    }


def selfcheck(html_text: str) -> list:
    """产出后自检：标签闭合 / SVG 越界 / None|NaN 泄漏。"""
    from html.parser import HTMLParser

    void = {"meta", "img", "br", "hr", "input", "line", "rect", "circle",
            "polyline", "polygon", "stop", "path", "use"}
    problems = []

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []

        def handle_starttag(self, tag, attrs):
            if tag not in void:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if tag in void:
                return
            if not self.stack or self.stack[-1] != tag:
                problems.append(f"标签不匹配 </{tag}>")
            elif self.stack:
                self.stack.pop()

    p = P()
    p.feed(html_text)
    if p.stack:
        problems.append(f"未闭合标签: {p.stack[:5]}")

    for i, svg in enumerate(re.findall(r"<svg.*?</svg>", html_text, re.S), 1):
        vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        if not vb:
            continue
        w, h = float(vb.group(1)), float(vb.group(2))
        for pts in re.findall(r'<polyline points="([^"]+)"', svg):
            for pair in pts.split():
                x, y = (float(v) for v in pair.split(","))
                if not (0 <= x <= w and 0 <= y <= h):
                    problems.append(f"SVG{i} 折线越界 ({x:.0f},{y:.0f})")

    # 只在去掉标签/样式后的可见文本里按整词查；原版对整份 HTML 做子串匹配，
    # "nan" 会误伤 Finance / nano 之类的词
    visible = re.sub(r"<style.*?</style>|<[^>]+>", " ", html_text, flags=re.S)
    for token in re.findall(r"\b(?:None|NaN|nan|inf|undefined)\b", visible):
        problems.append(f"疑似泄漏值: {token}")
    return problems


def main():
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"):
        print("用法: render_card.py <输入.json> <输出.html>\n\n"
              "输入可以是 fetch_data.py 落盘的 latest.json，也可以是跑鸭 MCP 的原始返回。")
        return 0 if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help") else 1
    src = Path(sys.argv[1]).expanduser()
    dst = Path(sys.argv[2]).expanduser()
    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[失败] 读不了输入 {src}: {exc}", file=sys.stderr)
        return 1
    try:
        data = normalize(raw)
        out = build(data)
    except (SystemExit, KeyError, TypeError, ValueError) as exc:
        print(f"[失败] 渲染出错（输入结构不符合预期）: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for w in data.get("_warnings", []):
        print(f"[警告] {w}", file=sys.stderr)
    if not data.get("segments"):
        print("[提示] 没有分段数据 —— 卡片将显示占位说明（属正常情况）")

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")           # 先写临时文件再替换：中途失败不留半截卡片
    tmp.write_text(out, encoding="utf-8")
    problems = selfcheck(out)
    if problems:
        print(f"  [自检发现问题] {'; '.join(problems[:5])}  —— 未覆盖 {dst.name}，问题输出保留在 {tmp.name}",
              file=sys.stderr)
        return 1
    tmp.replace(dst)

    print(f"已写入 {dst} ({dst.stat().st_size:,} bytes)")
    print(f"  日期 {data['dateLabel']} | 分段 {len(data['segments'])} 条 | 图表 {out.count('<svg')} 张")
    print("  自检通过：标签闭合 / SVG 未越界 / 无 None·NaN 泄漏（未做视觉截图核验）")
    return 0


if __name__ == "__main__":
    sys.exit(main())