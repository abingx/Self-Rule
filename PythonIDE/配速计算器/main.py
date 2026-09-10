import appui
import device

MARATHON = 42.095
HALF_MARATHON = 21.0975

PROJECTS = [
    ("马拉松", MARATHON),
    ("半马", HALF_MARATHON),
    ("10K", 10),
    ("5K", 5),
]
PROJECT_NAMES = [name for name, _ in PROJECTS]
PROJECT_DISTANCES = dict(PROJECTS)
DEFAULT_PROJECT = "马拉松"

SPLITS = [
    ("5K", 5),
    ("10K", 10),
    ("15K", 15),
    ("20K", 20),
    ("半马", HALF_MARATHON),
    ("25K", 25),
    ("30K", 30),
    ("35K", 35),
    ("40K", 40),
    ("全马", MARATHON),
]

# 屏幕自适应：启动时读一次屏高（点），按屏高缩放字号、行高与输入框，整页不滚动即可显示。
try:
    SCREEN_HEIGHT = float(device.screen_height())
except (AttributeError, TypeError, ValueError):
    SCREEN_HEIGHT = 844.0

BASE_HEIGHT = 844.0                                  # 基准屏高（iPhone 13/14），该屏不缩字号
SCALE = min(1.0, max(0.7, SCREEN_HEIGHT / BASE_HEIGHT))

FONT_BODY = round(15 * SCALE, 1)
FIELD_WIDTH = round(40 * SCALE, 1)
FIELD_HEIGHT = round(28 * SCALE, 1)
CORNER_RADIUS = round(8 * SCALE, 1)

SPLIT_COLUMN_GAP = round(90 * SCALE, 1)    # 左右两列之间的固定间距
SPLIT_CELL_GAP = round(4 * SCALE, 1)       # 分段名与时间之间的最小间距

# 默认值互相自洽：6'00"/公里 对应全马 4:12:34。
state = appui.PersistentState(
    persist_key="app.paces.calculator.v1",
    project=DEFAULT_PROJECT,
    pace_min="6",
    pace_sec="00",
    time_h="4",
    time_m="12",
    time_s="34",
)

# 旧数据里若存有已改名的项目，回落到默认项目，避免下拉框无选中项。
if state.project not in PROJECT_NAMES:
    state.project = DEFAULT_PROJECT

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


def current_pace_seconds():
    return to_int(state.pace_min) * 60 + to_int(state.pace_sec)


def current_time_seconds():
    return to_int(state.time_h) * 3600 + to_int(state.time_m) * 60 + to_int(state.time_s)


def project_distance():
    return PROJECT_DISTANCES.get(state.project, MARATHON)


def time_fields(pace, km):
    finish = int(round(pace * km))
    h, rem = divmod(finish, 3600)
    m, s = divmod(rem, 60)
    return {"time_h": str(h), "time_m": str(m), "time_s": str(s)}


def update_from_pace():
    pace = current_pace_seconds()
    if pace <= 0:
        return
    state.batch_update(**time_fields(pace, project_distance()))


def update_from_time():
    """用时反推配速，每公里秒数向下取整，使换算结果不超过目标用时。"""
    target = current_time_seconds()
    if target <= 0:
        return
    pace_sec_per_km = target / project_distance()
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


def set_project(value):
    """切换项目：按新距离重算用时，与项目一次提交避免中间态。"""
    pace = current_pace_seconds()
    if pace > 0:
        state.batch_update(project=value, **time_fields(
            pace, PROJECT_DISTANCES.get(value, MARATHON)))
    else:
        state.project = value
        update_from_time()


def split_cell(label, km, pace, limit):
    """单元内分段名靠左、时间靠右，两者自动分配单元宽度。"""
    color = "secondaryLabel" if km > limit else "label"
    return appui.HStack([
        appui.Text(label).font(size=FONT_BODY).foreground_color(color),
        appui.Text(fmt_seconds(pace * km))
            .font(size=FONT_BODY)
            .foreground_color(color)
            .frame(max_width=appui.infinity, alignment="trailing"),
    ], spacing=SPLIT_CELL_GAP).frame(max_width=appui.infinity)


def split_section(title, pace, limit):
    """分段按配速换算，超出所选项目距离的分段整行以灰色显示。

    系统行高固定（约 49pt，与字号无关），10 行放不进一屏，故两列并排、先竖排。
    """
    half = len(SPLITS) // 2
    rows = []
    for left, right in zip(SPLITS[:half], SPLITS[half:]):
        rows.append(appui.HStack([
            split_cell(*left, pace, limit),
            split_cell(*right, pace, limit),
        ], spacing=SPLIT_COLUMN_GAP))
    return appui.Section(title, rows)


def time_field(bind, placeholder, submit_action):
    """回车/换行提交时，以本框所在区域为起点换算。"""
    return (
        appui.TextField(placeholder, text=bind,
                        on_submit=submit_action,
                        keyboard_type="numberPad")
        .font(size=FONT_BODY)
        .multiline_text_alignment("center")
        .frame(width=FIELD_WIDTH, height=FIELD_HEIGHT)
        .background("secondarySystemBackground", corner_radius=CORNER_RADIUS)
        .tint("label")
    )


def separ_colon():
    return (appui.Text(":")
            .font(size=FONT_BODY)
            .foreground_color("label"))


def labeled_row(label, fields):
    """原生 LabeledContent 排布：标签与分区标题同源对齐，字段组靠行尾。"""
    row = [appui.Spacer()]
    for i, item in enumerate(fields):
        if i > 0:
            row.append(separ_colon())
        row.append(item)
    return (appui.LabeledContent(label, content=appui.HStack(row, spacing=4))
            .font(size=FONT_BODY))


def root():
    # 分段用时始终以配速为基准。
    pace = current_pace_seconds()
    limit = project_distance()

    main = [
        appui.Section("目标", [
            labeled_row("项目", [
                appui.Picker(selection=state.project,
                             options=PROJECT_NAMES,
                             on_change=set_project).tint("label"),
            ]),
            labeled_row("配速", [
                time_field(bind_pace_min, "分", submit_pace),
                time_field(bind_pace_sec, "秒", submit_pace),
            ]),
            labeled_row("用时", [
                time_field(bind_time_h, "时", submit_time),
                time_field(bind_time_m, "分", submit_time),
                time_field(bind_time_s, "秒", submit_time),
            ]),
        ]),
    ]

    if pace > 0:
        main.append(split_section("分段", pace, limit))
    else:
        main.append(appui.Section("分段", [
            appui.Text("请输入有效的配速或用时")
                .font(size=FONT_BODY)
                .foreground_color("secondaryLabel"),
        ]))

    # 分区表头由系统渲染、无法单独设字号，故在根视图统一注入字号，令全页同号。
    return appui.NavigationStack(
        appui.Form(main).font(size=FONT_BODY).navigation_title("配速计算器")
    )


appui.run(root, state=state, presentation="fullscreen_with_close")
