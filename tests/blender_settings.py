"""Round-trip the actual import/export operators using isolated settings files."""
import json
import os
from pathlib import Path
import runpy
import tempfile
import bpy

directory = Path(tempfile.mkdtemp(prefix='pie-settings-'))
os.environ['PIE_MENU_DATA_PATH'] = str(directory / 'active-menus.json')
demo = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'pie_prototype.py'))
demo['register']()
library = demo['LIBRARY']
candidate = demo['clone_library'](library)
candidate.menus[candidate.first_menu].groups['RADIAL'][0] = demo['Item'](
    'Bevel shortcut', 'shortcut', properties={'type': 'B', 'ctrl': True}, marker_color='none')
demo['save_library'](candidate)

menus_file = directory / 'menus-export.json'
assert bpy.ops.wm.pie_export_configuration(filepath=str(menus_file)) == {'FINISHED'}
exported = json.loads(menus_file.read_text(encoding='utf-8'))
assert exported == library.to_document()

changed = demo['clone_library'](library)
changed.menus[changed.first_menu].name = 'Changed after export'
demo['save_library'](changed)
before_import = library.to_document()
assert bpy.ops.wm.pie_import_configuration(filepath=str(menus_file)) == {'FINISHED'}
restored = library.to_document()
restored['revision'] = exported['revision']
assert restored == exported
backups = list(directory.glob('active-menus.before-import-*.json'))
assert len(backups) == 1
assert json.loads(backups[0].read_text(encoding='utf-8')) == before_import

invalid = directory / 'invalid.json'
invalid.write_text('{"schemaVersion":1,"menus":{}}', encoding='utf-8')
before = library.to_document()
try:
    result = bpy.ops.wm.pie_import_configuration(filepath=str(invalid))
    assert result == {'CANCELLED'}
except RuntimeError:
    pass  # Blender raises for an ERROR report from a cancelled operator.
assert library.to_document() == before
assert len(list(directory.glob('active-menus.before-import-*.json'))) == 1
demo['unregister']()
print('SETTINGS_IMPORT_EXPORT_PASSED', flush=True)
