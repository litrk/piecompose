"""An unreadable configuration must not silently activate an empty editor."""
import addon_utils
import bpy
import os
from pathlib import Path

path = Path(os.environ['PIE_EXTENSION_QA_ROOT']) / 'config/piecompose/pie-menus.json'
assert path.read_text(encoding='utf-8') == '{broken configuration'
assert not addon_utils.check('bl_ext.pie_qa.piecompose')[1]
assert not hasattr(bpy.types, 'WM_OT_pie_editor')
assert not any(item.idname == 'view3d.pie_prototype'
               for keymap in bpy.context.window_manager.keyconfigs.addon.keymaps
               for item in keymap.keymap_items)
assert path.read_text(encoding='utf-8') == '{broken configuration'
print('CONFIGURATION_ERROR_NO_RESET_PASSED', flush=True)
