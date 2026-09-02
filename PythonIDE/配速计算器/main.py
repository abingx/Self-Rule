import appui

FULL = 42.195
HALF = 21.0975

# 显式持久状态：persist_key 固定，5 个输入字段会自动写入持久化存储，
# 每次启动恢复上次的最后输入，避免默认值不一致。
state = appui.PersistentState(
    persist_key="app.paces.calculator.v1",
    # 目标配速（分:秒）
    pace_min="6",
    pace_sec="00",
    # 目标用时（时:分:秒）
    time_h="4",
    time_m="00",
    time_s="00",
)

# 最近一次提交计算的基准快照：(起点方向, 用时秒, 每公里配速秒)
# 属纯内存瞬态数据，不入持久化，避免 tuple 序列化问题。
_committed = None


# 官方双向绑定：绑定对象带原生 setter，用户输入即写回 state，
# 不会走「受控值 + on_change」导致的重建回退（首次编辑数字被吞回旧值）。
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


def to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def fmt_seconds(total_sec):
    total_sec = max(0, int(round(total_sec)))
    h, rem = divmod(total_sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_pace(sec_per_km):
    sec_per_km = max(0, int(round(sec_per_km)))
    m, s = divmod(sec_per_km, 60)
    return f"{m:.0f}'{s:02d}\""


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


# ---- 动态联动：改配速更新用时，改用时更新配速 ----
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
    state.time_h = str(h)
    state.time_m = str(m)
    state.time_s = str(s)


def update_from_time():
    """输入目标用时反推配速，并将每公里秒数向下取整。

    例如目标用时 3:00:00（10800 秒）:
    pace = 10800 / 42.195 ≈ 255.954497 秒/公里，
    向下取整为 255 秒，即 4:15/公里；全程用时约为 2:59:20，
    不超过目标用时。
    """
    target = current_time_seconds()
    if target <= 0:
        return
    pace_sec_per_km = target / FULL
    pmin = int(pace_sec_per_km // 60)
    psec = int(pace_sec_per_km % 60)
    if psec >= 60:
        pmin += 1
        psec -= 60
    state.pace_min = str(pmin)
    state.pace_sec = f"{psec:02d}"


def _blank_to_zero():
    """空输入框先补为 '0' 再计算，并回写为可见的 '0'。"""
    for k in ("pace_min", "pace_sec", "time_h", "time_m", "time_s"):
        v = getattr(state, k)
        if str(v).strip() == "":
            setattr(state, k, "0")


def compute(source):
    """以最后触发提交的输入框所在区域(source)为起点换算。

    source: "pace"（目标配速）或 "time"（目标用时）。
    起点区域有值时以它为基准反推另一区域；起点为空(0)则退回另一区域。
    用法时换算配速时，保证秒数向下取整且不超过 59。
    """
    global _committed
    _blank_to_zero()
    if source == "pace":
        pace = current_pace_seconds()
        if pace > 0:
            update_from_pace()          # 以配速反推用时
        else:
            update_from_time()          # 配速为空，退回用时反推配速
    else:  # source == "time"
        target = current_time_seconds()
        if target > 0:
            update_from_time()          # 以用时反推配速
        else:
            update_from_pace()          # 用时为空，退回配速反推用时

    _committed = _snapshot()      # 记录本次计算基准


def _snapshot():
    pace = current_pace_seconds()
    target = current_time_seconds()
    if pace > 0:
        return ("pace", int(pace * FULL), pace)
    if target > 0:
        return ("time", target, target / FULL)
    return None


def current_compute():
    # 优先使用最近一次提交的基准，避免编辑中的另一区域被误用做起点
    if _committed:
        kind, finish, pace = _committed
        return (kind, finish, pace)
    return _snapshot()


def split_section(title, splits):
    rows = []
    for label, v in splits:
        rows.append(
            appui.HStack([
                # 分段名颜色与目标配速标签一致（label）
                appui.Text(label).foreground_color("label"),
                appui.Text(fmt_seconds(v))
                    .frame(max_width=appui.infinity, alignment="trailing"),
            ], spacing=6)
        )
    return appui.Section(title, rows, header_padding=4)


FIELD_WIDTH = 40   # 所有输入框统一宽度
LABEL_WIDTH = 88   # 标签固定宽度，使各行输入组左侧起点对齐


def time_field(bind, placeholder, source):
    """统一输入框：无边框填充，自动适配深浅色模式。
    使用 state.bind(field) 双向绑定，输入即写回 state（不重建回退）。
    换行(提交)时以本框所在区域(source)为起点触发 compute。"""
    return (
        appui.TextField(placeholder, text=bind,
                        on_submit=lambda: compute(source),
                        keyboard_type="number_pad")
        .multiline_text_alignment("center")
        .tint("label")
        .background("secondarySystemFill", corner_radius=8)
        .frame(width=FIELD_WIDTH, height=28)
    )


def separ_colon():
    return (appui.Text(":")
            .foreground_color("label"))


def input_row(label, fields):
    """同一行：固定宽度标签 + 弹性占位 + 字段输入（框间用 ':' 分隔）。
    字段输入组靠右对齐，使两行中同为'分/秒/时'的输入框对齐（秒对秒、分对分）。"""
    row = [appui.Text(label).foreground_color("label")
           .frame(width=LABEL_WIDTH, alignment="leading")]
    # 弹性占位：把字段输入组推到最右侧，实现右对齐
    row.append(appui.Text("").frame(max_width=appui.infinity))
    for i, item in enumerate(fields):
        if i > 0:
            row.append(separ_colon())
        row.append(item)
    return appui.HStack(row, spacing=4).frame(max_width=appui.infinity)


def root():
    r = current_compute()

    main = [appui.Section([
        input_row("目标配速", [
            time_field(bind_pace_min, "分", "pace"),
            time_field(bind_pace_sec, "秒", "pace"),
        ]),
        input_row("目标用时", [
            time_field(bind_time_h, "时", "time"),
            time_field(bind_time_m, "分", "time"),
            time_field(bind_time_s, "秒", "time"),
        ]),
    ])]

    if r:
        _kind, _finish, _pace = r
        main.append(split_section("分段用时", [
            (label, _pace * km) for label, km in split_distances()
        ]))
    else:
        main.append(appui.Section([
            appui.Text("请输入有效的配速或用时").foreground_color("secondary"),
        ]))

    return appui.Form(main, spacing=4)


appui.run(root, state=state, presentation="fullscreen_with_close")