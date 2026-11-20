"""Native editor/capture reopen checks; start with --enable-event-simulate."""
import os
from pathlib import Path
import runpy
import tempfile
import traceback
import bpy

root = Path(__file__).resolve().parents[1]
os.environ['PIE_MENU_DATA_PATH'] = str(Path(tempfile.mkdtemp(prefix='pie-menu-memory-')) / 'menus.json')
bpy.context.preferences.view.show_splash = False
demo = runpy.run_path(str(root / 'pie_prototype.py'))
runpy.run_path(str(Path(__file__).with_name('demo_library.py')))['install'](demo)
instances = {}


def observe(cls, name):
    original = cls.invoke

    def invoke(self, context, event):
        instances[name] = self
        return original(self, context, event)

    cls.invoke = invoke


observe(demo['WM_OT_pie_editor'], 'editor')
observe(demo['WM_OT_pie_capture'], 'capture')
demo['register']()
area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
region = next(region for region in area.regions if region.type == 'WINDOW')
window = bpy.context.window


def open_editor():
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.wm.pie_editor('INVOKE_DEFAULT') == {'RUNNING_MODAL'}


def open_capture(**kwargs):
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.wm.pie_capture('INVOKE_DEFAULT', command='object.shade_smooth',
                                      caption='Smooth', **kwargs) == {'RUNNING_MODAL'}


def close():
    instances.clear()
    window.event_simulate(type='ESC', value='PRESS')
    window.event_simulate(type='ESC', value='RELEASE')


def scenarios():
    original = demo['STORE'].path.read_bytes()
    open_editor()
    yield 0.5
    instances['editor'].menu_choice = 'modeling'
    close()
    yield 0.5
    open_capture()
    yield 0.5
    assert instances['capture'].destination_menu == 'modeling', 'Capture did not remember the last edited menu'
    # Selection/cancellation are UI state and must not save configuration.
    instances['capture'].destination_menu = 'main'
    close()
    yield 0.5
    assert demo['STORE'].path.read_bytes() == original
    open_capture()
    yield 0.5
    assert instances['capture'].destination_menu == 'main'
    instances['capture'].destination_menu = 'modeling'
    close()
    yield 0.5
    open_editor()
    yield 0.5
    assert instances['editor'].menu_choice == 'modeling'
    instances['editor'].menu_name = 'Renamed destination'
    instances['editor'].rename_menu = True
    close()
    yield 0.5
    before = demo['clone_library'](demo['LIBRARY'])
    # An explicit API destination must win over remembered Modeling.
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.wm.pie_capture(command='object.shade_smooth', caption='Explicit save',
                                      destination_menu='main', slot='TOP_0') == {'FINISHED'}
    assert demo['LIBRARY'].menus['modeling'] == before.menus['modeling']
    open_capture(destination_menu='modeling')
    yield 0.5
    assert instances['capture'].destination_menu == 'modeling'
    close()
    yield 0.5
    # Saving without a destination uses the remembered menu, including API calls.
    before = demo['clone_library'](demo['LIBRARY'])
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.wm.pie_capture(command='object.shade_smooth', caption='Implicit save',
                                      slot='TOP_1') == {'FINISHED'}
    assert demo['LIBRARY'].menus['main'] == before.menus['main']
    assert demo['LIBRARY'].menus['modeling'].groups['TOP'][1].label == 'Implicit save'
    open_capture()
    yield 0.5
    assert instances['capture'].destination_menu == 'modeling'
    close()
    yield 0.5
    open_editor()
    yield 0.5
    assert instances['editor'].menu_choice == 'modeling'
    instances['editor'].remove_menu = True
    assert instances['editor'].menu_choice == 'main'
    close()
    yield 0.5
    open_capture()
    yield 0.5
    assert instances['capture'].destination_menu == 'main'
    close()
    yield 0.5
    # Replacing/importing a library may invalidate a remembered ID.
    candidate = demo['clone_library'](demo['LIBRARY'])
    new = demo['create_menu'](candidate, 'Temporary destination')
    demo['save_library'](candidate)
    open_editor()
    yield 0.5
    instances['editor'].menu_choice = new
    close()
    yield 0.5
    candidate = demo['clone_library'](demo['LIBRARY'])
    demo['delete_menu'](candidate, new)
    demo['save_library'](candidate)
    open_capture()
    yield 0.5
    assert instances['capture'].destination_menu == 'main'
    close()
    yield 0.5
    assert not demo['OPERATOR_STATES'], 'Cancelled dialogs leaked editor state'
    assert demo['STORE'].load().to_document() == demo['LIBRARY'].to_document()


scenario = scenarios()


def step():
    try:
        return next(scenario)
    except StopIteration:
        print('LAST_EDITED_MENU_CAPTURE_REOPEN_PASSED', flush=True)
    except Exception:
        traceback.print_exc()
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=0.5)
    return None


bpy.app.timers.register(step, first_interval=2)
bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=30)
