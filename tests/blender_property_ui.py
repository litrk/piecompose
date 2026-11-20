"""Native capture dialog preview for a context-bound checkbox."""
import os
from pathlib import Path
import runpy
import tempfile
import bpy

root = Path(__file__).resolve().parents[1]
os.environ['PIE_MENU_DATA_PATH'] = str(Path(tempfile.mkdtemp(prefix='pie-property-ui-')) / 'menus.json')
bpy.context.preferences.view.show_splash = False
demo = runpy.run_path(str(root / 'pie_prototype.py'))
demo['register']()


def capture():
    bpy.ops.screen.screenshot(filepath=str(root / 'design-preview/generic-property-capture.png'))
    print('GENERIC_PROPERTY_CAPTURE_UI_PASSED', flush=True)
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1)


def show():
    area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
    region = next(region for region in area.regions if region.type == 'WINDOW')
    obj = bpy.context.active_object
    with bpy.context.temp_override(area=area, region=region, button_operator=None,
                                  button_pointer=obj, button_prop=obj.bl_rna.properties['show_in_front']):
        command, caption, parameters = demo['capture_button'](bpy.context)
        assert bpy.ops.wm.pie_capture('INVOKE_DEFAULT', command=command, caption=caption,
                                      parameters=parameters) == {'RUNNING_MODAL'}
    bpy.app.timers.register(capture, first_interval=1)


bpy.app.timers.register(show, first_interval=2)
