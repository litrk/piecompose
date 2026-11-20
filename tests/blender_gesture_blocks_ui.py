"""Native gesture timing, highlight and submenu checks for extra blocks."""
import math
import os
from pathlib import Path
import runpy
import tempfile
import traceback
import bpy

root = Path(__file__).resolve().parents[1]
os.environ['PIE_MENU_DATA_PATH'] = str(Path(tempfile.mkdtemp(prefix='pie-blocks-ui-')) / 'menus.json')
bpy.context.preferences.view.show_splash = False
demo = runpy.run_path(str(root / 'pie_prototype.py'))
runpy.run_path(str(Path(__file__).with_name('demo_library.py')))['install'](demo)
cls = demo['VIEW3D_OT_pie_prototype']
calls, highlights = [], []
original_draw = cls.draw_button


def draw(self, context, button, active, scale, extra=False):
    highlights[:] = [active.slot if active else None]
    return original_draw(self, context, button, active, scale, extra)


cls.draw_button = draw
cls.execute_item = lambda self, context, item: calls.append(item) or True
demo['register']()
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
window = bpy.context.window
origin = (region.width / 2, region.height / 2)


def center(button):
    a, b, c, d = button.rect
    return ((a + c) / 2, (b + d) / 2)


def event(kind, value, point):
    window.event_simulate(type=kind, value=value,
                          x=int(region.x + point[0]), y=int(region.y + point[1]))


def close():
    if cls.active:
        with bpy.context.temp_override(area=area, region=region):
            cls.active.cancel(bpy.context)
    event('ESC', 'PRESS', origin)
    event('ESC', 'RELEASE', origin)


def scenarios():
    # A single mouse move jumps straight to each extra button, with no dwell or
    # intermediate gap event. The held-key highlight must show the radial target.
    for group in range(2):
        for index in range(6):
            event('F8', 'PRESS', origin)
            yield 0.15
            active = cls.active
            assert active and active.holding
            layout = active.menu_layout()
            button = layout.blocks[group][1][index]
            point = center(button)
            dx, dy = point[0] - layout.center[0], point[1] - layout.center[1]
            expected = layout.radial[math.floor(math.atan2(dy, dx) / (math.pi / 4) + 0.5) % 8]
            before = len(calls)
            event('MOUSEMOVE', 'NOTHING', point)
            yield 0.15
            assert len(calls) == before, 'Movement alone executed a command'
            assert highlights == [expected.slot], (highlights, expected.slot)
            if group == 0 and index == 1:
                bpy.ops.screen.screenshot(filepath=str(root / 'design-preview/gesture-over-block.png'))
            event('F8', 'RELEASE', point)
            yield 0.15
            if expected.item.action == 'submenu':
                assert cls.active and cls.active._menu_id == expected.item.target_menu
                assert len(calls) == before
            else:
                assert cls.active is None and calls[before:] == [expected.item]
            close()
            yield 0.1

    for group in range(2):
        event('F8', 'PRESS', origin)
        yield 0.65  # Holding still must not spend the delay.
        active = cls.active
        layout = active.menu_layout()
        button = layout.blocks[group][1][1]
        left, bottom, right, top = button.rect
        point = ((left + right) / 2, bottom + 2 if group == 0 else top - 2)
        before = len(calls)
        event('MOUSEMOVE', 'NOTHING', point)
        yield 0.1
        assert highlights == [layout.radial[2 if group == 0 else 6].slot]
        yield 0.55  # No new mouse events. The deadline must redraw the menu.
        assert highlights == [button.slot], (highlights, button.slot)
        assert len(calls) == before
        event('F8', 'RELEASE', point)
        yield 0.15
        assert cls.active is None and calls[before:] == [button.item]

    # A click keeps its exact target, including while the invoking key is held.
    for group in range(2):
        event('F8', 'PRESS', origin)
        yield 0.15
        active = cls.active
        button = active.menu_layout().blocks[group][1][1]
        before = len(calls)
        point = center(button)
        event('MOUSEMOVE', 'NOTHING', point)
        event('LEFTMOUSE', 'PRESS', point)
        event('LEFTMOUSE', 'RELEASE', point)
        event('F8', 'RELEASE', point)
        yield 0.2
        assert cls.active is None and calls[before:] == [button.item]

    candidate = demo['clone_library'](demo['LIBRARY'])
    menu = candidate.menus['main']
    menu.groups['TOP'][1] = demo['Item']('Click submenu', 'submenu', target_menu='modeling')
    demo['save_library'](candidate)
    event('F8', 'PRESS', origin)
    yield 0.15
    active = cls.active
    point = center(active.menu_layout().blocks[0][1][1])
    before = len(calls)
    event('LEFTMOUSE', 'PRESS', point)
    event('LEFTMOUSE', 'RELEASE', point)
    event('F8', 'RELEASE', point)
    yield 0.2
    assert cls.active and cls.active._menu_id == 'modeling' and not cls.active.holding
    assert len(calls) == before, 'Original key release executed after submenu click'
    close()
    print('NATIVE_RADIAL_GESTURES_DELAYED_BLOCKS_PASSED', flush=True)


scenario = scenarios()


def step():
    try:
        return next(scenario)
    except StopIteration:
        pass
    except Exception:
        traceback.print_exc()
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=0.5)


bpy.app.timers.register(step, first_interval=2)
bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=35)
