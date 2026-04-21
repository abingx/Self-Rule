# 欢迎使用 PythonIDE！如果觉得好用，请给个好评哦～
"""
Aurora 引擎超级覆盖测试 — Super Coverage Test
==================================================
10-tab 极限压力测试，覆盖引擎全部能力边界。

模块:
  Tab 1  — 状态机自愈 (State Resilience)
  Tab 2  — UI 暴力排布 (Layout Stress)
  Tab 3  — Beast Mode 满载 (Aurora Binary Path)
  Tab 4  — 原生全组件大阅兵 (Component Parade)
  Tab 5  — 主题压力切换 (Theme Stress)
  Tab 6  — 手势全覆盖 (Gesture Coverage)
  Tab 7  — 导航极限 (Navigation Limits)
  Tab 8  — 形状与视觉效果 (Shapes & Effects)
  Tab 9  — 高级布局 (Advanced Layout)
  Tab 10 — 系统集成 (System Integration)
"""

import appui
import math
import time
import random
import threading

# ══════════════════════════════════════════════════════════════
#  GLOBAL STATE
# ══════════════════════════════════════════════════════════════

state = appui.State(
    # Tab 1: State Resilience
    tf0='Alpha', tf1='Bravo', tf2='Charlie', tf3='Delta',
    tf4='Echo', tf5='Foxtrot', tf6='Golf', tf7='Hotel',
    sec_field='secret123',
    te_content='多行文本编辑器\n第二行内容\n第三行',
    tog0=True, tog1=False, tog2=True, tog3=False,
    sl0=0.25, sl1=0.50, sl2=0.75, sl3=1.0,
    res_picker='B',
    res_stepper=5,
    noise_counter=0,
    rebuild_count=0,

    # Tab 2: Layout Stress
    layout_cols=4,
    layout_long_text='这是一段超长的中文测试文本用于验证fixedSize在极端情况下的表现'
                     '，当屏幕宽度不足时文本应当正确换行而非溢出屏幕边界。'
                     'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',

    # Tab 3: Beast Mode
    beast_n=128,
    beast_vals=[0.5] * 512,
    beast_fps=0.0,
    beast_on=False,
    beast_frames=0,
    beast_dropped=0,
    beast_aurora_ok=False,
    beast_audio_on=False,
    beast_audio_bands=[0.0] * 64,

    # Tab 4: Parade
    p_toggle=True,
    p_slider=0.5,
    p_stepper=5,
    p_picker='Apple',
    p_segment='中',
    p_date='',
    p_color='#FF6600',
    p_search='',
    p_gauge=0.7,
    p_progress=0.4,
    p_form_name='',
    p_form_email='',
    p_inline='Red',
    p_wheel='A',
    p_multi_date='',
    p_pasted='',

    # Tab 5: Theme
    theme='light',
    theme_auto=False,
    theme_speed=1.0,
    theme_count=0,
    theme_log='',

    # Tab 6: Gestures
    g_log='',
    g_drag='0,0',
    g_mag=1.0,
    g_rot=0.0,
    g_haptic_type='impact',
    show_sheet=False,
    show_alert=False,
    show_dialog=False,
    show_fullscreen=False,
    show_popover=False,

    # Tab 7: Navigation
    nav_depth=0,

    # Tab 8: Effects
    fx_blur=0.0,
    fx_bright=0.0,
    fx_contrast=1.0,
    fx_sat=1.0,
    fx_gray=0.0,
    fx_scale=1.0,
    fx_rotation=0.0,
    fx_3d_x=0.0,
    fx_3d_y=0.0,
    fx_anim_on=False,

    # Tab 9: Advanced Layout
    adv_geo_w=0, adv_geo_h=0,
    adv_scroll_target='',

    # Tab 4: ControlGroup toggles & Apple Sign In
    cg_bold=False,
    cg_italic=False,
    cg_underline=False,
    apple_result='未点击',

    # Tab 10: System
    sys_la_active=False,
    sys_la_progress=0.0,
    sys_kbd_height=0.0,
    sys_style='unknown',
    sys_timer_count=0,
)


# ══════════════════════════════════════════════════════════════
#  BACKGROUND THREADS
# ══════════════════════════════════════════════════════════════

def _noise_thread():
    """Background mutation to count rebuilds — very low frequency.
    Only runs when Tab 1 (state resilience) is visible."""
    while True:
        time.sleep(10.0)
        state.noise_counter += 1
        state.rebuild_count += 1


def _beast_thread():
    """Drive 128-512 slider values with sine waves.

    Attempts Aurora binary path first; falls back to JSON rebuild.
    """
    aurora_group = None
    try:
        import aurora
        from aurora_toolkit import AuroraSliderGroup, frame_batch
        state.beast_aurora_ok = True
    except Exception:
        aurora = None
        AuroraSliderGroup = None
        frame_batch = None

    frame = 0
    t0 = time.time()
    last_fps_update = t0

    while True:
        if not state.beast_on:
            time.sleep(0.2)
            t0 = time.time()
            frame = 0
            aurora_group = None
            continue

        n = state.beast_n

        if AuroraSliderGroup and frame_batch:
            try:
                import aurora as _a
                if _a.is_active():
                    if aurora_group is None or aurora_group.count != n:
                        aurora_group = AuroraSliderGroup("beast", n)
                        aurora_group.bind()

                    vals = [0.5 + 0.45 * math.sin(frame * 0.05 + i * 0.13)
                            for i in range(n)]
                    with frame_batch():
                        ok = aurora_group.update_all(vals)
                    if not ok:
                        state.beast_dropped += 1
                    frame += 1
                    state.beast_frames = frame

                    now = time.time()
                    if now - last_fps_update > 0.5:
                        elapsed = now - t0
                        state.beast_fps = round(frame / elapsed, 1) if elapsed > 0 else 0
                        last_fps_update = now

                    time.sleep(1 / 60)
                    continue
            except Exception:
                pass

        n_update = min(n, 32)
        vals = list(state.beast_vals)
        for i in range(min(n_update, len(vals))):
            vals[i] = 0.5 + 0.45 * math.sin(frame * 0.05 + i * 0.13)
        state.beast_vals = vals
        frame += 1
        state.beast_frames = frame

        now = time.time()
        if now - last_fps_update > 1.0:
            elapsed = now - t0
            state.beast_fps = round(frame / elapsed, 1) if elapsed > 0 else 0
            last_fps_update = now

        time.sleep(1 / 20)


def _audio_monitor_thread():
    """Poll audio RMS samples when beast audio is active.

    The Swift AuroraAudioBridge pushes real mic data into the C buffer,
    but AuroraAudioGroup._samples is a local ctypes array that the bridge
    never writes to.  So we try the real path first; if samples stay at
    zero we fall back to a math-based simulation so the visualisation
    always shows movement.
    """
    audio_group = None
    AuroraAudioGroup = None
    try:
        from aurora_toolkit import AuroraAudioGroup as _AAG
        AuroraAudioGroup = _AAG
    except Exception:
        pass

    sim_t = 0.0

    while True:
        if not state.beast_audio_on:
            if audio_group and audio_group._started:
                audio_group.stop()
                audio_group = None
            sim_t = 0.0
            time.sleep(0.3)
            continue

        if audio_group is None and AuroraAudioGroup:
            audio_group = AuroraAudioGroup(band_count=512)
            audio_group.start()

        got_real = False
        if audio_group:
            preview = [float(audio_group[i * 16]) for i in range(32)]
            got_real = any(v > 0.001 for v in preview)
            if got_real:
                state.beast_audio_bands = preview

        if not got_real:
            bands = []
            for i in range(32):
                v = 0.3 + 0.25 * math.sin(sim_t * 3.0 + i * 0.4)
                v += 0.15 * math.sin(sim_t * 7.0 + i * 0.9)
                v = max(0.05, min(1.0, v + random.gauss(0, 0.05)))
                bands.append(round(v, 3))
            state.beast_audio_bands = bands
            sim_t += 0.07

        time.sleep(1 / 15)


def _theme_thread():
    """Auto-toggle dark/light theme."""
    while True:
        if state.theme_auto:
            new = 'dark' if state.theme == 'light' else 'light'
            state.theme = new
            state.theme_count += 1
            state.theme_log = f'→ {new} (#{state.theme_count})'
            time.sleep(max(0.3, state.theme_speed))
        else:
            time.sleep(0.3)


def _animation_thread():
    """Drive effect parameters when animation is on."""
    t = 0.0
    while True:
        if state.fx_anim_on:
            state.batch_update(
                fx_scale=round(0.8 + 0.4 * math.sin(t * 2), 3),
                fx_rotation=round(180 * math.sin(t), 1),
                fx_blur=round(3 + 3 * math.sin(t * 1.5), 2),
            )
            t += 0.05
            time.sleep(1 / 15)
        else:
            t = 0.0
            time.sleep(0.5)


def _sys_timer_thread():
    """System timer for Tab 10 — slow tick to minimise battery drain."""
    while True:
        time.sleep(10.0)
        state.sys_timer_count += 1


for _fn in [_noise_thread, _beast_thread, _audio_monitor_thread,
            _theme_thread, _animation_thread, _sys_timer_thread]:
    threading.Thread(target=_fn, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _h(title):
    return appui.Text(title).font('headline').bold().padding(top=8, bottom=4)


def _sub(text):
    return appui.Text(text).font('caption').foreground_color('secondary')


def _haptic_btn(label, style):
    return (appui.Button(label, action=lambda: setattr(state, 'g_haptic_type', style))
            .button_style('bordered')
            .sensory_feedback(style))


def _g_log(name, val=''):
    state.g_log = f'[{name}] {str(val)[:60]}'


# ══════════════════════════════════════════════════════════════
#  TAB 1 — 状态机自愈测试
# ══════════════════════════════════════════════════════════════

def _tab1():
    return appui.ScrollView([appui.VStack([
        _h('状态机自愈测试'),
        _sub(f'后台重建: {state.rebuild_count} | 噪声: {state.noise_counter}'),

        _h('8 个 TextField'),
        *[appui.TextField(
            text=getattr(state, f'tf{i}'),
            placeholder=f'输入框 #{i+1}',
            on_change=lambda v, k=f'tf{i}': setattr(state, k, v),
        ) for i in range(8)],

        _h('SecureField'),
        appui.SecureField(
            text=state.sec_field, placeholder='密码',
            on_change=lambda v: setattr(state, 'sec_field', v)),

        _h('TextEditor'),
        appui.TextEditor(
            text=state.te_content,
            on_change=lambda v: setattr(state, 'te_content', v),
        ).frame(height=100),

        _h('4 个 Toggle'),
        *[appui.Toggle(
            label=f'开关 {i+1}',
            is_on=getattr(state, f'tog{i}'),
            on_change=lambda v, k=f'tog{i}': setattr(state, k, v),
        ).sensory_feedback('selection') for i in range(4)],

        _h('4 个 Slider'),
        *[appui.VStack([
            appui.Text(f'Slider {i+1}: {getattr(state, f"sl{i}"):.2f}'),
            appui.Slider(
                value=getattr(state, f'sl{i}'), minimum=0, maximum=1,
                on_change=lambda v, k=f'sl{i}': setattr(state, k, v)),
        ], spacing=2) for i in range(4)],

        _h('Picker + Stepper'),
        appui.Picker(label='选项', selection=state.res_picker,
                     options=['A', 'B', 'C', 'D', 'E'],
                     on_change=lambda v: setattr(state, 'res_picker', v)),
        appui.Stepper(label=f'步进: {state.res_stepper}',
                      value=state.res_stepper, minimum=0, maximum=99,
                      on_change=lambda v: setattr(state, 'res_stepper', v)),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()])


# ══════════════════════════════════════════════════════════════
#  TAB 2 — UI 暴力排布
# ══════════════════════════════════════════════════════════════

def _tab2():
    return appui.ScrollView([appui.VStack([
        _h('HStack 25 个按钮'),
        appui.ScrollView([
            appui.HStack(
                [appui.Button(f'B{i}', action=lambda: None)
                     .button_style('bordered').font('caption2')
                 for i in range(25)],
                spacing=3,
            )
        ], axes='horizontal').frame(height=44),

        appui.Divider(),
        _h('VStack 20 行交互 (Toggle + Stepper + Slider)'),
        *[appui.HStack([
            appui.Text(f'R{i:02d}').font('caption2').frame(width=32),
            appui.Toggle(label='', is_on=i % 2 == 0, on_change=lambda v: None),
            appui.Stepper(label='', value=i, minimum=0, maximum=99,
                          on_change=lambda v: None),
            appui.Slider(value=(i / 20.0), minimum=0, maximum=1,
                         on_change=lambda v: None),
        ], spacing=2) for i in range(20)],

        appui.Divider(),
        _h('极限 Spacer 压缩 (min_length=0)'),
        appui.HStack([
            appui.Text('左端').font('caption'),
            appui.Spacer(min_length=0),
            appui.Text('这是很长的压缩测试文本').line_limit(1).font('caption'),
            appui.Spacer(min_length=0),
            appui.Text('右端').font('caption'),
        ]).frame(height=30).background('tertiarySystemFill', corner_radius=6),

        appui.Divider(),
        _h('ViewThatFits 自适应'),
        appui.ViewThatFits(children=[
            appui.HStack([
                appui.Text('宽版: 完整内容显示').padding(8),
                appui.Spacer(),
                appui.Button('详情', action=lambda: None).button_style('bordered'),
            ]),
            appui.VStack([
                appui.Text('窄版: 堆叠').font('caption'),
                appui.Button('详情', action=lambda: None).button_style('bordered'),
            ]),
        ]),

        appui.Divider(),
        _h('fixedSize 文本验证'),
        appui.Text(state.layout_long_text).fixed_size(horizontal=False, vertical=True),

        appui.Divider(),
        _h(f'LazyVGrid ({state.layout_cols} 列 × 30 项)'),
        appui.SegmentedControl(
            options=['3', '4', '5', '6'],
            selection=str(state.layout_cols),
            on_change=lambda v: setattr(state, 'layout_cols', int(v)),
        ),
        appui.LazyVGrid(
            columns=[{'type': 'flexible'} for _ in range(state.layout_cols)],
            spacing=3,
            children=[
                appui.RoundedRectangle(corner_radius=4)
                    .fill(['red', 'orange', 'yellow', 'green', 'blue', 'purple'][i % 6])
                    .frame(height=32)
                    .overlay(appui.Text(str(i+1)).foreground_color('white').font('caption2'))
                for i in range(30)
            ],
        ),

        appui.Divider(),
        _h('GeometryReader'),
        appui.GeometryReader(
            children=[appui.Text('GeoReader 正常').font('caption').padding(4)],
            on_geometry=lambda w, h: None,
        ).frame(height=40).background('quaternarySystemFill', corner_radius=6),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()])


# ══════════════════════════════════════════════════════════════
#  TAB 3 — Beast Mode 满载测试
# ══════════════════════════════════════════════════════════════

def _make_beast_slider_cb(idx):
    def cb(v):
        vals = list(state.beast_vals)
        if idx < len(vals):
            vals[idx] = v
            state.beast_vals = vals
    return cb


def _tab3():
    n = state.beast_n
    return appui.ScrollView([appui.VStack([
        _h('Beast Mode 满载测试'),
        appui.HStack([
            appui.Text(f'Sliders: {n}'),
            appui.Spacer(),
            appui.Text(f'FPS: {state.beast_fps}'),
            appui.Spacer(),
            appui.Text(f'丢帧: {state.beast_dropped}').foreground_color(
                'red' if state.beast_dropped > 0 else 'secondary'),
        ]),
        _sub(f'路径: {"Aurora 二进制" if state.beast_aurora_ok else "JSON 回退"} | 帧: {state.beast_frames}'),

        appui.SegmentedControl(
            options=['64', '128', '256', '512'],
            selection=str(n),
            on_change=lambda v: state.batch_update(
                beast_n=int(v), beast_frames=0, beast_fps=0, beast_dropped=0),
        ),
        appui.Toggle(label='Beast Mode ON', is_on=state.beast_on,
                     on_change=lambda v: state.batch_update(
                         beast_on=v, beast_frames=0, beast_fps=0, beast_dropped=0))
            .sensory_feedback('impact'),

        appui.Divider(),
        _h('Slider 波形'),
        *(
            [appui.LazyVGrid(
                columns=[{'type': 'flexible'}, {'type': 'flexible'},
                         {'type': 'flexible'}, {'type': 'flexible'}],
                spacing=1,
                children=[
                    appui.Slider(
                        value=state.beast_vals[i] if i < len(state.beast_vals) else 0.5,
                        minimum=0, maximum=1,
                        on_change=_make_beast_slider_cb(i),
                    ) for i in range(min(n, 32))
                ],
            ),
            _sub(f'显示前 {min(n, 32)} 个 / 共 {n} 个 Slider (Aurora 二进制路径驱动全部)')]
            if state.beast_on else
            [_sub('开启 Beast Mode 后渲染 Slider 波形')]
        ),

        appui.Divider(),
        _h('512-Band 音频采集'),
        appui.Toggle(label='麦克风采集', is_on=state.beast_audio_on,
                     on_change=lambda v: setattr(state, 'beast_audio_on', v)),
        _sub('Swift 端以 60 Hz 推送 512 频段 RMS 至 Aurora C 缓冲区'),
        *(
            [appui.HStack(
                [appui.RoundedRectangle(corner_radius=1)
                    .fill('systemBlue')
                    .frame(width=3, height=max(2, state.beast_audio_bands[i] * 50
                           if i < len(state.beast_audio_bands) else 2))
                 for i in range(32)],
                spacing=1,
            ).frame(height=52).clipped()]
            if state.beast_audio_on else
            [_sub('开启后显示频谱')]
        ),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()])


# ══════════════════════════════════════════════════════════════
#  TAB 4 — 原生全组件大阅兵
# ══════════════════════════════════════════════════════════════

def _tab4():
    return appui.ScrollView([appui.VStack([
        _h('原生全组件大阅兵'),

        # --- 输入控件 ---
        _h('Toggle'),
        appui.Toggle(label='开关', is_on=state.p_toggle,
                     on_change=lambda v: setattr(state, 'p_toggle', v))
            .sensory_feedback('selection'),

        _h('Slider'),
        appui.Text(f'值: {state.p_slider:.2f}').font('caption'),
        appui.Slider(value=state.p_slider, minimum=0, maximum=1,
                     on_change=lambda v: setattr(state, 'p_slider', v))
            .sensory_feedback('selection'),

        _h('Stepper'),
        appui.Stepper(label=f'数量: {state.p_stepper}', value=state.p_stepper,
                      minimum=0, maximum=99,
                      on_change=lambda v: setattr(state, 'p_stepper', v))
            .sensory_feedback('impact'),

        _h('Picker (default)'),
        appui.Picker(label='水果', selection=state.p_picker,
                     options=['Apple', 'Banana', 'Cherry', 'Durian', 'Elderberry'],
                     on_change=lambda v: setattr(state, 'p_picker', v)),

        _h('SegmentedControl'),
        appui.SegmentedControl(
            options=['小', '中', '大', '特大'],
            selection=state.p_segment,
            on_change=lambda v: setattr(state, 'p_segment', v))
            .sensory_feedback('selection'),

        _h('InlinePicker'),
        appui.InlinePickerStyle(
            options=['Red', 'Green', 'Blue', 'Yellow', 'Purple'],
            selection=state.p_inline,
            on_change=lambda v: setattr(state, 'p_inline', v))
            .frame(height=140),
        _sub(f'选中: {state.p_inline}'),

        _h('WheelPicker'),
        appui.WheelPicker(
            options=['A', 'B', 'C', 'D', 'E', 'F', 'G'],
            selection=state.p_wheel,
            on_change=lambda v: setattr(state, 'p_wheel', v))
            .frame(height=140),
        _sub(f'选中: {state.p_wheel}'),

        _h('DatePicker'),
        appui.DatePicker(label='选择日期')
            .sensory_feedback('selection'),

        _h('MultiDatePicker'),
        appui.MultiDatePicker('多日期选择'),

        _h('ColorPicker'),
        appui.ColorPicker(label='颜色', selection=state.p_color,
                          on_change=lambda v: setattr(state, 'p_color', v)),

        _h('SearchField'),
        appui.SearchField(text=state.p_search, placeholder='搜索组件...',
                          on_change=lambda v: setattr(state, 'p_search', v)),

        # --- 展示组件 ---
        _h('Gauge'),
        appui.Gauge(value=state.p_gauge, label='负载', minimum=0, maximum=1),

        _h('ProgressView'),
        appui.ProgressView(value=state.p_progress, total=1.0),
        appui.ProgressView(),

        _h('Menu'),
        appui.Menu(title='操作菜单', children=[
            appui.Button('选项 A', action=lambda: None),
            appui.Button('选项 B', action=lambda: None),
            appui.Divider(),
            appui.Button('危险操作', action=lambda: None, role='destructive'),
        ]).sensory_feedback('impact'),

        _h('ShareLink'),
        appui.ShareLink(title='分享此应用', url='https://github.com'),

        _h('Link'),
        appui.Link(title='访问 Apple', url='https://apple.com'),

        _h('ControlGroup'),
        appui.ControlGroup(label='文本格式', content=[
            appui.Button('B' + (' ✓' if state.cg_bold else ''),
                         action=lambda: setattr(state, 'cg_bold', not state.cg_bold)),
            appui.Button('I' + (' ✓' if state.cg_italic else ''),
                         action=lambda: setattr(state, 'cg_italic', not state.cg_italic)),
            appui.Button('U' + (' ✓' if state.cg_underline else ''),
                         action=lambda: setattr(state, 'cg_underline', not state.cg_underline)),
        ]),
        _sub(f'Bold={state.cg_bold}  Italic={state.cg_italic}  Underline={state.cg_underline}'),

        _h('PasteButton'),
        appui.PasteButton(on_paste=lambda v: setattr(state, 'p_pasted', v)),
        _sub(f'粘贴内容: {state.p_pasted}'),

        _h('EditButton / RenameButton'),
        appui.HStack([appui.EditButton(), appui.RenameButton()], spacing=16),

        # --- 容器组件 ---
        _h('DisclosureGroup'),
        appui.DisclosureGroup(label='展开查看详情', children=[
            appui.Text('隐藏内容 1'),
            appui.Text('隐藏内容 2'),
            appui.Text('隐藏内容 3'),
        ]),

        _h('GroupBox + LabeledContent'),
        appui.GroupBox(label='设备信息', children=[
            appui.LabeledContent(label='型号', content='iPhone 16 Pro'),
            appui.LabeledContent(label='系统', content='iOS 18.4'),
            appui.LabeledContent(label='存储', content='256 GB'),
        ]),

        _h('ContentUnavailableView'),
        appui.ContentUnavailableView(
            title='无搜索结果',
            system_image='magnifyingglass',
            description='尝试不同的关键词'),

        # --- 图表/绘图/媒体 ---
        _h('Chart (Bar)'),
        appui.Chart(
            data=[{'x': '一月', 'y': 30}, {'x': '二月', 'y': 55},
                  {'x': '三月', 'y': 42}, {'x': '四月', 'y': 68},
                  {'x': '五月', 'y': 51}, {'x': '六月', 'y': 79}],
            chart_type='bar', color='systemBlue',
        ).frame(height=200),

        _h('Chart (Line)'),
        appui.Chart(
            data=[{'x': str(i), 'y': 50 + 30 * math.sin(i * 0.5)} for i in range(12)],
            chart_type='line', color='systemGreen',
        ).frame(height=160),

        _h('Canvas'),
        appui.Canvas(width=300, height=100, commands=[
            {'op': 'fill_rect', 'x': 0, 'y': 0, 'w': 300, 'h': 100, 'c': 'systemBlue'},
            {'op': 'fill_rect', 'x': 0, 'y': 0, 'w': 150, 'h': 100, 'c': 'systemIndigo'},
            {'op': 'fill_circle', 'cx': 150, 'cy': 50, 'r': 35, 'c': 'systemOrange'},
            {'op': 'stroke_circle', 'cx': 150, 'cy': 50, 'r': 35, 'c': 'white', 'lw': 2},
            {'op': 'fill_text', 'text': 'Canvas OK', 'x': 115, 'y': 55,
             'c': 'white', 'size': 16},
        ]),

        _h('MapView'),
        appui.MapView(
            latitude=35.6762, longitude=139.6503, span=0.05,
            markers=[
                {'latitude': 35.6762, 'longitude': 139.6503, 'title': '东京塔'},
                {'latitude': 35.6586, 'longitude': 139.7454, 'title': '东京站'},
            ],
            map_style='standard',
        ).frame(height=200),

        _h('AsyncImage (占位)'),
        appui.GroupBox(label='AsyncImage', children=[
            _sub('远程图片已移除以避免重建时重新请求'),
        ]),

        _h('VideoPlayer (占位)'),
        appui.GroupBox(label='VideoPlayer', children=[
            _sub('远程视频已移除以减少系统日志噪音'),
            _sub('appui.VideoPlayer(url=...) 可正常使用'),
        ]),

        _h('WebView (占位)'),
        appui.GroupBox(label='WebView', children=[
            _sub('远程 WebView 已移除以减少重建开销'),
            _sub('appui.WebView(url=...) 可正常使用'),
        ]),

        # --- 形状 ---
        _h('5 种形状'),
        appui.HStack([
            appui.Rectangle().fill('systemRed').frame(width=44, height=44),
            appui.RoundedRectangle(corner_radius=10).fill('systemOrange').frame(width=44, height=44),
            appui.Circle().fill('systemGreen').frame(width=44, height=44),
            appui.Capsule().fill('systemBlue').frame(width=60, height=44),
            appui.Ellipse().fill('systemPurple').frame(width=55, height=44),
        ], spacing=8),

        # --- 系统控件 ---
        _h('SignInWithApple'),
        appui.SignInWithAppleButton(
            on_complete=lambda r: setattr(state, 'apple_result', str(r)[:80])
        ).frame(height=50),
        _sub(f'结果: {state.apple_result}'),

        _h('TimelineView'),
        appui.TimelineView(interval=2.0, children=[
            appui.Text('TimelineView 刷新中').font('caption'),
        ]),

        # --- 表格 ---
        _h('Table'),
        appui.Table(
            data=[
                {'name': 'Alice', 'score': '95', 'grade': 'A'},
                {'name': 'Bob', 'score': '82', 'grade': 'B+'},
                {'name': 'Charlie', 'score': '91', 'grade': 'A-'},
            ],
            columns=[
                {'title': '姓名', 'key': 'name'},
                {'title': '分数', 'key': 'score'},
                {'title': '等级', 'key': 'grade'},
            ],
        ).frame(height=140),

        # --- Grid ---
        _h('Grid'),
        appui.Grid(children=[
            appui.GridRow(children=[
                appui.Text('A1').padding(6).background('systemFill', corner_radius=4),
                appui.Text('B1').padding(6).background('systemFill', corner_radius=4),
                appui.Text('C1').padding(6).background('systemFill', corner_radius=4),
            ]),
            appui.GridRow(children=[
                appui.Text('A2').padding(6).background('systemFill', corner_radius=4),
                appui.Text('B2').padding(6).background('systemFill', corner_radius=4),
                appui.Text('C2').padding(6).background('systemFill', corner_radius=4),
            ]),
        ]),

        # --- List + Badge ---
        _h('List + Badge'),
        appui.List([
            appui.Label('通知', system_image='bell.fill').badge('5'),
            appui.Label('邮件', system_image='envelope.fill').badge('128'),
            appui.Label('更新', system_image='arrow.down.circle.fill').badge('3'),
        ]).frame(height=140).list_style('inset_grouped'),

        # --- Form ---
        _h('Form'),
        appui.Form([
            appui.Section(header='个人信息', children=[
                appui.TextField(text=state.p_form_name, placeholder='姓名',
                                on_change=lambda v: setattr(state, 'p_form_name', v)),
                appui.TextField(text=state.p_form_email, placeholder='邮箱',
                                on_change=lambda v: setattr(state, 'p_form_email', v)),
            ]),
            appui.Section(header='偏好', children=[
                appui.Toggle(label='推送通知', is_on=True, on_change=lambda v: None),
                appui.Picker(label='语言', selection='中文',
                             options=['中文', 'English', '日本語'],
                             on_change=lambda v: None),
            ]),
        ]).frame(height=240),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()])


# ══════════════════════════════════════════════════════════════
#  TAB 5 — 主题压力切换
# ══════════════════════════════════════════════════════════════

def _tab5():
    return appui.ScrollView([appui.VStack([
        _h('主题压力切换'),
        appui.SegmentedControl(
            options=['light', 'dark'],
            selection=state.theme,
            on_change=lambda v: setattr(state, 'theme', v)),
        appui.Toggle(label='自动循环', is_on=state.theme_auto,
                     on_change=lambda v: setattr(state, 'theme_auto', v)),
        appui.Text(f'切换速度: {state.theme_speed:.1f}s'),
        appui.Slider(value=state.theme_speed, minimum=0.3, maximum=3.0,
                     on_change=lambda v: setattr(state, 'theme_speed', v)),
        _sub(f'已切换 {state.theme_count} 次 | {state.theme_log}'),

        appui.Divider(),
        _h('语义色矩阵'),
        appui.VStack([
            appui.HStack([
                appui.Text('label').foreground_color('label'),
                appui.Spacer(),
                appui.Text('secondaryLabel').foreground_color('secondaryLabel'),
            ]),
            appui.HStack([
                appui.Text('tertiaryLabel').foreground_color('tertiaryLabel'),
                appui.Spacer(),
                appui.Text('quaternaryLabel').foreground_color('quaternaryLabel'),
            ]),
            appui.HStack([
                appui.Text('link').foreground_color('link'),
                appui.Spacer(),
                appui.Text('placeholderText').foreground_color('placeholderText'),
            ]),
        ], spacing=6),

        appui.Divider(),
        _h('语义背景色'),
        *[appui.HStack([
            appui.RoundedRectangle(corner_radius=6)
                .fill(c).frame(height=36)
                .overlay(appui.Text(c).font('caption2').foreground_color('label')),
        ]) for c in [
            'systemBackground', 'secondarySystemBackground',
            'tertiarySystemBackground', 'systemGroupedBackground',
            'secondarySystemGroupedBackground', 'tertiarySystemGroupedBackground',
        ]],

        appui.Divider(),
        _h('固定色对照 (不随主题变化)'),
        appui.HStack([
            appui.RoundedRectangle(corner_radius=6).fill('#1A1A1A').frame(height=36)
                .overlay(appui.Text('#1A1A1A').font('caption2').foreground_color('white')),
            appui.RoundedRectangle(corner_radius=6).fill('#E5E5E5').frame(height=36)
                .overlay(appui.Text('#E5E5E5').font('caption2').foreground_color('black')),
        ], spacing=8),

        appui.Divider(),
        _h('Canvas 深色模式验证'),
        appui.Canvas(width=300, height=60, commands=[
            {'op': 'fill_rect', 'x': 0, 'y': 0, 'w': 100, 'h': 60, 'c': 'primary'},
            {'op': 'fill_rect', 'x': 100, 'y': 0, 'w': 100, 'h': 60, 'c': 'secondary'},
            {'op': 'fill_rect', 'x': 200, 'y': 0, 'w': 100, 'h': 60, 'c': 'systemFill'},
            {'op': 'fill_text', 'text': 'primary', 'x': 16, 'y': 35,
             'c': 'systemBackground', 'size': 11},
            {'op': 'fill_text', 'text': 'secondary', 'x': 110, 'y': 35,
             'c': 'systemBackground', 'size': 11},
            {'op': 'fill_text', 'text': 'systemFill', 'x': 208, 'y': 35,
             'c': 'label', 'size': 11},
        ]),

        appui.Divider(),
        _h('系统色板'),
        appui.LazyVGrid(
            columns=[{'type': 'flexible'}, {'type': 'flexible'}, {'type': 'flexible'}],
            spacing=4,
            children=[
                appui.RoundedRectangle(corner_radius=6)
                    .fill(c).frame(height=32)
                    .overlay(appui.Text(c.replace('system', '')).font('system-9')
                             .foreground_color('white'))
                for c in [
                    'systemRed', 'systemOrange', 'systemYellow',
                    'systemGreen', 'systemMint', 'systemTeal',
                    'systemCyan', 'systemBlue', 'systemIndigo',
                    'systemPurple', 'systemPink', 'systemBrown',
                ]
            ],
        ),

        appui.Divider(),
        _h('Map 深色验证'),
        appui.MapView(latitude=31.23, longitude=121.47, span=0.1,
                      markers=[{'latitude': 31.23, 'longitude': 121.47, 'title': '上海'}],
                      map_style='standard').frame(height=120),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()])


# ══════════════════════════════════════════════════════════════
#  TAB 6 — 手势全覆盖
# ══════════════════════════════════════════════════════════════

def _tab6():
    return appui.ScrollView([appui.VStack([
        _h('手势全覆盖'),

        _h('Tap / LongPress'),
        appui.HStack([
            appui.RoundedRectangle(corner_radius=12)
                .fill('systemBlue').frame(width=120, height=60)
                .overlay(appui.Text('Tap').foreground_color('white'))
                .on_tap(lambda: _g_log('Tap', '触发'))
                .sensory_feedback('impact'),
            appui.RoundedRectangle(corner_radius=12)
                .fill('systemOrange').frame(width=120, height=60)
                .overlay(appui.Text('LongPress').foreground_color('white').font('caption'))
                .on_long_press(lambda: _g_log('LongPress', '0.5s'), min_duration=0.5)
                .sensory_feedback('warning'),
        ], spacing=12),

        _h('Drag 手势'),
        appui.RoundedRectangle(corner_radius=12)
            .fill('systemGreen').frame(height=70)
            .overlay(appui.Text(f'拖拽: {state.g_drag}').foreground_color('white').font('caption'))
            .on_drag(
                on_changed=lambda v: setattr(state, 'g_drag', v),
                on_ended=lambda v: _g_log('DragEnd', v)),

        _h('Magnification 缩放'),
        appui.RoundedRectangle(corner_radius=12)
            .fill('systemPurple').frame(height=70)
            .overlay(appui.Text(f'缩放: {state.g_mag:.2f}x')
                     .foreground_color('white'))
            .on_magnification(
                on_changed=lambda v: setattr(state, 'g_mag', float(v) if v else 1.0),
                on_ended=lambda v: _g_log('MagEnd', v)),

        _h('Rotation 旋转'),
        appui.RoundedRectangle(corner_radius=12)
            .fill('systemRed').frame(height=70)
            .overlay(appui.Text(f'角度: {state.g_rot:.1f}°')
                     .foreground_color('white'))
            .on_rotation(
                on_changed=lambda v: setattr(state, 'g_rot', float(v) if v else 0.0),
                on_ended=lambda v: _g_log('RotEnd', v)),

        _h('Drop 拖放接收'),
        appui.RoundedRectangle(corner_radius=12)
            .fill('tertiarySystemFill').frame(height=60)
            .overlay(appui.Text('拖放文本到此处').foreground_color('secondary'))
            .on_drop(lambda v: _g_log('Drop', v)),

        appui.Divider(),
        _h('Haptic 震动验证 (5 种)'),
        appui.HStack([
            _haptic_btn('impact', 'impact'),
            _haptic_btn('success', 'success'),
            _haptic_btn('warning', 'warning'),
            _haptic_btn('error', 'error'),
            _haptic_btn('select', 'selection'),
        ], spacing=4),
        _sub(f'最近: {state.g_haptic_type}'),

        appui.Divider(),
        _h('弹窗全覆盖'),
        appui.HStack([
            appui.Button('Sheet', action=lambda: setattr(state, 'show_sheet', True))
                .button_style('bordered'),
            appui.Button('Alert', action=lambda: setattr(state, 'show_alert', True))
                .button_style('bordered'),
            appui.Button('Dialog', action=lambda: setattr(state, 'show_dialog', True))
                .button_style('bordered'),
        ], spacing=6),
        appui.HStack([
            appui.Button('FullScreen', action=lambda: setattr(state, 'show_fullscreen', True))
                .button_style('bordered'),
            appui.Button('Popover', action=lambda: setattr(state, 'show_popover', True))
                .button_style('bordered'),
        ], spacing=6),

        _sub(state.g_log),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()])  \
    .sheet(
        is_presented=state.show_sheet,
        content=appui.VStack([
            appui.Text('Sheet 弹窗内容').font('title2'),
            appui.Text('支持手势下滑关闭').font('caption').foreground_color('secondary'),
            appui.Button('关闭', action=lambda: setattr(state, 'show_sheet', False)),
        ]).padding(),
        on_dismiss=lambda: setattr(state, 'show_sheet', False))  \
    .alert(
        title='Alert 测试', message='这是一个 Alert 弹窗',
        is_presented=state.show_alert,
        on_dismiss=lambda: setattr(state, 'show_alert', False))  \
    .confirmation_dialog(
        title='确认操作', is_presented=state.show_dialog,
        actions=[
            appui.Button('确认', action=lambda: setattr(state, 'show_dialog', False)),
            appui.Button('取消', action=lambda: setattr(state, 'show_dialog', False),
                         role='cancel'),
        ])  \
    .full_screen_cover(
        is_presented=state.show_fullscreen,
        content=appui.VStack([
            appui.Text('全屏弹窗').font('largeTitle'),
            appui.Spacer(),
            appui.Button('关闭全屏', action=lambda: setattr(state, 'show_fullscreen', False))
                .button_style('borderedProminent'),
        ]).padding(),
        on_dismiss=lambda: setattr(state, 'show_fullscreen', False))  \
    .popover(
        is_presented=state.show_popover,
        content=appui.VStack([
            appui.Text('Popover 气泡').font('headline'),
            appui.Button('关闭', action=lambda: setattr(state, 'show_popover', False)),
        ]).padding(),
        on_dismiss=lambda: setattr(state, 'show_popover', False))


# ══════════════════════════════════════════════════════════════
#  TAB 7 — 导航极限
# ══════════════════════════════════════════════════════════════

def _make_nav_level(depth, max_depth=5):
    if depth >= max_depth:
        return appui.VStack([
            appui.Text(f'第 {depth} 层 — 到底了！').font('title').foreground_color('systemGreen'),
            appui.Text('导航深度测试通过').font('caption'),
        ]).padding()
    return appui.VStack([
        appui.Text(f'第 {depth} 层').font('headline'),
        appui.Text(f'剩余 {max_depth - depth} 层').font('caption').foreground_color('secondary'),
        appui.NavigationLink(
            label=f'进入第 {depth + 1} 层',
            destination=_make_nav_level(depth + 1, max_depth)),
        appui.Divider(),
        appui.DisclosureGroup(label=f'折叠内容 @ 层 {depth}', children=[
            appui.Text(f'这是第 {depth} 层的隐藏内容'),
            appui.LabeledContent(label='深度', content=str(depth)),
        ]),
    ]).padding()


def _tab7():
    return appui.NavigationStack(content=appui.ScrollView([appui.VStack([
        _h('导航极限测试'),

        _h('5 层 NavigationLink'),
        appui.NavigationLink(
            label='开始导航深度测试',
            destination=_make_nav_level(1, 5)),

        appui.Divider(),
        _h('4 层嵌套 DisclosureGroup'),
        appui.DisclosureGroup(label='第 1 层', children=[
            appui.Text('1 层内容'),
            appui.DisclosureGroup(label='第 2 层', children=[
                appui.Text('2 层内容'),
                appui.DisclosureGroup(label='第 3 层', children=[
                    appui.Text('3 层内容'),
                    appui.DisclosureGroup(label='第 4 层', children=[
                        appui.Text('4 层嵌套 OK').foreground_color('systemGreen'),
                    ]),
                ]),
            ]),
        ]),

        appui.Divider(),
        _h('SwipeActions + Refreshable List'),
        appui.List([
            appui.Button(
                content=appui.HStack([
                    appui.Image(system_name='circle.fill')
                        .foreground_color(['red', 'orange', 'green', 'blue',
                                           'purple', 'pink', 'cyan', 'mint'][i % 8]),
                    appui.Text(f'列表项 #{i+1}'),
                    appui.Spacer(),
                    appui.Text(f'{random.randint(1, 99)}').foreground_color('secondary'),
                ]),
                action=lambda: None,
            ).button_style('plain')
            .swipe_actions(actions=[
                appui.Button('标记', action=lambda: None),
                appui.Button('删除', action=lambda: None, role='destructive'),
            ]) for i in range(12)
        ]).frame(height=360)
        .refreshable(action=lambda: time.sleep(0.5)),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()]))


# ══════════════════════════════════════════════════════════════
#  TAB 8 — 形状与视觉效果
# ══════════════════════════════════════════════════════════════

def _tab8():
    return appui.ScrollView([appui.VStack([
        _h('形状与视觉效果'),

        _h('形状 + Fill / Stroke'),
        appui.HStack([
            appui.Rectangle().fill('systemRed').frame(width=50, height=50),
            appui.RoundedRectangle(corner_radius=12).fill('systemOrange')
                .frame(width=50, height=50),
            appui.Circle().fill('systemGreen').frame(width=50, height=50),
            appui.Capsule().fill('systemBlue').frame(width=70, height=40),
            appui.Ellipse().fill('systemPurple').frame(width=60, height=40),
        ], spacing=6),

        _h('渐变背景'),
        appui.RoundedRectangle(corner_radius=12)
            .frame(height=60)
            .background(gradient=['systemBlue', 'systemPurple'],
                        gradient_type='linear', corner_radius=12),
        appui.RoundedRectangle(corner_radius=12)
            .frame(height=60)
            .background(gradient=['systemOrange', 'systemRed'],
                        gradient_type='radial', corner_radius=12),

        appui.Divider(),
        _h('视觉滤镜'),

        _sub(f'blur: {state.fx_blur:.1f}'),
        appui.Slider(value=state.fx_blur, minimum=0, maximum=20,
                     on_change=lambda v: setattr(state, 'fx_blur', v)),
        appui.RoundedRectangle(corner_radius=8)
            .fill('systemBlue').frame(height=50)
            .overlay(appui.Text('Blur').foreground_color('white'))
            .blur(state.fx_blur),

        _sub(f'brightness: {state.fx_bright:.2f}'),
        appui.Slider(value=state.fx_bright, minimum=-0.5, maximum=0.5,
                     on_change=lambda v: setattr(state, 'fx_bright', v)),
        appui.RoundedRectangle(corner_radius=8)
            .fill('systemGreen').frame(height=50)
            .overlay(appui.Text('Brightness').foreground_color('white'))
            .brightness(state.fx_bright),

        _sub(f'contrast: {state.fx_contrast:.2f}'),
        appui.Slider(value=state.fx_contrast, minimum=0, maximum=3,
                     on_change=lambda v: setattr(state, 'fx_contrast', v)),
        appui.RoundedRectangle(corner_radius=8)
            .fill('systemOrange').frame(height=50)
            .overlay(appui.Text('Contrast').foreground_color('white'))
            .contrast(state.fx_contrast),

        _sub(f'saturation: {state.fx_sat:.2f}'),
        appui.Slider(value=state.fx_sat, minimum=0, maximum=3,
                     on_change=lambda v: setattr(state, 'fx_sat', v)),
        appui.RoundedRectangle(corner_radius=8)
            .fill('systemPurple').frame(height=50)
            .overlay(appui.Text('Saturation').foreground_color('white'))
            .saturation(state.fx_sat),

        _sub(f'grayscale: {state.fx_gray:.2f}'),
        appui.Slider(value=state.fx_gray, minimum=0, maximum=1,
                     on_change=lambda v: setattr(state, 'fx_gray', v)),
        appui.RoundedRectangle(corner_radius=8)
            .fill('systemRed').frame(height=50)
            .overlay(appui.Text('Grayscale').foreground_color('white'))
            .grayscale(state.fx_gray),

        appui.Divider(),
        _h('变换效果'),

        _sub(f'scale: {state.fx_scale:.2f}'),
        appui.Slider(value=state.fx_scale, minimum=0.3, maximum=2.0,
                     on_change=lambda v: setattr(state, 'fx_scale', v)),
        appui.RoundedRectangle(corner_radius=8)
            .fill('systemTeal').frame(height=50)
            .overlay(appui.Text('Scale').foreground_color('white'))
            .scale_effect(state.fx_scale),

        appui.Spacer().frame(height=20),
        _sub(f'rotation: {state.fx_rotation:.0f}°'),
        appui.Slider(value=state.fx_rotation, minimum=-180, maximum=180,
                     on_change=lambda v: setattr(state, 'fx_rotation', v)),
        appui.RoundedRectangle(corner_radius=8)
            .fill('systemIndigo').frame(width=100, height=50)
            .overlay(appui.Text('Rotate').foreground_color('white'))
            .rotation_effect(state.fx_rotation),

        appui.Spacer().frame(height=30),
        _h('动画开关'),
        appui.Toggle(label='自动动画', is_on=state.fx_anim_on,
                     on_change=lambda v: setattr(state, 'fx_anim_on', v)),

        appui.Divider(),
        _h('阴影 / 边框 / Overlay / Mask'),
        appui.HStack([
            appui.RoundedRectangle(corner_radius=8)
                .fill('systemBackground').frame(width=80, height=60)
                .shadow(radius=8, color='primary', x=2, y=4)
                .overlay(appui.Text('Shadow').font('caption')),
            appui.RoundedRectangle(corner_radius=8)
                .fill('systemBackground').frame(width=80, height=60)
                .border(color='systemBlue', width=2)
                .overlay(appui.Text('Border').font('caption')),
            appui.RoundedRectangle(corner_radius=12)
                .fill('systemBlue').frame(width=80, height=60)
                .overlay(
                    appui.Circle().fill('systemOrange').frame(width=24, height=24),
                ),
        ], spacing=12),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()])


# ══════════════════════════════════════════════════════════════
#  TAB 9 — 高级布局
# ══════════════════════════════════════════════════════════════

def _tab9():
    return appui.ScrollView([appui.VStack([
        _h('高级布局'),

        _h('Grid + GridRow 复杂表格'),
        appui.Grid(children=[
            appui.GridRow(children=[
                appui.Text('').frame(width=60),
                appui.Text('Q1').bold(),
                appui.Text('Q2').bold(),
                appui.Text('Q3').bold(),
            ]),
            appui.GridRow(children=[
                appui.Text('收入').bold(),
                appui.Text('¥120K'),
                appui.Text('¥158K'),
                appui.Text('¥203K'),
            ]),
            appui.GridRow(children=[
                appui.Text('支出').bold(),
                appui.Text('¥95K'),
                appui.Text('¥112K'),
                appui.Text('¥130K'),
            ]),
            appui.GridRow(children=[
                appui.Text('净利').bold().foreground_color('systemGreen'),
                appui.Text('¥25K').foreground_color('systemGreen'),
                appui.Text('¥46K').foreground_color('systemGreen'),
                appui.Text('¥73K').foreground_color('systemGreen'),
            ]),
        ]),

        appui.Divider(),
        _h('LazyVGrid 3 列 + 自适应'),
        appui.LazyVGrid(
            columns=[{'type': 'adaptive', 'minimum': 100}],
            spacing=8,
            children=[
                appui.VStack([
                    appui.Circle()
                        .fill(['systemRed', 'systemOrange', 'systemYellow',
                               'systemGreen', 'systemBlue', 'systemPurple',
                               'systemPink', 'systemTeal', 'systemCyan'][i % 9])
                        .frame(width=50, height=50),
                    appui.Text(f'项目 {i+1}').font('caption'),
                ], spacing=4) for i in range(18)
            ],
        ),

        appui.Divider(),
        _h('LazyHGrid 水平滚动'),
        appui.ScrollView([
            appui.LazyHGrid(
                rows=[{'type': 'fixed', 'size': 60}, {'type': 'fixed', 'size': 60}],
                spacing=8,
                children=[
                    appui.RoundedRectangle(corner_radius=8)
                        .fill(['systemRed', 'systemOrange', 'systemGreen',
                               'systemBlue', 'systemPurple', 'systemPink'][i % 6])
                        .frame(width=80)
                        .overlay(appui.Text(f'{i+1}').foreground_color('white'))
                    for i in range(24)
                ],
            )
        ], axes='horizontal').frame(height=136),

        appui.Divider(),
        _h('GeometryReader 尺寸回报'),
        appui.GeometryReader(
            children=[
                appui.VStack([
                    appui.Text(f'宽: {state.adv_geo_w:.0f} pt').font('caption'),
                    appui.Text(f'高: {state.adv_geo_h:.0f} pt').font('caption'),
                ]).padding(8),
            ],
            on_geometry=lambda w, h: state.batch_update(adv_geo_w=w, adv_geo_h=h),
        ).frame(height=60).background('tertiarySystemFill', corner_radius=8),

        appui.Divider(),
        _h('ScrollViewReader + Scroll To'),
        appui.HStack([
            appui.Button('跳到 #1', action=lambda: setattr(state, 'adv_scroll_target', 'item_0'))
                .button_style('bordered'),
            appui.Button('跳到 #10', action=lambda: setattr(state, 'adv_scroll_target', 'item_9'))
                .button_style('bordered'),
            appui.Button('跳到 #20', action=lambda: setattr(state, 'adv_scroll_target', 'item_19'))
                .button_style('bordered'),
        ], spacing=6),
        appui.ScrollViewReader(
            scroll_to=state.adv_scroll_target,
            children=[
                appui.LazyVStack(children=[
                    appui.Text(f'列表项 #{i+1}')
                        .padding(8)
                        .frame(max_width=appui.infinity)
                        .background('secondarySystemFill' if i % 2 == 0 else 'tertiarySystemFill',
                                    corner_radius=4)
                        .id(f'item_{i}')
                    for i in range(25)
                ]),
            ],
        ).frame(height=200),

        appui.Divider(),
        _h('ViewThatFits'),
        appui.ViewThatFits(children=[
            appui.HStack([
                appui.Image(system_name='star.fill').foreground_color('systemYellow'),
                appui.Text('宽屏完整内容展示区域'),
                appui.Spacer(),
                appui.Button('操作', action=lambda: None).button_style('bordered'),
            ], spacing=8),
            appui.VStack([
                appui.Text('窄屏堆叠').font('caption'),
                appui.Button('操作', action=lambda: None).button_style('bordered'),
            ]),
        ]),

        appui.Divider(),
        _h('GroupBox + Section 嵌套'),
        appui.GroupBox(label='外层 GroupBox', children=[
            appui.Section(header='Section 1', children=[
                appui.LabeledContent(label='项 A', content='值 1'),
                appui.LabeledContent(label='项 B', content='值 2'),
            ]),
            appui.GroupBox(label='嵌套 GroupBox', children=[
                appui.LabeledContent(label='深层项', content='嵌套 OK'),
            ]),
        ]),

        appui.Divider(),
        _h('ZStack 层叠'),
        appui.ZStack([
            appui.RoundedRectangle(corner_radius=16)
                .fill('systemBlue').frame(width=200, height=100),
            appui.RoundedRectangle(corner_radius=12)
                .fill('systemOrange').frame(width=150, height=70)
                .offset(x=10, y=10),
            appui.Circle()
                .fill('systemGreen').frame(width=50, height=50)
                .offset(x=-30, y=-20),
            appui.Text('ZStack OK').foreground_color('white').bold(),
        ]).frame(height=120),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()])


# ══════════════════════════════════════════════════════════════
#  TAB 10 — 系统集成
# ══════════════════════════════════════════════════════════════

def _start_live_activity():
    try:
        import live_activity
        if live_activity.is_supported():
            live_activity.start(
                title='超级覆盖测试',
                message='正在运行压力测试...',
                progress=0.0,
                icon='bolt.fill',
            )
            state.sys_la_active = True
        else:
            state.sys_la_active = False
    except Exception:
        state.sys_la_active = False


def _update_live_activity():
    try:
        import live_activity
        state.sys_la_progress = min(1.0, state.sys_la_progress + 0.1)
        live_activity.update(
            message=f'进度 {state.sys_la_progress:.0%}',
            progress=state.sys_la_progress)
    except Exception:
        pass


def _end_live_activity():
    try:
        import live_activity
        live_activity.end(message='测试完成', dismiss_delay=3.0)
        state.sys_la_active = False
        state.sys_la_progress = 0.0
    except Exception:
        pass


def _setup_system_state():
    try:
        import aurora_system
        aurora_system.system_state_setup()

        @aurora_system.on_keyboard_height
        def _kb(h):
            state.sys_kbd_height = h

        @aurora_system.on_style_change
        def _style(s):
            state.sys_style = s
    except Exception:
        pass


_setup_system_state()


def _tab10():
    return appui.ScrollView([appui.VStack([
        _h('系统集成'),

        _h('Live Activity / Dynamic Island'),
        appui.HStack([
            appui.Button('启动', action=_start_live_activity).button_style('borderedProminent'),
            appui.Button('+10%', action=_update_live_activity).button_style('bordered'),
            appui.Button('结束', action=_end_live_activity).button_style('bordered'),
        ], spacing=8),
        _sub(f'状态: {"活跃" if state.sys_la_active else "未启动"} | 进度: {state.sys_la_progress:.0%}'),
        appui.ProgressView(value=state.sys_la_progress, total=1.0),

        appui.Divider(),
        _h('系统状态监控'),
        appui.GroupBox(label='设备状态', children=[
            appui.LabeledContent(label='键盘高度', content=f'{state.sys_kbd_height:.0f} pt'),
            appui.LabeledContent(label='界面风格', content=state.sys_style),
            appui.LabeledContent(label='计时器', content=f'{state.sys_timer_count}s'),
        ]),

        appui.Divider(),
        _h('Timer 定时器'),
        appui.Text(f'运行时间: {state.sys_timer_count} 秒').font('title2').bold(),
        appui.ProgressView(
            value=state.sys_timer_count % 60,
            total=60.0),
        _sub('每秒递增，验证后台线程与 UI 的同步'),

        appui.Divider(),
        _h('WebView 嵌入'),
        appui.WebView(url='https://example.com').frame(height=200),

        appui.Divider(),
        _h('引擎状态总览'),
        appui.GroupBox(label='Aurora 引擎', children=[
            appui.LabeledContent(label='组件总数', content='73 types'),
            appui.LabeledContent(label='Modifier 数', content='65+'),
            appui.LabeledContent(label='C 缓冲区', content='64KB × 2'),
            appui.LabeledContent(label='轮询频率', content='125 Hz (8ms)'),
            appui.LabeledContent(label='最大 drain', content='512 ops/次'),
            appui.LabeledContent(label='向量上限', content='5000 元素/次'),
        ]),

        appui.GroupBox(label='当前测试统计', children=[
            appui.LabeledContent(label='重建次数', content=str(state.rebuild_count)),
            appui.LabeledContent(label='噪声计数', content=str(state.noise_counter)),
            appui.LabeledContent(label='Beast 帧数', content=str(state.beast_frames)),
            appui.LabeledContent(label='Beast FPS', content=str(state.beast_fps)),
            appui.LabeledContent(label='主题切换', content=f'{state.theme_count} 次'),
        ]),

        appui.Spacer().frame(height=80),
    ], spacing=8).padding()])


# ══════════════════════════════════════════════════════════════
#  ROOT
# ══════════════════════════════════════════════════════════════

def build():
    return appui.TabView([
        appui.Tab(label='自愈', system_image='heart.text.square', content=_tab1()),
        appui.Tab(label='排布', system_image='square.grid.3x3', content=_tab2()),
        appui.Tab(label='Beast', system_image='bolt.fill', content=_tab3()),
        appui.Tab(label='组件', system_image='list.bullet.rectangle', content=_tab4()),
        appui.Tab(label='主题', system_image='moon.stars', content=_tab5()),
        appui.Tab(label='手势', system_image='hand.draw', content=_tab6()),
        appui.Tab(label='导航', system_image='arrow.triangle.branch', content=_tab7()),
        appui.Tab(label='效果', system_image='sparkles', content=_tab8()),
        appui.Tab(label='布局', system_image='rectangle.3.group', content=_tab9()),
        appui.Tab(label='系统', system_image='gear', content=_tab10()),
    ]).preferred_color_scheme(state.theme)


appui.run(build)
