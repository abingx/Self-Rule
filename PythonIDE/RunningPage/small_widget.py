# Small Widget — Running Stats
# 跑步统计小尺寸组件（PythonIDE-iOS / widget DSL）

from widget import Widget

# ── 数据 ──────────────────────────────────────────────────────────
data = {
    "today":  {"distance": 12.34, "count": 1},
    "week":   {"distance": 34.12, "count": 3},
    "month":  {"distance": 201.12, "count": 19},
    "year":   {"distance": 2123.56, "count": 201},
    "latest": "2026/04/09 07:30",
}

# ── 配色（完全对应 common.js getTheme） ───────────────────────────
TEXT_TITLE = ("#ffffff", "#e9ecef")
TEXT_LABEL = ("#ffffff", "#adb5bd")
TEXT_VALUE = "#ffffff"
TEXT_TIME  = ("#ffffff", "#e9ecef")
BOX_BG     = "#ffffff"

# ── 构建组件 ──────────────────────────────────────────────────────
w = Widget(background={"gradient": ["#5568d3", "#6b4fa0", "#d946ef"], "direction": "vertical"})

with w.vstack(spacing=0, padding=6):

    # ① 头部：Running + 🏃‍♂️
    with w.hstack(spacing=0):
        w.text("Running", size=15, weight="bold", color=TEXT_TITLE,
               align="leading", frame={"width": 110})
        w.emoji("🏃‍♂️", size=15)

    w.spacer(length=2)

    # ② 今日距离
    with w.vstack(spacing=0, align="center"):
        w.text("Today", size=10, weight="bold", color=TEXT_LABEL, align="center")
        w.text(f"{data['today']['distance']:.2f}",
               size=26, weight="bold", color=TEXT_VALUE,
               align="center", max_lines=1)

    w.spacer(length=2)

    # ③ 周 / 月 / 年 三列卡片
    with w.hstack(spacing=4):
        for label, key in [("WEEK", "week"), ("MONTH", "month"), ("YEAR", "year")]:
            with w.card(background=BOX_BG, corner_radius=6,
                        padding=3, spacing=2, opacity=0.15):
                w.text(label,
                       size=7, weight="bold", color=TEXT_LABEL, align="center")
                w.text(str(data[key]["count"]),
                       size=7, weight="bold", color=TEXT_VALUE, align="center")
                w.text(f"{data[key]['distance']:.2f}",
                       size=7, weight="bold", color=TEXT_VALUE, align="center")

    w.spacer(length=2)

    # ④ 时间戳
    w.text(f"Latest: {data['latest']}",
           size=6, design="monospaced", color=TEXT_TIME, align="center")

w.render()
