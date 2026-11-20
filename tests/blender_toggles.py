"""Capture Tools/Viewport booleans, persist and toggle in the active context."""
import json
import os
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
import bpy

os.environ['PIE_MENU_DATA_PATH'] = str(Path(tempfile.mkdtemp(prefix='pie-toggles-')) / 'menus.json')
demo = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'pie_prototype.py'))
demo['register']()
area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
region = next(region for region in area.regions if region.type == 'WINDOW')
cases = [
    ('scene.tool_settings', 'use_transform_data_origin'),
    ('scene.tool_settings', 'use_transform_pivot_point_align'),
    ('scene.tool_settings', 'use_transform_skip_children'),
    ('space_data.shading', 'show_shadows'),
    ('space_data.overlay', 'show_floor'),
    ('space_data', 'show_gizmo'),
]


def owner_at(context, path):
    owner = context
    for part in path.split('.'):
        owner = getattr(owner, part)
    return owner


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
    for index, (path, name) in enumerate(cases):
        owner = owner_at(bpy.context, path)
        original = getattr(owner, name)
        with bpy.context.temp_override(button_operator=None, button_pointer=owner,
                                      button_prop=owner.bl_rna.properties[name]):
            layout = Layout()
            demo['draw_button_context'](SimpleNamespace(layout=layout), bpy.context)
            assert len(layout.buttons) == 1
            button = layout.buttons[0]
            assert button.command == 'wm.context_toggle'
            assert json.loads(button.parameters) == {'data_path': f'{path}.{name}'}
            assert getattr(owner, name) == original, 'Capture changed the source toggle'
            assert bpy.ops.wm.pie_capture(command=button.command, caption=button.caption,
                                          parameters=button.parameters, destination_menu='main',
                                          slot=f'RADIAL_{index}') == {'FINISHED'}
    saved = demo['STORE'].load()
    operator = SimpleNamespace(report=lambda *args: None)
    for index, (path, name) in enumerate(cases):
        owner = owner_at(bpy.context, path)
        item = saved.menus['main'].groups['RADIAL'][index]
        setattr(owner, name, False)
        assert demo['toggle_state'](bpy.context, item) is False
        assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
        assert getattr(owner, name) is True
        assert demo['toggle_state'](bpy.context, item) is True
        assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
        assert getattr(owner, name) is False
    # Numeric controls and arbitrary scene properties are not accepted as booleans.
    with bpy.context.temp_override(button_operator=None, button_pointer=area.spaces.active.shading,
                                  button_prop=area.spaces.active.shading.bl_rna.properties['xray_alpha']):
        assert demo['capture_button'](bpy.context) is None
    assert demo['resolve_boolean_property'](bpy.context, 'space_data.shading.show_shadows;invalid') is None
    assert demo['resolve_boolean_property'](bpy.context, 'scene.objects[0].hide_render') is not None
    obj = bpy.context.active_object
    with bpy.context.temp_override(button_operator=None, button_pointer=obj,
                                  button_prop=obj.bl_rna.properties['show_in_front']):
        captured = demo['capture_button'](bpy.context)
        assert captured[0] == 'wm.context_toggle'
        assert json.loads(captured[2]) == {'data_path': 'active_object.show_in_front'}

# Saved buttons follow the current scene, not the capture source.
scene = bpy.data.scenes.new('Toggle target')
with bpy.context.temp_override(area=area, region=region, scene=scene):
    item = saved.menus['main'].groups['RADIAL'][0]
    scene.tool_settings.use_transform_data_origin = False
    assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
    assert scene.tool_settings.use_transform_data_origin is True
assert bpy.context.scene.tool_settings.use_transform_data_origin is False

# Saved viewport buttons likewise follow another active viewport.
other = next(candidate for candidate in bpy.context.screen.areas if candidate != area)
original_type = other.type
other.type = 'VIEW_3D'
other_region = next(region for region in other.regions if region.type == 'WINDOW')
with bpy.context.temp_override(area=other, region=other_region):
    item = saved.menus['main'].groups['RADIAL'][3]
    other.spaces.active.shading.show_shadows = False
    assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
    assert other.spaces.active.shading.show_shadows is True
assert area.spaces.active.shading.show_shadows is False
other.type = original_type
demo['unregister']()
print('TOOLS_VIEWPORT_TOGGLE_CAPTURE_PERSIST_CONTEXT_PASSED', flush=True)
