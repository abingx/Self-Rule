import threading
import time

import appui
import sound

state = appui.State(
    freq=180,
    angle=0.0,
    running=False,
    show_input=False,
    input_text='180',
)


def normalize_freq(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = state.freq
    return max(1, value)


def set_freq(value):
    value = normalize_freq(value)
    state.freq = value
    state.input_text = str(value)


def increment_freq():
    set_freq(state.freq + 1)


def decrement_freq():
    set_freq(state.freq - 1)


def show_number_input():
    state.show_input = True


def cancel_number_input():
    state.show_input = False


def save_number_input():
    set_freq(state.input_text)
    state.show_input = False


def start_stop():
    state.running = not state.running
    if state.running:
        _spawn_pointer_loop()
    else:
        state.angle = 0.0
        sound.stop_all_effects()


def _spawn_pointer_loop():
    def pointer_loop():
        while state.running:
            interval = max(0.05, 60.0 / max(1, state.freq))
            state.angle = -45.0
            time.sleep(interval / 2)
            if not state.running:
                break
            state.angle = 45.0
            sound.play_effect('ui:click1', volume=1.0)
            time.sleep(interval / 2)
        if not state.running:
            state.angle = 0.0

    thread = threading.Thread(target=pointer_loop, daemon=True)
    thread.start()


def pointer_section():
    return appui.VStack([
        appui.Text('摆动指针').font('title2').bold(),
        appui.ZStack([
            appui.Text('◯').font('system', size=130).foreground_color('secondary'),
            appui.Text('▲')
            .font('system', size=68)
            .foreground_color('red')
            .rotation_effect(degrees=state.angle)
            .animation('ease_in_out'),
        ]).frame(height=280),
    ], alignment='center', spacing=16).padding(0)


def control_section():
    return appui.HStack([
        appui.Button('-', action=decrement_freq)
        .font('title2')
        .button_style('bordered'),
        appui.Button(str(state.freq), action=show_number_input)
        .font('title2')
        .button_style('bordered_prominent')
        .frame(min_width=100, min_height=58),
        appui.Button('+', action=increment_freq)
        .font('title2')
        .button_style('bordered'),
    ], alignment='center', spacing=20)


def action_section():
    label = '停止' if state.running else '开始'
    return (
        appui.Button(label, action=start_stop)
        .button_style('bordered_prominent')
        .font('title2')
        .frame(min_height=72)
    )


def number_input_sheet():
    return appui.VStack([
        appui.Text('设置频率').font('title2').bold(),
        appui.TextField('请输入频率', text=state.input_text, on_change=lambda v: setattr(state, 'input_text', v))
        .keyboard_type('number_pad')
        .padding(12)
        .background('secondary_system_fill', corner_radius=12),
        appui.HStack([
            appui.Button('取消', action=cancel_number_input).button_style('bordered'),
            appui.Button('保存', action=save_number_input).button_style('bordered_prominent'),
        ], spacing=16),
    ], spacing=18).padding()


def body():
    return appui.VStack([
        pointer_section().frame(height=320),
        control_section().frame(height=180),
        action_section().frame(height=120),
    ], spacing=24).padding(24).sheet(
        is_presented=state.show_input,
        content=number_input_sheet,
    )


appui.run(body, state=state, presentation='fullscreen_with_close')

