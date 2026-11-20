"""Build and validate the distributable without bundling personal settings."""
import argparse
from pathlib import Path
import subprocess
import sys
import tomllib
import zipfile
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from piecompose.pie_data import library_from_document, write_json_atomic
import json

parser = argparse.ArgumentParser()
parser.add_argument('--blender', default='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')
parser.add_argument('--backup-config', type=Path)
args = parser.parse_args()
package = ROOT / 'piecompose'
manifest = tomllib.loads((package / 'blender_manifest.toml').read_text(encoding='utf-8'))
output = ROOT / 'dist'
output.mkdir(exist_ok=True)
archive = output / f"{manifest['id']}-{manifest['version']}.zip"
with tempfile.TemporaryDirectory(prefix='piecompose-build-') as profile:
    env = dict(os.environ)
    for key, folder in (('BLENDER_USER_CONFIG', 'config'), ('BLENDER_USER_SCRIPTS', 'scripts'),
                        ('BLENDER_USER_EXTENSIONS', 'extensions')):
        path = Path(profile) / folder
        path.mkdir()
        env[key] = str(path)
    # Build tools must not load the user's installed add-on or configuration.
    subprocess.run([args.blender, '--command', 'extension', 'validate', str(package)], check=True, env=env)
    subprocess.run([args.blender, '--command', 'extension', 'build', '--source-dir', str(package),
                    '--output-filepath', str(archive)], check=True, env=env)
    subprocess.run([args.blender, '--command', 'extension', 'validate', str(archive)], check=True, env=env)
with zipfile.ZipFile(archive) as bundle:
    expected = {'__init__.py', 'runtime.py', 'pie_data.py', 'property_bindings.py', 'shortcuts.py',
                'blender_manifest.toml', 'LICENSE.txt', 'README.md'}
    assert set(bundle.namelist()) == expected, bundle.namelist()
if args.backup_config:
    library = library_from_document(json.loads(args.backup_config.read_text(encoding='utf-8-sig')))
    backup = output / 'pie-configuration-backup.json'
    write_json_atomic(backup, library.to_document())
    print(f'Configuration backup (not in ZIP): {backup}')
print(f'Extension ready: {archive}')
