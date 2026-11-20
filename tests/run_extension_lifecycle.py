"""Install the built ZIP in a temporary Blender profile and test restarts."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import tomllib
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from piecompose.pie_data import Item, MenuLibrary, PieMenu, write_json_atomic

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--blender', default='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')
parser.add_argument('--previous-archive', type=Path,
                    help='Install this ZIP first, then update in the same running Blender process')
args = parser.parse_args()
manifest = tomllib.loads((root / 'piecompose/blender_manifest.toml').read_text(encoding='utf-8'))
target_id = manifest['id']
archive = root / 'dist' / f"{target_id}-{manifest['version']}.zip"
source_archive = (args.previous_archive or archive).resolve()
with zipfile.ZipFile(source_archive) as source_zip:
    source_id = tomllib.loads(source_zip.read('blender_manifest.toml').decode('utf-8'))['id']
if source_id != target_id:
    parser.error('The previous archive must have the same extension ID')
qa_root = Path(tempfile.mkdtemp(prefix='pie-extension-'))
env = dict(os.environ)
env.pop('PIE_MENU_DATA_PATH', None)
for key, folder in (('BLENDER_USER_CONFIG', 'config'), ('BLENDER_USER_SCRIPTS', 'scripts'),
                    ('BLENDER_USER_EXTENSIONS', 'extensions')):
    path = qa_root / folder
    path.mkdir()
    env[key] = str(path)
env['PIE_EXTENSION_QA_ROOT'] = str(qa_root)
env['PIE_EXTENSION_QA_ARCHIVE'] = str(archive)
env['PIE_EXTENSION_QA_VERSION'] = manifest['version']
env['PIE_EXTENSION_QA_TARGET_ID'] = target_id

# Seed an unrelated extension folder to verify fresh-install isolation.
fixture = MenuLibrary({'legacy': PieMenu('Preserved menu', hotkey={'type': 'F8'}),
                      'child': PieMenu('Preserved child')},
                     palette={'#83a9d5': 'Preserved label'})
fixture.menus['legacy'].groups['RADIAL'][0] = Item(
    'Preserved command', 'view3d.view_axis', True, {'type': 'TOP'}, marker_color='#83a9d5')
fixture.menus['legacy'].groups['TOP'][0] = Item('Preserved link', 'submenu', True, target_menu='child', marker_color='none')
other_path = qa_root / 'config' / 'other_extension' / 'pie-menus.json'
other_path.parent.mkdir(parents=True)
write_json_atomic(other_path, fixture.to_document())
(qa_root / 'configuration-fixture.json').write_bytes(other_path.read_bytes())


def run(*arguments, expected=None):
    if '--python' in arguments:
        arguments = (*arguments[:1], '--python-exit-code', '1', *arguments[1:])
    result = subprocess.run([args.blender, *arguments], env=env, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=90)
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='')
    if result.returncode or (expected and expected not in result.stdout):
        raise RuntimeError(f'Blender check failed: {arguments}')


run('--background', '--factory-startup', '--python-expr',
    "import bpy,os; from pathlib import Path; p=Path(bpy.utils.user_resource('CONFIG')); "
    "assert p.resolve().is_relative_to(Path(os.environ['PIE_EXTENSION_QA_ROOT']).resolve()); print('ISOLATED_PROFILE_OK')",
    expected='ISOLATED_PROFILE_OK')
run('--command', 'extension', 'repo-add', '--directory', str(qa_root / 'repository'), '--clear-all', 'pie_qa')
run('--command', 'extension', 'install-file', '--repo', 'pie_qa', '--enable', str(archive))
script = root / 'tests' / 'blender_extension_lifecycle.py'
run('--background', '--python', str(script), '--', 'fresh', expected='EMPTY_FIRST_INSTALL_PASSED')
current_path = qa_root / 'config' / target_id / 'pie-menus.json'
if source_archive != archive:
    run('--command', 'extension', 'install-file', '--repo', 'pie_qa', '--enable', str(source_archive))
current_path.write_bytes((qa_root / 'configuration-fixture.json').read_bytes())
run('--background', '--python', str(script), '--', 'write', expected='EXTENSION_ENABLE_DISABLE_PASSED')
run('--background', '--python', str(script), '--', 'upgrade', expected='LIVE_INSTALL_FROM_DISK_PRESERVED_CONFIGURATION')
run('--background', '--python', str(script), '--', 'read', expected='EXTENSION_RESTART_AND_UPDATE_PASSED')
# A broken file must fail visibly, not show an apparently empty configuration.
current_path.write_text('{broken configuration', encoding='utf-8')
run('--background', '--python', str(root / 'tests/blender_config_failure.py'),
    expected='CONFIGURATION_ERROR_NO_RESET_PASSED')
current_path.write_bytes((qa_root / 'upgrade-expected.json').read_bytes())
# Reinstall the archive as an update, then start a new process once more.
run('--command', 'extension', 'install-file', '--repo', 'pie_qa', '--enable', str(archive))
run('--background', '--python', str(script), '--', 'read', expected='EXTENSION_RESTART_AND_UPDATE_PASSED')
print(f'EXTENSION_LIFECYCLE_PASSED: {qa_root}')
