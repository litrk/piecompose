"""Verify the first command, label and shortcut from an empty editor."""
import os
from pathlib import Path
import runpy
import tempfile
import bpy

root = Path(__file__).resolve().parents[1]
os.environ['PIE_MENU_DATA_PATH'] = str(Path(tempfile.mkdtemp(prefix='pie-empty-ui-')) / 'menus.json')
bpy.context.preferences.view.show_splash = False
demo = runpy.run_path(str(root / 'pie_prototype.py'))
cls = demo['WM_OT_pie_editor']
original_invoke = cls.invoke
instances = {}


def invoke(self, context, event):
    instances['editor'] = self
    return original_invoke(self, context, event)


cls.invoke = invoke
demo['register']()
assert not demo['KEYMAPS'] and not demo['LIBRARY'].palette


def exercise():
    bpy.ops.screen.screenshot(filepath=str(root / 'design-preview' / 'empty-editor.png'))
    editor = instances['editor']
    assert editor.item_kind == 'empty'
    assert editor.palette_choice == '__none__'
    editor.item_kind = 'command'
    editor.item_name = 'Smooth'
    editor.item_action = 'object.shade_smooth'
    editor.item_parameters = '{}'
    editor.apply_item = True
    menu = demo['LIBRARY'].menus[editor.menu_choice]
    assert menu.groups['RADIAL'][0].label == 'Smooth'
    assert menu.groups['RADIAL'][0].marker_color == 'none'
    editor.marker_mode = 'new'
    editor.marker_name = 'First label'
    editor.marker_color = (1.0, 0.5, 0.0)
    editor.save_label = True
    editor.assign_label = True
    assert demo['LIBRARY'].palette == {'#ff8000': 'First label'}
    menu = demo['LIBRARY'].menus[editor.menu_choice]
    assert menu.groups['RADIAL'][0].marker_color == '#ff8000'
    editor.delete_label = True
    assert not demo['LIBRARY'].palette
    editor.slot = 'RADIAL_1'
    assert editor.palette_choice == '__none__'
    editor.marker_mode = 'new'
    editor.marker_name = 'Replacement label'
    editor.marker_color = (0.0, 1.0, 0.0)
    editor.save_label = True
    editor.slot = 'RADIAL_0'
    assert editor.palette_choice == '#00ff00'
    assert demo['LIBRARY'].menus[editor.menu_choice].groups['RADIAL'][0].marker_color == 'none'
    editor.assign_label = True
    assert demo['LIBRARY'].menus[editor.menu_choice].groups['RADIAL'][0].marker_color == '#00ff00'
    draft = demo['hotkey_draft'](editor)
    draft.type = 'F8'
    editor.save_hotkey = True
    assert len(demo['KEYMAPS']) == 1
    assert demo['LIBRARY'].menus[editor.menu_choice].hotkey['type'] == 'F8'
    print('EMPTY_EDITOR_FIRST_COMMAND_LABEL_HOTKEY_PASSED', flush=True)
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1)


def show():
    area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
    region = next(region for region in area.regions if region.type == 'WINDOW')
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.wm.pie_editor('INVOKE_DEFAULT')
    bpy.app.timers.register(exercise, first_interval=1)


bpy.app.timers.register(show, first_interval=2)
