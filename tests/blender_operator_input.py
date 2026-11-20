"""Write/read manual operator names; execute Bevel in its required mesh mode."""
import os
from pathlib import Path
import runpy
import sys
from dataclasses import replace
from types import MethodType, SimpleNamespace
import bmesh
import bpy

phase, path = sys.argv[sys.argv.index('--') + 1:]
os.environ['PIE_MENU_DATA_PATH'] = path
demo = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'pie_prototype.py'))
demo['register']()

if phase == 'write':
    cls = demo['WM_OT_pie_editor']
    editor = SimpleNamespace(_document=demo['clone_library'](demo['LIBRARY']),
                             menu_choice='main', slot='RADIAL_0', report=lambda *args: None)
    editor.load_fields = MethodType(cls.load_fields, editor)
    editor.load_fields()
    editor.item_kind = 'command'
    editor.item_name = 'Bevel'
    editor.item_action = 'bpy.ops.mesh.bevel'
    editor.item_parameters = '{"offset": 0.1, "segments": 2}'
    cls.perform(editor, 'apply_item')
    assert demo['LIBRARY'].menus['main'].groups['RADIAL'][0].action == 'mesh.bevel'
    assert bpy.ops.wm.pie_capture(command='bpy.ops.mesh.bevel()', caption='Bevel copy',
                                  destination_menu='main', slot='RADIAL_1') == {'FINISHED'}
    before = demo['STORE'].path.read_bytes()
    editor._document = demo['clone_library'](demo['LIBRARY'])
    editor.item_action = 'bpy.ops.mesh.bevel(offset=1)'
    cls.perform(editor, 'apply_item')
    assert demo['STORE'].path.read_bytes() == before
    assert 'Parameters JSON' in editor._message
    print('OPERATOR_NAME_INPUT_WRITE_PASSED', flush=True)
elif phase == 'read':
    item = demo['LIBRARY'].menus['main'].groups['RADIAL'][0]
    assert item.action == 'mesh.bevel' and item.invoke is True
    assert item.properties == {'offset': 0.1, 'segments': 2}
    assert demo['LIBRARY'].menus['main'].groups['RADIAL'][1].action == 'mesh.bevel'
    reports = []
    operator = SimpleNamespace(report=lambda level, message: reports.append(message))
    area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
    region = next(region for region in area.regions if region.type == 'WINDOW')
    with bpy.context.temp_override(area=area, region=region):
        assert not demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, item)
        assert any('unavailable' in message for message in reports)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        before = len(bmesh.from_edit_mesh(bpy.context.active_object.data).verts)
        assert demo['VIEW3D_OT_pie_prototype'].execute_item(operator, bpy.context, replace(item, invoke=False))
        assert len(bmesh.from_edit_mesh(bpy.context.active_object.data).verts) > before
        bpy.ops.object.mode_set(mode='OBJECT')
    print('OPERATOR_NAME_RESTART_BEVEL_EXECUTION_PASSED', flush=True)
else:
    raise ValueError(phase)

demo['unregister']()
