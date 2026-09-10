import appui

FULL = 42.195
HALF = 21.0975

# 默认值互相自洽：6'00"/公里 对应全程 4:13:10。
state = appui.PersistentState(
    persist_key="app.paces.calculator.v1",
    pace_min="6",
    pace_sec="00",
    time_h="4",
    time_m="13",
    time_s="10",
)

# state.bind 返回的 Binding 可直接传给 TextField.text。
bind_pace_min = state.bind("pace_min")
bind_pace_sec = state.bind("pace_sec")
bind_time_h = state.bind("time_h")
bind_time_m = state.bind("time_m")
bind_time_s = state.bind("time_s")


def to_int(v):
    try:
        return max(0, int(float(v)))
    except (TypeError, ValueError):
        return 0


def fmt_seconds(total_sec):
    total_sec = max(0, int(round(total_sec)))
    h, rem = divmod(total_sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def split_distances():
    return [
        ("5 公里", 5),
        ("10 公里", 10),
        ("15 公里", 15),
        ("20 公里", 20),
        ("半程", HALF),
        ("25 公里", 25),
        ("30 公里", 30),
        ("35 公里", 35),
        ("40 公里", 40),
        ("全程", FULL),
    ]


def current_pace_seconds():
    return to_int(state.pace_min) * 60 + to_int(state.pace_sec)


def current_time_seconds():
    return to_int(state.time_h) * 3600 + to_int(state.time_m) * 60 + to_int(state.time_s)


def update_from_pace():
    pace = current_pace_seconds()
    if pace <= 0:
        return
    finish = int(round(pace * FULL))
    h, rem = divmod(finish, 3600)
    m, s = divmod(rem, 60)
    state.batch_update(time_h=str(h), time_m=str(m), time_s=str(s))


def update_from_time():
    """用时反推配速，每公里秒数向下取整。

    例如 3:00:00（10800 秒）：10800 / 42.195 ≈ 255.95 秒/公里，
    取 255 秒即 4:15/公里，全程约 2:59:20，不超过目标用时。
    """
    target = current_time_seconds()
    if target <= 0:
        return
    pace_sec_per_km = target / FULL
    pmin = int(pace_sec_per_km // 60)
    psec = int(pace_sec_per_km % 60)
    state.batch_update(pace_min=str(pmin), pace_sec=f"{psec:02d}")


def _blank_to_zero():
    """空输入补 0 并回写，使 '0' 在界面上可见。"""
    updates = {}
    for k in ("pace_min", "pace_sec", "time_h", "time_m", "time_s"):
        if str(getattr(state, k)).strip() == "":
            updates[k] = "0"
    if updates:
        state.batch_update(**updates)


def compute(source):
    """以 source 区域为起点换算；该区域为空(0)时退回另一区域。

    source: "pace" 或 "time"。
    """
    _blank_to_zero()
    if source == "pace":
        pace = current_pace_seconds()
        if pace > 0:
            update_from_pace()
        else:
            update_from_time()
    else:
        target = current_time_seconds()
        if target > 0:
            update_from_time()
        else:
            update_from_pace()


# _value 仅为兼容桥回传新文本，回调不使用该参数。
def submit_pace(_value=None):
    compute("pace")


def submit_time(_value=None):
    compute("time")


def split_section(title, splits):
    rows = []
    for label, v in splits:
        rows.append(
            appui.HStack([
                appui.Text(label).foreground_color("label"),
                appui.Text(fmt_seconds(v))
                    .frame(max_width=appui.infinity, alignment="trailing"),
            ], spacing=6)
        )
    return appui.Section(title, rows)


FIELD_WIDTH = 40
LABEL_WIDTH = 88   # 标签定宽，使两行输入组左侧对齐


def time_field(bind, placeholder, submit_action):
    """回车/换行提交时，以本框所在区域为起点换算。"""
    return (
        appui.TextField(placeholder, text=bind,
                        on_submit=submit_action,
                        keyboard_type="numberPad")
        .multiline_text_alignment("center")
        .tint("label")
        .background("secondarySystemBackground", corner_radius=8)
        .frame(width=FIELD_WIDTH, height=28)
    )


def separ_colon():
    return (appui.Text(":")
            .foreground_color("label"))


def input_row(label, fields):
    """标签定宽 + 弹性占位 + 右侧字段组，使两行的分/秒/时纵向对齐。"""
    row = [appui.Text(label).foreground_color("label")
           .frame(width=LABEL_WIDTH, alignment="leading")]
    row.append(appui.Spacer())
    for i, item in enumerate(fields):
        if i > 0:
            row.append(separ_colon())
        row.append(item)
    return appui.HStack(row, spacing=4).frame(max_width=appui.infinity)


def root():
    # 分段用时始终以配速为基准。
    pace = current_pace_seconds()

    main = [
        appui.Section("输入", [
            input_row("目标配速", [
                time_field(bind_pace_min, "分", submit_pace),
                time_field(bind_pace_sec, "秒", submit_pace),
            ]),
            input_row("目标用时", [
                time_field(bind_time_h, "时", submit_time),
                time_field(bind_time_m, "分", submit_time),
                time_field(bind_time_s, "秒", submit_time),
            ]),
        ]),
    ]

    if pace > 0:
        main.append(split_section("分段用时", [
            (label, pace * km) for label, km in split_distances()
        ]))
    else:
        main.append(appui.Section("分段用时", [
            appui.Text("请输入有效的配速或用时").foreground_color("secondaryLabel"),
        ]))

    return appui.NavigationStack(
        appui.Form(main).navigation_title("配速计算器")
    )


appui.run(root, state=state, presentation="fullscreen_with_close")
