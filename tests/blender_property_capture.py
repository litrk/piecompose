"""Run write/read with one temporary JSON: generic RNA checkbox capture."""
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import bpy

phase, path = sys.argv[sys.argv.index('--') + 1:]
os.environ['PIE_MENU_DATA_PATH'] = path
demo = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'pie_prototype.py'))
demo['register']()
area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
region = next(region for region in area.regions if region.type == 'WINDOW')


def setup_object(obj):
    material = bpy.data.materials.new(obj.name + ' material')
    obj.data.materials.append(material)
    obj.active_material_index = len(obj.data.materials) - 1
    modifier = obj.modifiers.new('Bevel "quoted" \\ name', 'BEVEL')
    obj.modifiers.active = modifier
    return material, modifier


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
    cube = bpy.context.active_object
    material, modifier = setup_object(cube)
    group = cube.vertex_groups.new(name='Original group')
    node = material.node_tree.nodes.new('ShaderNodeValue')
    material.node_tree.nodes.active = node
    if phase == 'write':
        cases = [
            (cube, 'show_in_front', 'active_object.show_in_front'),
            (material, 'use_backface_culling', 'active_object.active_material.use_backface_culling'),
            (bpy.context.scene.render, 'film_transparent', 'scene.render.film_transparent'),
            (modifier, 'show_viewport', 'active_object.modifiers.active.show_viewport'),
            (cube.data, 'use_mirror_x', 'active_object.data.use_mirror_x'),
            (bpy.context.scene.world, 'use_sun_shadow', 'scene.world.use_sun_shadow'),
            (cube, 'hide_render', 'active_object.hide_render'),
            (modifier, 'use_clamp_overlap', 'active_object.modifiers.active.use_clamp_overlap'),
        ]
        for index, (owner, name, expected) in enumerate(cases):
            before = getattr(owner, name)
            with bpy.context.temp_override(button_operator=None, button_pointer=owner,
                                          button_prop=owner.bl_rna.properties[name]):
                layout = Layout()
                demo['draw_button_context'](SimpleNamespace(layout=layout), bpy.context)
                assert len(layout.buttons) == 1
                button = layout.buttons[0]
                assert json.loads(button.parameters) == {'data_path': expected}, button.parameters
                assert bpy.ops.wm.pie_capture(command=button.command, caption=button.caption,
                                              parameters=button.parameters, destination_menu='main',
                                              slot=f'RADIAL_{index}') == {'FINISHED'}
            assert getattr(owner, name) == before
        for owner, name, expected, slot in (
            (group, 'lock_weight', 'active_object.vertex_groups.active.lock_weight', 'TOP_0'),
            (node, 'mute', 'active_object.active_material.node_tree.nodes.active.mute', 'TOP_1'),
        ):
            with bpy.context.temp_override(button_operator=None, button_pointer=owner,
                                          button_prop=owner.bl_rna.properties[name]):
                command, caption, parameters = demo['capture_button'](bpy.context)
                assert json.loads(parameters) == {'data_path': expected}, parameters
                assert bpy.ops.wm.pie_capture(command=command, caption=caption, parameters=parameters,
                                              destination_menu='main', slot=slot) == {'FINISHED'}
        # Preferences have no path_from_id: the same mechanism discovers their
        # pointer graph. Capture only; never change or save user preferences.
        inputs = bpy.context.preferences.inputs
        with bpy.context.temp_override(button_operator=None, button_pointer=inputs,
                                      button_prop=inputs.bl_rna.properties['use_mouse_emulate_3_button']):
            captured = demo['capture_button'](bpy.context)
            assert json.loads(captured[2]) == {'data_path': 'preferences.inputs.use_mouse_emulate_3_button'}
        print('GENERIC_RNA_CAPTURE_WRITE_PASSED', flush=True)
    elif phase == 'read':
        items = demo['LIBRARY'].menus['main'].groups['RADIAL']
        reports = []
        operator = SimpleNamespace(report=lambda level, message: reports.append((level, message)))

        def toggle(item, owner, name):
            setattr(owner, name, False)
            assert demo['toggle_state'](bpy.context, item) is False
            assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
            assert getattr(owner, name) is True
            assert demo['toggle_state'](bpy.context, item) is True
            assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
            assert getattr(owner, name) is False

        toggle(items[0], cube, 'show_in_front')
        toggle(items[1], material, 'use_backface_culling')
        toggle(items[2], bpy.context.scene.render, 'film_transparent')
        modifier.name = 'Renamed after capture'
        toggle(items[3], modifier, 'show_viewport')
        toggle(items[4], cube.data, 'use_mirror_x')
        toggle(items[5], bpy.context.scene.world, 'use_sun_shadow')
        toggle(items[6], cube, 'hide_render')
        toggle(items[7], modifier, 'use_clamp_overlap')
        group.name = 'Renamed group'
        toggle(demo['LIBRARY'].menus['main'].groups['TOP'][0], group, 'lock_weight')
        node.name = 'Renamed node'
        toggle(demo['LIBRARY'].menus['main'].groups['TOP'][1], node, 'mute')
        bpy.ops.mesh.primitive_uv_sphere_add()
        sphere = bpy.context.active_object
        sphere_material, sphere_modifier = setup_object(sphere)
        toggle(items[0], sphere, 'show_in_front')
        toggle(items[1], sphere_material, 'use_backface_culling')
        toggle(items[3], sphere_modifier, 'show_viewport')
        assert cube.show_in_front is False and material.use_backface_culling is False
        mirror = sphere.modifiers.new('Different type', 'MIRROR')
        sphere_modifier.use_clamp_overlap = False
        sphere.modifiers.active = mirror
        assert not demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, items[7])
        assert sphere_modifier.use_clamp_overlap is False
        toggle(items[3], mirror, 'show_viewport')
        sphere.modifiers.remove(mirror)
        sphere.modifiers.remove(sphere_modifier)
        assert demo['toggle_state'](bpy.context, items[3]) is None
        assert not demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, items[3])
        assert len(sphere.modifiers) == 0
        sphere.data.materials.clear()
        assert not demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, items[1])
        # Wrong object data type must not modify some unrelated target.
        camera_data = bpy.data.cameras.new('Camera data')
        camera = bpy.data.objects.new('Camera target', camera_data)
        bpy.context.scene.collection.objects.link(camera)
        bpy.context.view_layer.objects.active = camera
        assert not demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, items[4])
        bpy.context.view_layer.objects.active = None
        assert demo['toggle_state'](bpy.context, items[0]) is None
        assert not demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, items[0])
        assert any('missing or read-only' in message for _, message in reports)
        bpy.context.view_layer.objects.active = cube
        readonly = demo['replace'](items[0], properties={'data_path': 'active_object.is_editable'})
        assert not demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, readonly)
        print('GENERIC_RNA_CAPTURE_RESTART_ACTIVE_TARGETS_PASSED', flush=True)
    else:
        raise ValueError(phase)

demo['unregister']()
