"""Development launcher; the installed add-on lives in piecompose."""
import os
import sys
from pathlib import Path

_project_path = Path(__file__).resolve().parent
if str(_project_path) not in sys.path:
    sys.path.insert(0, str(_project_path))
from piecompose import runtime as _runtime

# Keep development data in the project; installed extensions use Blender's
# user configuration directory. Tests can override this with an isolated path.
if not os.environ.get('PIE_MENU_DATA_PATH'):
    _runtime.STORE.path = _project_path / 'pie-menus.json'
_runtime.STYLE_PATH = _project_path / 'pie-style.json'
globals().update({key: value for key, value in vars(_runtime).items() if not key.startswith('__')})

if __name__ == '__main__':
    _runtime.register()
