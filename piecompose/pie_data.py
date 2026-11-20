"""Menu data and atomic storage, independent of Blender."""

import copy
import json
import math
import os
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from uuid import uuid4


GROUP_SIZES = {'RADIAL': 8, 'TOP': 6, 'BOTTOM': 6}
CATEGORIES = {'auto', 'transform', 'view', 'cursor', 'menu'}
BUILTIN_ACTIONS = {'submenu', 'back', 'origins', 'overlays', 'pivot_median', 'pivot_cursor', 'shortcut'}
DEFAULT_PALETTE = {
    '#69bfaf': 'Mint', '#83a9d5': 'Blue',
    '#d3ae70': 'Sand', '#b49cd4': 'Lavender',
}


def normalize_command_identifier(value):
    """Accept operator IDs or copied bpy.ops names, never execute input code."""
    if not isinstance(value, str):
        raise ValueError('Enter an operator name such as mesh.bevel')
    value = value.strip()
    if value in BUILTIN_ACTIONS:
        return value
    match = re.fullmatch(r'(?:bpy\.ops\.)?([A-Za-z_]\w*\.[A-Za-z_]\w*)\s*(?:\(\s*\))?', value)
    if match is None:
        raise ValueError('Use mesh.bevel or bpy.ops.mesh.bevel; put arguments in Parameters JSON')
    return match.group(1)


HOTKEY_KEYS = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ') | {
    'ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE',
    'SPACE', 'TAB', 'RET', 'HOME', 'END', 'PAGE_UP', 'PAGE_DOWN',
    'LEFT_ARROW', 'RIGHT_ARROW', 'UP_ARROW', 'DOWN_ARROW',
    'INSERT', 'DEL', 'ACCENT_GRAVE', 'MINUS', 'EQUAL', 'LEFT_BRACKET', 'RIGHT_BRACKET',
    'SEMI_COLON', 'QUOTE', 'COMMA', 'PERIOD', 'SLASH', 'BACK_SLASH',
} | {f'F{i}' for i in range(1, 25)} | {f'NUMPAD_{i}' for i in range(10)}


def normalize_hotkey(value):
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get('type'), str) or value['type'] not in HOTKEY_KEYS:
        raise ValueError('Choose a valid keyboard key')
    if set(value) - {'type', 'ctrl', 'shift', 'alt', 'oskey'}:
        raise ValueError('Invalid hotkey settings')
    result = {'type': value['type']}
    for modifier in ('ctrl', 'shift', 'alt', 'oskey'):
        enabled = value.get(modifier, False)
        if type(enabled) is not bool:
            raise ValueError('Invalid hotkey modifier')
        result[modifier] = enabled
    return result


def hotkey_signature(value):
    key = normalize_hotkey(value)
    return tuple(key.values()) if key else None


@dataclass(frozen=True)
class Item:
    label: str
    action: str
    invoke: bool = False
    properties: dict = field(default_factory=dict)
    category: str = 'auto'
    target_menu: str = ''
    marker_color: str = ''


@dataclass
class PieMenu:
    name: str
    groups: dict = field(default_factory=lambda: {
        group: [None] * size for group, size in GROUP_SIZES.items()
    })
    hotkey: dict | None = None


@dataclass
class MenuLibrary:
    menus: dict
    revision: int = 0
    palette: dict = field(default_factory=lambda: dict(DEFAULT_PALETTE))

    @property
    def first_menu(self):
        return next(iter(self.menus))

    def to_document(self):
        return {'schemaVersion': 1, 'revision': self.revision,
                'palette': dict(self.palette),
                'menus': {key: {'name': menu.name, 'hotkey': menu.hotkey, 'groups': {
                    group: [asdict(item) if item else None for item in items]
                    for group, items in menu.groups.items()
                }} for key, menu in self.menus.items()}}


def validate_properties(value):
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, list):
        for child in value:
            validate_properties(child)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for child in value.values():
            validate_properties(child)
        return
    raise ValueError('Command parameters must contain JSON values')


def library_from_document(document):
    if not isinstance(document, dict) or document.get('schemaVersion') != 1:
        raise ValueError('Unsupported menu file format')
    records = document.get('menus')
    legacy_root = document.get('rootMenu')
    revision = document.get('revision', 0)
    if not isinstance(records, dict) or not records:
        raise ValueError('The configuration must contain at least one menu')
    legacy_root = legacy_root if isinstance(legacy_root, str) and legacy_root in records else next(iter(records))
    if type(revision) is not int or revision < 0:
        raise ValueError('Invalid menu file revision')
    palette = document.get('palette', DEFAULT_PALETTE)
    if not isinstance(palette, dict):
        raise ValueError('Invalid label palette')
    names = set()
    normalized_palette = {}
    for color, name in palette.items():
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Invalid palette color')
        if not isinstance(name, str) or not name.strip() or name.strip().casefold() in names:
            raise ValueError('Color names must be nonempty and unique')
        if color.lower() in normalized_palette:
            raise ValueError('Duplicate palette color')
        names.add(name.strip().casefold())
        normalized_palette[color.lower()] = name.strip()
    menus = {}
    shortcuts = set()
    for key, record in records.items():
        if not isinstance(key, str) or not key or not isinstance(record, dict):
            raise ValueError('Invalid menu definition')
        name = record.get('name')
        groups = record.get('groups')
        if not isinstance(name, str) or not name.strip() or not isinstance(groups, dict):
            raise ValueError('Menu name or button list is missing')
        menu = PieMenu(name.strip())
        menu.hotkey = normalize_hotkey(record.get('hotkey', {'type': 'F8'} if key == legacy_root else None))
        signature = hotkey_signature(menu.hotkey)
        if signature is not None:
            if signature in shortcuts:
                raise ValueError('This hotkey is already assigned to another pie menu')
            shortcuts.add(signature)
        for group, size in GROUP_SIZES.items():
            slots = groups.get(group, [None] * size)
            if not isinstance(slots, list) or len(slots) > size:
                raise ValueError(f'Invalid button count in {group}')
            for index, source in enumerate(slots):
                if source is None:
                    continue
                if not isinstance(source, dict):
                    raise ValueError('Invalid button')
                item = Item(**source)
                if not isinstance(item.label, str) or not item.label.strip():
                    raise ValueError('Button name is missing')
                if not isinstance(item.action, str) or not (
                    item.action in BUILTIN_ACTIONS or
                    re.fullmatch(r'[A-Za-z_]\w*\.[A-Za-z_]\w*', item.action)
                ):
                    raise ValueError('Invalid button command')
                if item.category not in CATEGORIES or type(item.invoke) is not bool:
                    raise ValueError('Invalid button settings')
                if not isinstance(item.marker_color, str) or not (
                    item.marker_color in {'', 'none'} or re.fullmatch(r'#[0-9a-fA-F]{6}', item.marker_color)
                ):
                    raise ValueError('Invalid marker color')
                if not isinstance(item.properties, dict):
                    raise ValueError('Invalid command parameters')
                validate_properties(item.properties)
                if item.action == 'shortcut':
                    shortcut = normalize_hotkey(item.properties)
                    if shortcut is None:
                        raise ValueError('Choose a keyboard shortcut')
                    item = replace(item, properties=shortcut)
                if item.action == 'submenu' and item.target_menu not in records:
                    raise ValueError('Button links to a missing menu')
                menu.groups[group][index] = item
        menus[key] = menu
    return MenuLibrary(menus, revision, normalized_palette)


def assign_hotkey(library, menu_id, value):
    key = normalize_hotkey(value)
    signature = hotkey_signature(key)
    menu = library.menus[menu_id]
    displaced = []
    if signature is not None:
        for other_id, other in library.menus.items():
            if other_id != menu_id and hotkey_signature(other.hotkey) == signature:
                other.hotkey = None
                displaced.append(other_id)
    menu.hotkey = key
    return displaced


def add_palette_color(library, name, color):
    if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('Invalid color')
    color = color.lower()
    if color in library.palette:
        return color
    if not isinstance(name, str) or not name.strip():
        raise ValueError('Enter a name for the new color')
    if name.strip().casefold() in {value.casefold() for value in library.palette.values()}:
        raise ValueError('A color with this name already exists')
    library.palette[color] = name.strip()
    return color


def palette_usage(library, color):
    return sum(item is not None and item.marker_color == color
               for menu in library.menus.values() for slots in menu.groups.values() for item in slots)


def delete_palette_color(library, color):
    if color not in library.palette:
        raise ValueError('Choose a saved label')
    for menu in library.menus.values():
        for slots in menu.groups.values():
            for index, item in enumerate(slots):
                if item is not None and item.marker_color == color:
                    slots[index] = replace(item, marker_color='none')
    del library.palette[color]


def update_palette_color(library, previous, name, color):
    if previous not in library.palette:
        raise ValueError('Choose a saved label')
    if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('Invalid color')
    color = color.lower()
    if not isinstance(name, str) or not name.strip():
        raise ValueError('Enter a label name')
    name = name.strip()
    if color != previous and color in library.palette:
        raise ValueError('Another label already uses this color')
    if name.casefold() in {value.casefold() for key, value in library.palette.items() if key != previous}:
        raise ValueError('A label with this name already exists')
    library.palette = {color if key == previous else key: name if key == previous else value
                       for key, value in library.palette.items()}
    for menu in library.menus.values():
        for slots in menu.groups.values():
            for index, item in enumerate(slots):
                if item is not None and item.marker_color == previous:
                    slots[index] = replace(item, marker_color=color)
    return color


@contextmanager
def atomic_output(path, **options):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name,
                                         suffix='.tmp', delete=False, **options) as handle:
            temporary = Path(handle.name)
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

def write_json_atomic(path, document):
    with atomic_output(path, mode='w', encoding='utf-8') as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


class StorageConflict(RuntimeError):
    pass


@contextmanager
def exclusive_file_lock(path):
    """OS locks are released even if Blender exits unexpectedly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'\0')
            handle.flush()
        deadline = time.monotonic() + 3
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise StorageConflict('The menu file is in use by another Blender instance')
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)


class MenuStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        return library_from_document(json.loads(self.path.read_text(encoding='utf-8-sig')))

    def save(self, library):
        candidate = library_from_document(library.to_document())
        with exclusive_file_lock(self.path.with_suffix('.lock')):
            revision = self.load().revision if self.path.exists() else 0
            if revision != candidate.revision:
                raise StorageConflict('Menus changed in another window. Reopen the editor.')
            candidate.revision += 1
            write_json_atomic(self.path, candidate.to_document())
        library.revision = candidate.revision


def create_menu(library, name='New menu'):
    key = uuid4().hex
    library.menus[key] = PieMenu(name)
    return key


def delete_menu(library, key):
    if len(library.menus) == 1:
        raise ValueError('Keep at least one menu in the library')
    del library.menus[key]
    for menu in library.menus.values():
        for slots in menu.groups.values():
            for index, item in enumerate(slots):
                if item and item.action == 'submenu' and item.target_menu == key:
                    slots[index] = None


def move_item(library, menu_id, source, destination):
    """Swap occupied positions so a move never discards another command."""
    source_group, source_index = source.rsplit('_', 1)
    target_group, target_index = destination.rsplit('_', 1)
    groups = library.menus[menu_id].groups
    left, right = int(source_index), int(target_index)
    groups[source_group][left], groups[target_group][right] = (
        groups[target_group][right], groups[source_group][left]
    )


def clone_library(library):
    return copy.deepcopy(library)
