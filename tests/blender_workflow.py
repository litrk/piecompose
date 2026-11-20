"""Run twice with --python, passing write/read and a temporary data path after --."""

import os
from pathlib import Path
import runpy
import sys
from types import MethodType, SimpleNamespace
from dataclasses import replace

import bpy

phase, path = sys.argv[sys.argv.index('--') + 1:]
os.environ['PIE_MENU_DATA_PATH'] = path
demo = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'pie_prototype.py'))
runpy.run_path(str(Path(__file__).resolve().with_name('demo_library.py')))['install'](demo)
demo['register']()
library = demo['LIBRARY']
macro_rna = bpy.ops.object.duplicate_move.get_rna_type()
assert demo['restore_operator_parameters']({}, macro_rna, interactive=True)['TRANSFORM_OT_translate']['release_confirm'] is False
assert demo['restore_operator_parameters']({'TRANSFORM_OT_translate': {'release_confirm': True}},
                                           macro_rna, interactive=True)['TRANSFORM_OT_translate']['release_confirm'] is True

if phase == 'write':
    # Use the same capture operator as the right-click menu, with real RNA properties.
    km = bpy.context.window_manager.keyconfigs.addon.keymaps.new(name='Pie Workflow Test', space_type='VIEW_3D')
    try:
        for index, axis in enumerate(('FRONT', 'TOP')):
            button = km.keymap_items.new('view3d.view_axis', 'F7', 'PRESS')
            button.properties.type = axis
            command, caption, parameters = demo['capture_operator'](button.properties)
            assert bpy.ops.wm.pie_capture(command=command, caption=axis, parameters=parameters,
                                          slot=f'TOP_{index}', destination_menu='main',
                                          assigned_marker='#83a9d5' if index else 'none') == {'FINISHED'}
        for index, identifier in enumerate(('object.duplicate_move', 'object.duplicate_move_linked')):
            button = km.keymap_items.new(identifier, 'F6', 'PRESS')
            button.properties.OBJECT_OT_duplicate.linked = bool(index)
            button.properties.TRANSFORM_OT_translate.value = (1.25, 2.5, 3.75)
            button.properties.TRANSFORM_OT_translate.snap_elements = {'EDGE', 'VERTEX'}
            command, caption, parameters = demo['capture_operator'](button.properties)
            assert bpy.ops.wm.pie_capture(command=command, caption=caption, parameters=parameters,
                                          slot=f'TOP_{index + 2}', destination_menu='main') == {'FINISHED'}
    finally:
        bpy.context.window_manager.keyconfigs.addon.keymaps.remove(km)

    # Exercise the editor's actual mutations and saving methods.
    cls = demo['WM_OT_pie_editor']
    editor = SimpleNamespace(_document=demo['clone_library'](library), menu_choice='main',
                             slot='RADIAL_0', report=lambda *args: None)
    editor.load_fields = MethodType(cls.load_fields, editor)
    editor.load_fields()
    cls.perform(editor, 'new_menu')
    child_id = editor.menu_choice
    editor.menu_name = 'Saved child'
    cls.perform(editor, 'rename_menu')
    editor.item_kind, editor.item_name = 'command', 'Smooth saved'
    editor.item_action, editor.item_parameters = 'object.shade_smooth', '{}'
    editor.item_category, editor.item_invoke = 'menu', False
    cls.perform(editor, 'apply_item')
    editor.marker_mode, editor.marker_color = 'new', (1.0, 0.5, 0.0)
    editor.marker_name = 'Выделение'
    demo['PieOperatorState'].perform_label(editor, 'save_label')
    demo['PieOperatorState'].perform_label(editor, 'assign_label')
    editor.hotkey_enabled, editor.hotkey_type = True, 'F9'
    editor.hotkey_ctrl, editor.hotkey_shift, editor.hotkey_alt, editor.hotkey_oskey = True, True, False, False
    cls.perform(editor, 'save_hotkey')
    editor.move_target = 'BOTTOM_5'
    cls.perform(editor, 'move_item')
    assert library.menus[child_id].groups['BOTTOM'][5].label == 'Smooth saved'
    assert library.palette['#ff8000'] == 'Выделение'
    editor.menu_choice, editor.slot = 'main', 'RADIAL_0'
    editor.load_fields()
    editor.item_kind, editor.item_name, editor.target_menu = 'submenu', 'Open saved child', child_id
    cls.perform(editor, 'apply_item')
    settings = bpy.context.scene.tool_settings
    with bpy.context.temp_override(button_operator=None, button_pointer=settings,
                                  button_prop=settings.bl_rna.properties['use_transform_data_origin']):
        command, caption, parameters = demo['capture_button'](bpy.context)
        assert bpy.ops.wm.pie_capture(command=command, caption=caption, parameters=parameters,
                                      destination_menu='main', slot='TOP_4') == {'FINISHED'}
    print('WRITE_PHASE_PASSED', flush=True)
else:
    assert library.menus['main'].groups['TOP'][0].properties == {'type': 'FRONT'}
    assert library.menus['main'].groups['TOP'][1].properties == {'type': 'TOP'}
    link = library.menus['main'].groups['RADIAL'][0]
    child = library.menus[link.target_menu]
    assert child.name == 'Saved child'
    assert child.hotkey['type'] == 'F9' and child.hotkey['ctrl'] and child.hotkey['shift']
    assert any(item.type == 'F9' and item.ctrl and item.shift and item.properties.menu_id == link.target_menu
               for _, item in demo['KEYMAPS'])
    assert child.groups['BOTTOM'][5].label == 'Smooth saved'
    assert child.groups['BOTTOM'][5].marker_color == '#ff8000'
    assert library.palette['#ff8000'] == 'Выделение'
    assert library.menus['main'].groups['TOP'][0].marker_color == 'none'
    assert library.menus['main'].groups['TOP'][1].marker_color == '#83a9d5'
    assert child.groups['RADIAL'][0] is None
    layout = demo['PieLayout'](1200, 900, (600, 450), 1, menu=child)
    assert layout.radial[0] is None and len(layout.blocks[0][1]) == 1
    area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
    region = next(region for region in area.regions if region.type == 'WINDOW')
    rotations = []
    with bpy.context.temp_override(area=area, region=region):
        operator = SimpleNamespace(report=lambda *args: None)
        settings = bpy.context.scene.tool_settings
        toggle = library.menus['main'].groups['TOP'][4]
        assert toggle.action == 'wm.context_toggle'
        assert toggle.properties == {'data_path': 'scene.tool_settings.use_transform_data_origin'}
        settings.use_transform_data_origin = False
        assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, toggle)
        assert settings.use_transform_data_origin is True
        assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, toggle)
        assert settings.use_transform_data_origin is False
        for item in library.menus['main'].groups['TOP'][:2]:
            assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
            rotations.append(tuple(area.spaces.active.region_3d.view_rotation))
        assert rotations[0] != rotations[1]
        assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, child.groups['BOTTOM'][5])
        assert all(polygon.use_smooth for polygon in bpy.context.active_object.data.polygons)
        source = bpy.context.active_object
        for index, item in enumerate(library.menus['main'].groups['TOP'][2:4]):
            assert item.properties['OBJECT_OT_duplicate']['linked'] is bool(index)
            assert set(item.properties['TRANSFORM_OT_translate']['snap_elements']) == {'EDGE', 'VERTEX'}
            bpy.ops.object.select_all(action='DESELECT')
            source.select_set(True)
            bpy.context.view_layer.objects.active = source
            count = len(bpy.context.scene.objects)
            assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, replace(item, invoke=False))
            duplicate = bpy.context.active_object
            assert len(bpy.context.scene.objects) == count + 1 and duplicate != source
            assert (duplicate.data == source.data) is bool(index)
            assert all(abs(duplicate.location[axis] - source.location[axis] - offset) < 1e-5
                       for axis, offset in enumerate((1.25, 2.5, 3.75)))
    navigation = SimpleNamespace(_menu_id='main', history=[], holding=True, report=lambda *args: None)
    demo['VIEW3D_OT_pie_prototype'].open_submenu(navigation, link.target_menu)
    assert navigation._menu_id == link.target_menu and navigation.history == ['main']
    demo['VIEW3D_OT_pie_prototype'].navigate_back(navigation)
    assert navigation._menu_id == 'main' and not navigation.history
    # Escape release must not close the parent immediately after going back.
    cls = demo['VIEW3D_OT_pie_prototype']
    navigation = SimpleNamespace(_menu_id=link.target_menu, history=['main'], holding=False,
                                 handler=True, area=SimpleNamespace(tag_redraw=lambda: None),
                                 mouse=lambda event: (600, 450), menu_layout=lambda: layout,
                                 cancel=lambda context: setattr(navigation, 'handler', None))
    navigation.navigate_back = MethodType(cls.navigate_back, navigation)
    for value in ('PRESS', 'RELEASE'):
        assert cls.modal(navigation, bpy.context, SimpleNamespace(type='ESC', value=value)) == {'RUNNING_MODAL'}
    assert navigation._menu_id == 'main' and navigation.handler is True
    triggered = []
    navigation.trigger_key = 'F9'
    navigation.execute_item = lambda context, item: triggered.append(item) or True
    navigation.mouse = lambda event: layout.center
    assert cls.modal(navigation, bpy.context, SimpleNamespace(type='F9', value='PRESS', is_repeat=False)) == {'RUNNING_MODAL'}
    assert navigation.holding
    gesture_layout = demo['PieLayout'](1400, 1000, (700, 500), 1, menu=library.menus['main'])
    navigation.menu_layout = lambda: gesture_layout
    navigation.gesture_start = gesture_layout.center
    rect = gesture_layout.radial[2].rect
    navigation.mouse = lambda event: ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
    assert cls.modal(navigation, bpy.context, SimpleNamespace(type='F9', value='RELEASE')) == {'FINISHED'}
    assert triggered == [gesture_layout.radial[2].item]
    navigation.menu_layout = lambda: layout
    for point in ((600, 450), (5, 5)):
        navigation.history = []
        navigation.handler = True
        navigation.mouse = lambda event, point=point: point
        assert cls.modal(navigation, bpy.context, SimpleNamespace(type='LEFTMOUSE', value='PRESS')) == {'CANCELLED'}
        assert navigation.handler is None
    navigation.history = ['main']
    navigation._menu_id = link.target_menu
    navigation.handler = True
    navigation.mouse = lambda event: layout.center
    assert cls.modal(navigation, bpy.context, SimpleNamespace(type='LEFTMOUSE', value='PRESS')) == {'RUNNING_MODAL'}
    assert navigation._menu_id == 'main' and navigation.handler is True
    layout = demo['PieLayout'](1400, 1000, (700, 500), 1, menu=library.menus['main'])
    dimensions = {(round(b.rect[2] - b.rect[0], 4), round(b.rect[3] - b.rect[1], 4))
                  for b in list(layout.radial) + [b for _, buttons in layout.blocks for b in buttons] if b}
    assert len(dimensions) == 1, dimensions
    radial_top = max(b.rect[3] for b in layout.radial if b)
    radial_bottom = min(b.rect[1] for b in layout.radial if b)
    for rect, buttons in layout.blocks:
        gap = rect[1] - radial_top if rect[1] > layout.center[1] else radial_bottom - rect[3]
        assert gap >= 40 * layout.scale - 1e-6, gap
    print('RESTART_AND_EXECUTION_PASSED', flush=True)

demo['unregister']()
