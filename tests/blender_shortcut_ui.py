"""Native single-chord button save/restart, keymap lookup and modal execution."""
import os
from pathlib import Path
import runpy
import sys
import traceback
import bmesh
import bpy

phase, path = sys.argv[sys.argv.index('--') + 1:]
os.environ['PIE_MENU_DATA_PATH'] = path
bpy.context.preferences.view.show_splash = False
demo = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'pie_prototype.py'))
instances = {}
cls = demo['WM_OT_pie_editor']
original_invoke = cls.invoke


def invoke(self, context, event):
    instances['editor'] = self
    return original_invoke(self, context, event)


cls.invoke = invoke
demo['register']()
area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
region = next(region for region in area.regions if region.type == 'WINDOW')
window = bpy.context.window


def event(kind, value, x=None, y=None):
    args = {} if x is None else {'x': int(x), 'y': int(y)}
    window.event_simulate(type=kind, value=value, **args)


def scenarios():
    chord = {'type': 'B', 'ctrl': True}
    if phase == 'read':
        with bpy.context.temp_override(area=area, region=region):
            source = demo['shortcut_command'](bpy.context, chord)
            assert source is None or source.idname != 'mesh.bevel', 'Object Mode used the Mesh keymap'
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        source = demo['shortcut_command'](bpy.context, chord)
        assert source is not None and source.idname == 'mesh.bevel'
        vertex = demo['shortcut_command'](bpy.context, {'type': 'B', 'ctrl': True, 'shift': True})
        assert vertex is not None and vertex.idname == 'mesh.bevel'
        assert demo['capture_operator_properties'](vertex.properties)['affect'] == 'VERTICES'
        bpy.ops.wm.pie_editor('INVOKE_DEFAULT')
    yield 0.5
    editor = instances.pop('editor')
    if phase == 'write':
        editor.item_kind = 'shortcut'
        draft = demo['shortcut_draft'](editor)
        assert draft.type == 'NONE' and not draft.active
        before = demo['LIBRARY'].to_document()
        editor.apply_item = True
        assert demo['LIBRARY'].to_document() == before, 'An empty chord must not save a button'
        draft.type, draft.ctrl = 'B', True
        editor.item_name = ''
        editor.apply_item = True
        item = demo['LIBRARY'].menus['main'].groups['RADIAL'][0]
        assert item.action == 'shortcut' and item.label == 'Ctrl+B'
    else:
        assert editor.item_kind == 'shortcut'
        draft = demo['shortcut_draft'](editor)
        assert draft.type == 'B' and draft.ctrl and not draft.active
        item = demo['LIBRARY'].menus['main'].groups['RADIAL'][0]
        assert item.action == 'shortcut' and item.properties['type'] == 'B' and item.properties['ctrl']
    assert demo['LIBRARY'].menus['main'].hotkey is None
    if phase == 'read':
        bpy.ops.screen.screenshot(filepath=str(Path(__file__).resolve().parents[1] /
                                              'design-preview' / 'shortcut-editor.png'))
    event('ESC', 'PRESS')
    event('ESC', 'RELEASE')
    yield 0.5
    assert not demo['OPERATOR_STATES']
    assert not any(keymap.name == 'PieCompose Action Shortcut Draft'
                   for keymap in bpy.context.window_manager.keyconfigs.addon.keymaps)
    # Change the live binding after saving the button. Invocation must use its
    # new properties rather than freezing the old command at editor save time.
    mesh_map = bpy.context.window_manager.keyconfigs.user.keymaps['Mesh']
    with bpy.context.temp_override(area=area, region=region):
        original = demo['shortcut_command'](bpy.context, chord)
    original.active = False
    original_id = original.id
    custom = mesh_map.keymap_items.new('mesh.bevel', 'B', 'PRESS', ctrl=True)
    custom.properties.segments = 4
    custom_id = custom.id
    with bpy.context.temp_override(area=area, region=region):
        assert demo['shortcut_command'](bpy.context, chord) == custom
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
    bevel = next((operator for operator in window.modal_operators if operator.bl_idname == 'MESH_OT_bevel'), None)
    assert bevel is not None, 'Shortcut did not invoke interactive Bevel'
    assert bevel.properties.segments == 4, 'Saved button ignored the changed live keymap parameters'
    event('MOUSEMOVE', 'NOTHING', x + 60, y + 20)
    yield 0.5
    assert len(bmesh.from_edit_mesh(bpy.context.active_object.data).verts) > 8
    event('ESC', 'PRESS')
    event('ESC', 'RELEASE')
    yield 0.5
    assert len(bmesh.from_edit_mesh(bpy.context.active_object.data).verts) == 8
    # Blender rebuilds user keymaps when our menu bindings are synchronized;
    # reacquire RNA items instead of retaining pointers across that rebuild.
    mesh_map = bpy.context.window_manager.keyconfigs.user.keymaps['Mesh']
    mesh_map.keymap_items.remove(mesh_map.keymap_items.from_id(custom_id))
    mesh_map.keymap_items.from_id(original_id).active = True
    with bpy.context.temp_override(area=area, region=region):
        assert demo['shortcut_command'](bpy.context, {'type': 'F24', 'ctrl': True, 'alt': True}) is None
        reports = []
        proxy = type('Reports', (), {'report': lambda self, level, message: reports.append(message)})()
        missing = demo['replace'](item, properties={'type': 'F24', 'ctrl': True, 'alt': True})
        assert not demo['VIEW3D_OT_pie_prototype'].execute_item(proxy, bpy.context, missing)
        assert any('no available command' in message for message in reports)
    assert demo['STORE'].load().to_document() == demo['LIBRARY'].to_document()
    print('SHORTCUT_CHORD_' + phase.upper() + '_LIVE_KEYMAP_MODAL_PASSED', flush=True)


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
bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=25)
