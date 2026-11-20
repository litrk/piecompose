"""Save a copied bpy.ops name, click its pie button and test modal Bevel."""
import os
from pathlib import Path
import runpy
import tempfile
import traceback
import bmesh
import bpy

root = Path(__file__).resolve().parents[1]
os.environ['PIE_MENU_DATA_PATH'] = str(Path(tempfile.mkdtemp(prefix='pie-bevel-ui-')) / 'menus.json')
bpy.context.preferences.view.show_splash = False
demo = runpy.run_path(str(root / 'pie_prototype.py'))
instances = {}
cls = demo['WM_OT_pie_editor']
original = cls.invoke


def invoke(self, context, event):
    instances['editor'] = self
    return original(self, context, event)


cls.invoke = invoke
demo['register']()
area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
region = next(region for region in area.regions if region.type == 'WINDOW')
window = bpy.context.window


def event(kind, value, x=None, y=None):
    args = {} if x is None else {'x': int(x), 'y': int(y)}
    window.event_simulate(type=kind, value=value, **args)


def bevel_active():
    return any(operator.bl_idname == 'MESH_OT_bevel' for operator in window.modal_operators)


def scenarios():
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.wm.pie_editor('INVOKE_DEFAULT')
    yield 0.5
    editor = instances.pop('editor')
    editor.item_kind = 'command'
    editor.item_name = 'Bevel'
    editor.item_action = 'bpy.ops.mesh.bevel'
    editor.item_parameters = '{"segments": 2}'
    editor.apply_item = True
    assert demo['LIBRARY'].menus['main'].groups['RADIAL'][0].action == 'mesh.bevel'
    event('ESC', 'PRESS')
    event('ESC', 'RELEASE')
    yield 0.5
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        assert bpy.ops.view3d.pie_prototype('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
        active = demo['VIEW3D_OT_pie_prototype'].active
        active.origin = active.point = (region.width / 2, region.height / 2)
        area.tag_redraw()
    yield 0.5
    button = active.menu_layout().radial[0]
    x = region.x + (button.rect[0] + button.rect[2]) / 2
    y = region.y + (button.rect[1] + button.rect[3]) / 2
    event('MOUSEMOVE', 'NOTHING', x, y)
    event('LEFTMOUSE', 'PRESS', x, y)
    event('LEFTMOUSE', 'RELEASE', x, y)
    yield 0.5
    assert demo['VIEW3D_OT_pie_prototype'].active is None
    assert bevel_active(), 'Bevel did not stay interactive after the pie click/release'
    event('MOUSEMOVE', 'NOTHING', x + 60, y + 20)
    yield 0.5
    assert bevel_active()
    assert len(bmesh.from_edit_mesh(bpy.context.active_object.data).verts) > 8
    bpy.ops.screen.screenshot(filepath=str(root / 'design-preview/bevel-interactive.png'))
    event('ESC', 'PRESS')
    event('ESC', 'RELEASE')
    yield 0.5
    assert not bevel_active()
    assert len(bmesh.from_edit_mesh(bpy.context.active_object.data).verts) == 8
    print('BEVEL_MANUAL_INPUT_PIE_CLICK_MODAL_PASSED', flush=True)


scenario = scenarios()


def step():
    try:
        return next(scenario)
    except StopIteration:
        pass
    except Exception:
        traceback.print_exc()
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=0.5)
    return None


bpy.app.timers.register(step, first_interval=2)
bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=20)
