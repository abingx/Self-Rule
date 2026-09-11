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

# 各项目的分段：马拉松/半马共用固定分段，10K/5K 按每公里；超出所选项目的分段灰显。
MARATHON_SPLITS = [
    ("5K", 5), ("10K", 10), ("15K", 15), ("20K", 20), ("半马", HALF_MARATHON),
    ("25K", 25), ("30K", 30), ("35K", 35), ("40K", 40), ("全马", MARATHON),
]
PER_KM_SPLITS = [(f"{i}K", i) for i in range(1, 11)]
SPLITS_BY_PROJECT = {
    "马拉松": MARATHON_SPLITS,
    "半马": MARATHON_SPLITS,
    "10K": PER_KM_SPLITS,
    "5K": PER_KM_SPLITS,
}

# 滚轮选项统一两位显示
HOUR_OPTIONS = [f"{i:02d}" for i in range(0, 24)]
MINUTE_OPTIONS = [f"{i:02d}" for i in range(0, 60)]
SECOND_OPTIONS = [f"{i:02d}" for i in range(0, 60)]

# 按屏高缩放字号与输入框，使整页不滚动即可显示。
try:
    SCREEN_HEIGHT = float(device.screen_height())
    SCREEN_WIDTH = float(device.screen_width())
except (AttributeError, TypeError, ValueError):
    SCREEN_HEIGHT = 844.0
    SCREEN_WIDTH = 390.0

BASE_HEIGHT = 844.0                                  # 基准屏高（iPhone 13/14），该屏不缩字号
SCALE = min(1.0, max(0.7, SCREEN_HEIGHT / BASE_HEIGHT))

FONT_BODY = round(16 * SCALE, 1)
FIELD_WIDTH = round(40 * SCALE, 1)
FIELD_HEIGHT = round(28 * SCALE, 1)
CORNER_RADIUS = round(8 * SCALE, 1)

# 左右两列间距占屏宽比例：23%（即 iPhone 14 上 90pt / 390pt），按需直接改这个比例
SPLIT_COLUMN_GAP_RATIO = 0.23
SPLIT_COLUMN_GAP = round(SCREEN_WIDTH * SPLIT_COLUMN_GAP_RATIO, 1)
SPLIT_CELL_GAP = round(4 * SCALE, 1)       # 分段名与时间之间的最小间距

# 默认值互相自洽：06'00"/公里 对应全马 04:12:34。
# sheet_kind/show_sheet 只描述弹层会话，不入持久化。
state = appui.PersistentState(
    persist_key="app.paces.calculator.v1",
    transient=["sheet_kind", "show_sheet"],
    project=DEFAULT_PROJECT,
    pace_min="06",
    pace_sec="00",
    time_h="04",
    time_m="12",
    time_s="34",
    sheet_kind="pace",
    show_sheet=False,
)

bind_show_sheet = state.bind("show_sheet")


def to_int(v):
    try:
        return max(0, int(float(v)))
    except (TypeError, ValueError):
        return 0


# 旧数据归一到滚轮选项（两位数字），项目改名后回落默认项目。
if state.project not in PROJECT_NAMES:
    state.project = DEFAULT_PROJECT
state.pace_min = f"{min(to_int(state.pace_min), 59):02d}"
state.pace_sec = f"{min(to_int(state.pace_sec), 59):02d}"
state.time_h = f"{min(to_int(state.time_h), 23):02d}"
state.time_m = f"{min(to_int(state.time_m), 59):02d}"
state.time_s = f"{min(to_int(state.time_s), 59):02d}"


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
    return {"time_h": f"{h:02d}", "time_m": f"{m:02d}", "time_s": f"{s:02d}"}


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
    state.batch_update(pace_min=f"{pmin:02d}", pace_sec=f"{psec:02d}")


def compute(source):
    """以 source 区域为起点换算；该区域为空(0)时退回另一区域。

    source: "pace" 或 "time"。
    """
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


# 滚轮改动即写回状态并换算另一区域
def set_pace_min(value):
    state.pace_min = value
    compute("pace")


def set_pace_sec(value):
    state.pace_sec = value
    compute("pace")


def set_time_h(value):
    state.time_h = value
    compute("time")


def set_time_m(value):
    state.time_m = value
    compute("time")


def set_time_s(value):
    state.time_s = value
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


def open_pace_sheet():
    state.batch_update(sheet_kind="pace", show_sheet=True)


def open_time_sheet():
    state.batch_update(sheet_kind="time", show_sheet=True)


def value_box(text):
    """只读显示框，外观沿用原来的输入框样式。"""
    return (appui.Text(text)
            .multiline_text_alignment("center")
            .frame(width=FIELD_WIDTH, height=FIELD_HEIGHT)
            .background("secondarySystemBackground", corner_radius=CORNER_RADIUS)
            .foreground_color("label"))


def separ_colon():
    return appui.Text(":").foreground_color("label")


def field_group(fields):
    """框间以 ':' 分隔，整组靠行尾。"""
    row = [appui.Spacer()]
    for i, item in enumerate(fields):
        if i > 0:
            row.append(separ_colon())
        row.append(item)
    return appui.HStack(row, spacing=4)


def labeled_row(label, fields):
    return appui.LabeledContent(label, content=field_group(fields))


def pace_row():
    """配速行：只读显示，点击整行选择分/秒。"""
    return (appui.LabeledContent(
        "配速", content=field_group([
            value_box(state.pace_min), value_box(state.pace_sec)]))
        .on_tap(open_pace_sheet))


def time_row():
    """用时行：只读显示，点击整行选择时/分/秒。"""
    return (appui.LabeledContent(
        "用时", content=field_group([
            value_box(state.time_h), value_box(state.time_m), value_box(state.time_s)]))
        .on_tap(open_time_sheet))


def sheet_content():
    """弹层内容：按 sheet_kind 显示对应的滚轮组（传给 sheet 的命名函数）。"""
    if state.sheet_kind == "pace":
        title = "目标配速（分 : 秒）"
        wheels = [(MINUTE_OPTIONS, state.pace_min, set_pace_min),
                  (SECOND_OPTIONS, state.pace_sec, set_pace_sec)]
    else:
        title = "目标用时（时 : 分 : 秒）"
        wheels = [(HOUR_OPTIONS, state.time_h, set_time_h),
                  (MINUTE_OPTIONS, state.time_m, set_time_m),
                  (SECOND_OPTIONS, state.time_s, set_time_s)]
    return appui.VStack([
        appui.Text(title).foreground_color("secondaryLabel"),
        appui.HStack([
            appui.WheelPicker(options=options, selection=value, on_change=on_change)
            for options, value, on_change in wheels
        ], spacing=8),
        # system_image 传空串会回落到默认的 xmark；这里用无效符号名占位以隐藏图标
        appui.CloseButton("完成", system_image=" ").button_style("bordered"),
    ], spacing=8)


def split_cell(label, km, pace, limit):
    """两列单元：分段名靠左、时间靠右；超出所选项目的分段整格灰显。"""
    color = "secondaryLabel" if km > limit else "label"
    return appui.HStack([
        appui.Text(label).foreground_color(color),
        appui.Text(fmt_seconds(pace * km))
            .foreground_color(color)
            .frame(max_width=appui.infinity, alignment="trailing"),
    ], spacing=SPLIT_CELL_GAP).frame(max_width=appui.infinity)


def split_section(title, pace, limit):
    """分段按配速换算，统一两列先竖排（左半 / 右半）。"""
    items = SPLITS_BY_PROJECT.get(state.project, MARATHON_SPLITS)
    half = len(items) // 2
    rows = [appui.HStack([split_cell(*left, pace, limit),
                          split_cell(*right, pace, limit)],
                         spacing=SPLIT_COLUMN_GAP)
            for left, right in zip(items[:half], items[half:])]
    return appui.Section(title, rows)


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
            pace_row(),
            time_row(),
        ]),
    ]

    if pace > 0:
        main.append(split_section("分段", pace, limit))
    else:
        main.append(appui.Section("分段", [
            appui.Text("请输入有效的配速或用时").foreground_color("secondaryLabel"),
        ]))

    # 字号在根视图统一注入，系统分区表头也随之同号。
    # 呈现修饰符必须挂在根视图上，content 传命名函数。
    return (appui.NavigationStack(
        appui.Form(main)
        .font(size=FONT_BODY)
        .navigation_title("配速计算器")
        .navigation_bar_title_display_mode("inline"))
        .sheet(bind_show_sheet,
               content=sheet_content,
               drag_indicator="visible",
               detents=["medium", "large"]))


appui.run(root, state=state, presentation="fullscreen_with_close")
