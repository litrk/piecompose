"""Capture both X-Ray property buttons, persist, and execute in both draw modes."""
import json
import os
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
import bpy

os.environ['PIE_MENU_DATA_PATH'] = str(Path(tempfile.mkdtemp(prefix='pie-xray-')) / 'menus.json')
demo = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'pie_prototype.py'))
demo['register']()
area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
region = next(region for region in area.regions if region.type == 'WINDOW')


class Layout:
    def __init__(self):
        self.buttons = []

    def separator(self):
        pass

    def operator(self, identifier, **kwargs):
        assert identifier == 'wm.pie_capture'
        button = SimpleNamespace()
        self.buttons.append(button)
        return button


with bpy.context.temp_override(area=area, region=region):
    shading = area.spaces.active.shading
    for index, (mode, name) in enumerate((('SOLID', 'show_xray'), ('WIREFRAME', 'show_xray_wireframe'))):
        shading.type = mode
        with bpy.context.temp_override(button_operator=None, button_pointer=shading,
                                      button_prop=shading.bl_rna.properties[name]):
            layout = Layout()
            demo['draw_button_context'](SimpleNamespace(layout=layout), bpy.context)
            assert len(layout.buttons) == 1
            button = layout.buttons[0]
            assert button.command == 'view3d.toggle_xray'
            assert json.loads(button.parameters) == {}
            assert bpy.ops.wm.pie_capture(command=button.command, caption=button.caption,
                                          parameters=button.parameters, destination_menu='main',
                                          slot=f'RADIAL_{index}') == {'FINISHED'}
    # Other supported shading booleans use the generic property capture path.
    with bpy.context.temp_override(button_operator=None, button_pointer=shading,
                                  button_prop=shading.bl_rna.properties['show_shadows']):
        captured = demo['capture_button'](bpy.context)
        assert captured[0] == 'wm.context_toggle'
        assert json.loads(captured[2]) == {'data_path': 'space_data.shading.show_shadows'}
    # Header/menu operator buttons continue through the normal capture path.
    keymap = bpy.context.window_manager.keyconfigs.addon.keymaps.new(name='Pie X-Ray QA', space_type='VIEW_3D')
    key = keymap.keymap_items.new('view3d.toggle_xray', 'X', 'PRESS')
    with bpy.context.temp_override(button_operator=key.properties):
        assert demo['capture_button'](bpy.context)[0] == 'view3d.toggle_xray'
    keymap.keymap_items.remove(key)
    bpy.context.window_manager.keyconfigs.addon.keymaps.remove(keymap)
    saved = demo['STORE'].load()
    operator = SimpleNamespace(report=lambda *args: None)
    # Each saved button must follow the current draw mode, irrespective of
    # which property button it originally came from. It toggles, never sets.
    for item in saved.menus['main'].groups['RADIAL'][:2]:
        for mode, name in (('SOLID', 'show_xray'), ('WIREFRAME', 'show_xray_wireframe')):
            shading.type = mode
            setattr(shading, name, False)
            assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
            assert getattr(shading, name) is True
            assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
            assert getattr(shading, name) is False

demo['unregister']()
print('XRAY_CAPTURE_PERSIST_AND_TOGGLE_PASSED', flush=True)
