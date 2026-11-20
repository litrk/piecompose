"""Blender background regression tests; optional --pie-ui-preview screenshot."""

import math
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace

import bpy

root = Path(__file__).resolve().parents[1]
os.environ['PIE_MENU_DATA_PATH'] = str(Path(tempfile.mkdtemp(prefix='pie-gesture-')) / 'menus.json')
demo = runpy.run_path(str(root / 'pie_prototype.py'))
runpy.run_path(str(Path(__file__).resolve().with_name('demo_library.py')))['install'](demo)
menu = demo['LIBRARY'].menus['main']
if '--pie-ui-property-toggle' in sys.argv:
    menu.groups['TOP'][1] = demo['replace'](
        menu.groups['TOP'][1], action='wm.context_toggle',
        properties={'data_path': 'scene.tool_settings.use_transform_data_origin'})


def center(button):
    left, bottom, right, top = button.rect
    return ((left + right) / 2, (bottom + top) / 2)


def direction(layout, point):
    dx, dy = point[0] - layout.center[0], point[1] - layout.center[1]
    return layout.radial[math.floor(math.atan2(dy, dx) / (math.pi / 4) + 0.5) % 8]


for width, height, origin, scale in ((1400, 1000, (700, 500), 1),
                                     (800, 600, (2, 598), 1.5),
                                     (1000, 720, (998, 2), 1)):
    layout = demo['PieLayout'](width, height, origin, scale, menu=menu)
    cx, cy = layout.center
    for index in range(8):
        angle = index * math.pi / 4
        point = (cx + 420 * layout.scale * math.cos(angle),
                 cy + 420 * layout.scale * math.sin(angle))
        assert layout.target(point, gesture=True) is layout.radial[index]
        assert layout.target(point) is None
    assert layout.target(layout.center, gesture=True) is None
    for rect, buttons in layout.blocks:
        assert len({round(center(button)[0], 4) for button in buttons}) == 3
        assert len({round(center(button)[1], 4) for button in buttons}) == 2
        for button in buttons:
            assert layout.target(center(button), gesture=True) is direction(layout, center(button))
            assert layout.target(center(button)) is button
            left, bottom, right, top = button.rect
            assert left >= 0 and bottom >= 0 and right <= width and top <= height
        y = (rect[1] + rect[3]) / 2
        expected = layout.radial[2 if y > cy else 6]
        # The row gap and the gaps between columns must not swallow gestures.
        assert layout.target((cx, y), gesture=True) is expected
        assert layout.target((cx, y)) is None
        upper_y = max(center(button)[1] for button in buttons)
        x = cx + (demo['STYLE']['extraWidth'] + demo['STYLE']['columnGap']) / 2 * layout.scale
        assert layout.target((x, upper_y)) is None
        assert layout.target((x, upper_y), gesture=True) is expected
    for button in layout.radial:
        assert layout.target(center(button), gesture=True) is button

# Check both sides of the delay in the actual release branch.
cls = demo['VIEW3D_OT_pie_prototype']
layout = demo['PieLayout'](1400, 1000, (700, 500), 1, menu=menu)
assert all(button is None or button.suffix == '' for button in layout.radial)
points = [(center(button), direction(layout, center(button)), None)
          for _, buttons in layout.blocks for button in buttons]
points += [(center(button), button, 0) for _, buttons in layout.blocks for button in buttons]
points += [(center(button), button, None) for button in layout.radial if button]
points += [((layout.center[0], (rect[1] + rect[3]) / 2), layout.radial[2 if rect[1] > layout.center[1] else 6], 0)
           for rect, _ in layout.blocks]
points.append((layout.center, None, 0))
for point, expected, deadline in points:
    calls = []
    operator = SimpleNamespace(
        handler=True, history=[], trigger_key='F8', holding=True, gesture_start=layout.center,
        extra_gesture_ready_at=deadline,
        mouse=lambda event, point=point: point, menu_layout=lambda: layout,
        area=SimpleNamespace(tag_redraw=lambda: None),
        cancel=lambda context: calls.append('cancel'),
        execute_item=lambda context, item: calls.append(item) or True,
        open_submenu=lambda target: calls.append(target), navigate_back=lambda: calls.append('back'),
    )
    result = cls.modal(operator, bpy.context, SimpleNamespace(type='F8', value='RELEASE'))
    if expected is None:
        assert not calls and result == {'RUNNING_MODAL'}
    elif expected.item.action == 'submenu':
        assert calls == [expected.item.target_menu] and result == {'RUNNING_MODAL'}
    else:
        assert calls == ['cancel', expected.item] and result == {'FINISHED'}

# Both blocks still execute immediately on click, whether or not the invocation
# key is held. A submenu click must ignore the subsequent key release.
for holding in (False, True):
    for _, buttons in layout.blocks:
        for button in buttons:
            calls = []
            operator = SimpleNamespace(
                handler=True, history=[], trigger_key='F8', holding=holding,
                gesture_start=layout.center, mouse=lambda event, button=button: center(button),
                menu_layout=lambda: layout, area=SimpleNamespace(tag_redraw=lambda: None),
                cancel=lambda context: calls.append('cancel'),
                execute_item=lambda context, item: calls.append(item) or True)
            assert cls.modal(operator, bpy.context, SimpleNamespace(type='LEFTMOUSE', value='PRESS')) == {'FINISHED'}
            assert calls == ['cancel', button.item]

linked = demo['clone_library'](demo['LIBRARY']).menus['main']
linked.groups['TOP'][1] = demo['Item']('Extra submenu', 'submenu', target_menu='modeling')
linked_layout = demo['PieLayout'](1400, 1000, (700, 500), 1, menu=linked)
link = next(button for _, buttons in linked_layout.blocks for button in buttons if button.item.action == 'submenu')
operator = SimpleNamespace(
    handler=True, history=[], _menu_id='main', trigger_key='F8', holding=True,
    gesture_start=linked_layout.center, mouse=lambda event: center(link),
    menu_layout=lambda: linked_layout, area=SimpleNamespace(tag_redraw=lambda: None))
operator.open_submenu = lambda target: cls.open_submenu(operator, target)
assert cls.modal(operator, bpy.context, SimpleNamespace(type='LEFTMOUSE', value='PRESS')) == {'RUNNING_MODAL'}
assert operator._menu_id == 'modeling' and not operator.holding
assert cls.modal(operator, bpy.context, SimpleNamespace(type='F8', value='RELEASE')) == {'RUNNING_MODAL'}

# NumPad no longer selects sectors; only the invoking shortcut and pointer do.
calls = []
operator = SimpleNamespace(
    handler=True, history=[], trigger_key='F8', holding=False, gesture_start=layout.center,
    mouse=lambda event: center(layout.radial[0]), menu_layout=lambda: layout,
    area=SimpleNamespace(tag_redraw=lambda: None),
    cancel=lambda context: calls.append('cancel'),
    execute_item=lambda context, item: calls.append(item),
)
for key in ('NUMPAD_1', 'NUMPAD_2', 'NUMPAD_3', 'NUMPAD_4', 'NUMPAD_6', 'NUMPAD_7', 'NUMPAD_8', 'NUMPAD_9'):
    assert cls.modal(operator, bpy.context, SimpleNamespace(type=key, value='PRESS')) == {'RUNNING_MODAL'}
assert not calls

# Empty slots keep their directions; they are not replaced by adjacent commands.
empty = demo['clone_library'](demo['LIBRARY']).menus['main']
empty.groups['RADIAL'][2] = None
empty.groups['TOP'][1] = None
layout = demo['PieLayout'](1400, 1000, (700, 500), 1, menu=empty)
assert layout.target((layout.center[0], layout.center[1] + 420 * layout.scale), gesture=True) is None
for _, buttons in layout.blocks:
    for button in buttons:
        assert layout.target(center(button), gesture=True) is direction(layout, center(button))
assert layout.target(layout.center) is None
print('RADIAL_GESTURES_DELAYED_BLOCKS_3X2_PASSED', flush=True)

if '--pie-ui-preview' in sys.argv:
    bpy.context.preferences.view.show_splash = False
    demo['register']()
    if '--pie-marker-compare' in sys.argv:
        cls.marker_shape = 'bar' if '--pie-marker-bar' in sys.argv else 'dot'
    elif '--pie-marker-bar' in sys.argv:
        cls.marker_shape = 'bar'

    def capture():
        filename = 'blender-button-priority.png'
        if '--pie-marker-compare' in sys.argv:
            filename = 'markers-bars.png' if cls.marker_shape == 'bar' else 'markers-dots.png'
        bpy.ops.screen.screenshot(filepath=str(root / 'design-preview' / filename))
        print('BUTTON_PRIORITY_UI_CAPTURED', flush=True)
        if '--pie-ui-auto-close' in sys.argv:
            bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1)

    def show_menu():
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.view3d.pie_prototype('INVOKE_DEFAULT')
            active = cls.active
            active.origin = active.point = (region.width / 2, region.height / 2)
            if '--pie-ui-hover' in sys.argv:
                active.point = center(active.menu_layout().radial[2])
            if '--pie-ui-checkbox' in sys.argv:
                bpy.context.scene.tool_settings.use_transform_data_origin = True
                active.point = center(active.menu_layout().blocks[0][1][1])
            area.tag_redraw()
        bpy.app.timers.register(capture, first_interval=1)

    bpy.app.timers.register(show_menu, first_interval=2)
