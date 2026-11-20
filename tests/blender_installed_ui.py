"""Native UI smoke test of the installed extension in the lifecycle profile."""
import addon_utils
import bpy
from pathlib import Path

assert addon_utils.check('bl_ext.pie_qa.piecompose')[1]
bpy.context.preferences.view.show_splash = False


def capture():
    output = Path(__file__).resolve().parents[1] / 'design-preview' / 'installed-addon-editor.png'
    bpy.ops.screen.screenshot(filepath=str(output))
    print('INSTALLED_EXTENSION_UI_PASSED', flush=True)
    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1)


def show_editor():
    area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
    region = next(region for region in area.regions if region.type == 'WINDOW')
    with bpy.context.temp_override(area=area, region=region):
        assert bpy.ops.wm.pie_editor('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
    bpy.app.timers.register(capture, first_interval=1)


bpy.app.timers.register(show_editor, first_interval=2)
