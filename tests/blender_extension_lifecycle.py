"""Run inside the isolated installed-extension profile, never factory startup."""
import addon_utils
import bpy
import importlib
import os
from pathlib import Path
import sys
import json
import tomllib

phase = sys.argv[sys.argv.index('--') + 1]
qa_root = Path(os.environ['PIE_EXTENSION_QA_ROOT']).resolve()
target_id = os.environ['PIE_EXTENSION_QA_TARGET_ID']
module_name = 'bl_ext.pie_qa.' + target_id
assert addon_utils.check(module_name)[1], 'Installed extension did not load automatically'
module = importlib.import_module(module_name)
runtime = importlib.import_module(module_name + '.runtime')
data = importlib.import_module(module_name + '.pie_data')
assert runtime.STORE.path.resolve().is_relative_to(qa_root)
assert not runtime.STORE.path.resolve().is_relative_to(Path(module.__file__).parent.resolve())
storage_path = qa_root / 'config' / module_name.rsplit('.', 1)[1] / 'pie-menus.json'
assert runtime.STORE.path.resolve() == storage_path.resolve()
old_path = qa_root / 'config' / 'other_extension' / 'pie-menus.json'
assert old_path.read_bytes() == (qa_root / 'configuration-fixture.json').read_bytes()
assert runtime.VIEW3D_OT_pie_prototype.marker_shape == 'bar'


def assert_bindings():
    assigned = [menu for menu in runtime.LIBRARY.menus.values() if menu.hotkey]
    assert len(runtime.KEYMAPS) == len(assigned)
    actual = [item for keymap in bpy.context.window_manager.keyconfigs.addon.keymaps
              for item in keymap.keymap_items if item.idname == 'view3d.pie_prototype']
    assert len(actual) == len(assigned), 'Duplicate or leaked keymap items'
    assert len({data.hotkey_signature(menu.hotkey) for menu in assigned}) == len(assigned)


if phase == 'fresh':
    assert len(runtime.LIBRARY.menus) == 1
    menu = runtime.LIBRARY.menus[runtime.LIBRARY.first_menu]
    assert menu.name == 'New menu' and menu.hotkey is None
    assert not any(item for slots in menu.groups.values() for item in slots)
    assert not runtime.LIBRARY.palette
    assert not runtime.KEYMAPS
    assert runtime.STORE.load().to_document() == runtime.LIBRARY.to_document()
    print('EMPTY_FIRST_INSTALL_PASSED', flush=True)
elif phase == 'write':
    current_path = storage_path
    assert current_path.read_bytes() == (qa_root / 'configuration-fixture.json').read_bytes()
    expected = data.library_from_document(json.loads(current_path.read_text(encoding='utf-8')))
    assert runtime.LIBRARY.to_document() == expected.to_document()
    assert runtime.WM_OT_pie_editor.bl_label == 'PieCompose: Menu Editor'
    assert runtime.VIEW3D_PT_pie_menus.bl_category == 'PieCompose'
    print('SOURCE_CONFIGURATION_RELOAD_PASSED', flush=True)
    configuration = qa_root / 'configuration-fixture.json'
    runtime.prepare_palette(expected)
    assert bpy.ops.wm.pie_import_configuration(filepath=str(configuration)) == {'FINISHED'}
    actual = runtime.LIBRARY.to_document()
    actual['revision'] = expected.revision
    assert actual == expected.to_document()
    print('CONFIGURATION_IMPORT_PASSED', flush=True)
    candidate = data.clone_library(runtime.LIBRARY)
    candidate.menus[candidate.first_menu].name = 'Restart check'
    child = data.create_menu(candidate, 'Installed tools')
    data.assign_hotkey(candidate, child, {'type': 'F9', 'ctrl': True})
    # When the source archive supports shortcut actions, preserve one through
    # the live update/restart alongside operator buttons, links and labels.
    if 'shortcut' in data.BUILTIN_ACTIONS:
        candidate.menus[child].groups['BOTTOM'][5] = data.Item(
            'Bevel shortcut', 'shortcut', True, {'type': 'B', 'ctrl': True}, marker_color='none')
    runtime.save_library(candidate)
    saved = runtime.STORE.path.read_bytes()
    (qa_root / 'upgrade-expected.json').write_bytes(saved)
    for _ in range(3):
        assert_bindings()
        addon_utils.disable(module_name, default_set=False)
        assert not addon_utils.check(module_name)[1]
        assert not runtime.KEYMAPS
        assert not hasattr(bpy.types, 'WM_OT_pie_editor')
        addon_utils.enable(module_name, default_set=False)
        assert addon_utils.check(module_name)[1]
        assert runtime.STORE.path.read_bytes() == saved
    bpy.ops.wm.save_userpref()
    print('EXTENSION_ENABLE_DISABLE_PASSED', flush=True)
elif phase in {'read', 'upgrade'}:
    expected_bytes = (qa_root / 'upgrade-expected.json').read_bytes()
    if phase == 'upgrade':
        result = bpy.ops.extensions.package_install_files(
            'EXEC_DEFAULT', repo='pie_qa', filepath=os.environ['PIE_EXTENSION_QA_ARCHIVE'],
            enable_on_install=True)
        assert result == {'FINISHED'}, result
        assert addon_utils.check(module_name)[1], 'Updated extension did not enable'
        module = importlib.import_module(module_name)
        runtime = importlib.import_module(module_name + '.runtime')
        assert runtime.CONFIG_DIRECTORY == target_id, 'Old runtime remained loaded after updating'
        assert runtime.STORE.path == qa_root / 'config' / target_id / 'pie-menus.json'
        installed_manifest = tomllib.loads(Path(module.__file__).with_name('blender_manifest.toml').read_text(encoding='utf-8'))
        assert installed_manifest['version'] == os.environ['PIE_EXTENSION_QA_VERSION']
        bpy.ops.wm.save_userpref()
    assert runtime.STORE.path.read_bytes() == expected_bytes, 'Update changed the saved configuration'
    assert runtime.LIBRARY.to_document() == json.loads(expected_bytes), 'Update lost configuration in memory'
    assert runtime.LIBRARY.menus[runtime.LIBRARY.first_menu].name == 'Restart check'
    child = next(menu for menu in runtime.LIBRARY.menus.values() if menu.name == 'Installed tools')
    assert child.hotkey['type'] == 'F9' and child.hotkey['ctrl']
    assert_bindings()
    if phase == 'upgrade':
        print('LIVE_INSTALL_FROM_DISK_PRESERVED_CONFIGURATION', flush=True)
    print('EXTENSION_RESTART_AND_UPDATE_PASSED', flush=True)
else:
    raise ValueError(phase)
