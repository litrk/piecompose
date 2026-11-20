"""PieCompose runtime. SPDX-License-Identifier: GPL-3.0-or-later"""

import math
import json
import os
from pathlib import Path
from dataclasses import dataclass, replace
from time import monotonic

from .pie_data import (
    GROUP_SIZES, Item, MenuLibrary, MenuStore, PieMenu, StorageConflict,
    clone_library, create_menu, delete_menu, move_item, add_palette_color,
    HOTKEY_KEYS, normalize_hotkey, hotkey_signature, assign_hotkey,
    palette_usage, delete_palette_color, update_palette_color, write_json_atomic, library_from_document,
    normalize_command_identifier,
)
from uuid import uuid4

import blf
import bpy
import bpy.utils.previews
from bpy_extras.io_utils import ExportHelper
from .property_bindings import binding_description, capture_boolean_path, resolve_boolean
from .shortcuts import resolve_shortcut
import gpu
from gpu_extras.batch import batch_for_shader


FONT_ID = 0
EXTRA_GESTURE_DELAY = 0.5
STYLE_PATH = Path(__file__).resolve().with_name('legacy-layout.json')
DEFAULT_STYLE = {
    'radialColor': '#141414', 'extraColor': '#1c1c1c', 'hoverColor': '#185b56',
    'hoverTextColor': '#dedede', 'textColor': '#ababab', 'mutedColor': '#929292',
    'borderColor': '#515151', 'backgroundColor': '#3b3b3b',
    'transformColor': '#69bfaf', 'viewColor': '#83a9d5',
    'cursorColor': '#d3ae70', 'menuColor': '#b49cd4',
    'radius': 15, 'fontSize': 14, 'padding': 9, 'radialWidth': 186,
    'radialHeight': 35, 'extraWidth': 186, 'extraHeight': 35,
    'rowGap': 8, 'columnGap': 8, 'horizontalDistance': 200,
    'verticalDistance': 138, 'diagonalX': 140, 'diagonalY': 85,
    'blockDistance': 260, 'markerMode': 'category', 'markerSize': 5,
    'buttonColors': {},
}
STYLE_RANGES = {
    'radius': (0, 18), 'fontSize': (10, 18), 'padding': (5, 22),
    'radialWidth': (110, 220), 'radialHeight': (26, 48),
    'extraWidth': (110, 240), 'extraHeight': (22, 48),
    'rowGap': (2, 16), 'columnGap': (2, 20), 'horizontalDistance': (175, 280),
    'verticalDistance': (115, 180), 'diagonalX': (115, 190),
    'diagonalY': (65, 115), 'blockDistance': (200, 310), 'markerSize': (3, 9),
}


def rgba(color):
    if not isinstance(color, str) or len(color) != 7 or not color.startswith('#'):
        raise ValueError(f'Invalid color {color!r}')
    return tuple(int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)) + (1.0,)


def theme_rgba(color):
    return tuple(color) if len(color) == 4 else tuple(color) + (1.0,)


def validate_style(document):
    if not isinstance(document, dict):
        raise ValueError('Expected a style settings object')
    if document.get('schemaVersion', 1) != 1:
        raise ValueError('Unsupported style version')
    source = document.get('settings', document)
    if not isinstance(source, dict):
        raise ValueError('Invalid style settings')
    result = {**DEFAULT_STYLE, **{key: value for key, value in source.items() if key in DEFAULT_STYLE}}
    for key, value in result.items():
        if key.endswith('Color'):
            rgba(value)
    for key, (minimum, maximum) in STYLE_RANGES.items():
        value = result[key]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f'Invalid size for {key}')
    if result['markerMode'] not in {'none', 'category', 'custom'}:
        raise ValueError('Unknown marker mode')
    if not isinstance(result['buttonColors'], dict):
        raise ValueError('Invalid button colors')
    for color in result['buttonColors'].values():
        rgba(color)
    # Keep older exports readable; all working-menu buttons now share one size.
    result['extraWidth'] = result['radialWidth']
    result['extraHeight'] = result['radialHeight']
    return result


STYLE = validate_style({})


def load_style(path=None):
    path = path or STYLE_PATH
    candidate = validate_style(json.loads(Path(path).read_text(encoding='utf-8-sig')))
    STYLE.clear()
    STYLE.update(candidate)

LIBRARY = MenuLibrary({'main': PieMenu('New menu')}, palette={})
LAST_EDITED_MENU = None


def preferred_menu(library):
    return LAST_EDITED_MENU if LAST_EDITED_MENU in library.menus else library.first_menu


def remember_menu(menu_id, library):
    global LAST_EDITED_MENU
    if menu_id in library.menus:
        LAST_EDITED_MENU = menu_id

# Persistent storage identity. Keep this independent of release versions,
# package display names, installation repositories and ZIP locations.
CONFIG_DIRECTORY = 'piecompose'

def configuration_path():
    override = os.environ.get('PIE_MENU_DATA_PATH')
    if override:
        return Path(override)
    config_root = bpy.utils.user_resource('CONFIG')
    if not config_root:
        config_root = str(Path(bpy.utils.resource_path('USER')) / 'config')
    return Path(config_root) / CONFIG_DIRECTORY / 'pie-menus.json'


STORE = MenuStore(configuration_path())


def publish_library(candidate):
    prepare_palette(candidate)
    LIBRARY.menus = candidate.menus
    LIBRARY.revision = candidate.revision
    LIBRARY.palette = candidate.palette
    if KEYMAPS_READY:
        sync_keymaps()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def refresh_library():
    if STORE.path.exists():
        publish_library(STORE.load())


def save_library(candidate):
    prepare_palette(candidate)
    supported = {item[0] for item in HOTKEY_ITEMS}
    for menu in candidate.menus.values():
        if menu.hotkey and menu.hotkey['type'] not in supported:
            raise ValueError('This key is not supported by this Blender version')
    STORE.save(candidate)
    publish_library(candidate)


@dataclass(frozen=True)
class Button:
    item: Item
    rect: tuple
    suffix: str = ''
    slot: str = ''

    def contains(self, point):
        left, bottom, right, top = self.rect
        x, y = point
        return left <= x <= right and bottom <= y <= top


def rectangle(x, y, width, height):
    return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)


def fill(shader, rect, color, radius=4):
    left, bottom, right, top = rect
    radius = min(radius, (right - left) / 2, (top - bottom) / 2)
    vertices = [((left + right) / 2, (bottom + top) / 2)]
    for cx, cy, angle in ((right - radius, top - radius, 0),
                          (left + radius, top - radius, 90),
                          (left + radius, bottom + radius, 180),
                          (right - radius, bottom + radius, 270)):
        for step in range(7):
            radians = math.radians(angle + step * 15)
            vertices.append((cx + math.cos(radians) * radius,
                             cy + math.sin(radians) * radius))
    vertices.append(vertices[1])
    indices = [(0, index, index + 1) for index in range(1, len(vertices) - 1)]
    shader.bind()
    shader.uniform_float('color', color)
    batch_for_shader(shader, 'TRIS', {'pos': vertices}, indices=indices).draw(shader)


def label(text, x, y, size, color, align='left'):
    blf.size(FONT_ID, size)
    width, _ = blf.dimensions(FONT_ID, text)
    if align == 'center':
        x -= width / 2
    elif align == 'right':
        x -= width
    blf.color(FONT_ID, *color)
    blf.position(FONT_ID, x, y, 0)
    blf.draw(FONT_ID, text)


def item_category(item):
    if item.category != 'auto':
        return item.category
    if item.action in {'submenu', 'back'} or item.action.startswith(('mesh.', 'object.')):
        return 'menu'
    if item.action.startswith('pivot_') or 'cursor' in item.action:
        return 'cursor'
    if item.action.startswith('transform.') or item.action == 'origins':
        return 'transform'
    return 'view'


def prepare_palette(library):
    """Freeze legacy automatic marks once; new assignments are always explicit."""
    for menu in library.menus.values():
        for group, slots in menu.groups.items():
            for index, item in enumerate(slots):
                if item is None:
                    continue
                color = item.marker_color
                if not color:
                    color = 'none' if STYLE['markerMode'] == 'none' else STYLE[item_category(item) + 'Color']
                    if STYLE['markerMode'] == 'custom':
                        slot = f'radial-{index}' if group == 'RADIAL' else f'{group.lower()}-block-{index}'
                        color = STYLE['buttonColors'].get(slot, color)
                color = color.lower()
                # Legacy execution flags are no longer a user setting.
                # Commands launch as they do from Blender's own UI.
                slots[index] = replace(item, marker_color=color, invoke=True)
                if color != 'none' and color not in library.palette:
                    name = f'Color {color}'
                    while name.casefold() in {value.casefold() for value in library.palette.values()}:
                        name += ' ·'
                    library.palette[color] = name


class PieLayout:
    def __init__(self, width, height, origin, ui_scale, child=False, menu=None):
        menu = menu or LIBRARY.menus[LIBRARY.first_menu]
        extra_groups = (menu.groups['TOP'], menu.groups['BOTTOM'])
        # Leave room for the viewport's overlapping header at either edge.
        radial_half_width = STYLE['radialWidth'] / 2
        half_width = max(STYLE['horizontalDistance'] + radial_half_width,
                         STYLE['diagonalX'] + radial_half_width,
                         (3 * STYLE['extraWidth'] + 2 * STYLE['columnGap']) / 2) + 52
        rows = max(math.ceil(len(items) / 3) for items in extra_groups)
        block_height = rows * STYLE['extraHeight'] + (rows - 1) * STYLE['rowGap']
        radial_top = max(STYLE['verticalDistance'], STYLE['diagonalY']) + STYLE['radialHeight'] / 2
        # Preserve a clear gap even when importing an older, tighter layout.
        block_distance = max(STYLE['blockDistance'], radial_top + block_height / 2 + 40)
        half_height = max(radial_top, block_distance + block_height / 2) + 45
        self.scale = scale = min(ui_scale, width / (2 * half_width), height / (2 * half_height))
        self.center = (
            min(max(origin[0], half_width * scale), width - half_width * scale),
            min(max(origin[1], half_height * scale), height - half_height * scale),
        )
        positions = (
            (STYLE['horizontalDistance'], 0), (STYLE['diagonalX'], STYLE['diagonalY']),
            (0, STYLE['verticalDistance']), (-STYLE['diagonalX'], STYLE['diagonalY']),
            (-STYLE['horizontalDistance'], 0), (-STYLE['diagonalX'], -STYLE['diagonalY']),
            (0, -STYLE['verticalDistance']), (STYLE['diagonalX'], -STYLE['diagonalY']),
        )
        self.radial = tuple(
            self.button(item, x, y, STYLE['radialWidth'], STYLE['radialHeight'],
                        slot=f'{"child" if child else "radial"}-{index}') if item else None
            for index, (item, (x, y)) in enumerate(zip(menu.groups['RADIAL'], positions))
        )
        self.blocks = []
        if any(any(item is not None for item in items) for items in extra_groups):
            for group, y, items in zip(('top', 'bottom'),
                                       (block_distance, -block_distance), extra_groups):
                if not any(item is not None for item in items):
                    continue
                row_step = STYLE['extraHeight'] + STYLE['rowGap']
                column_step = STYLE['extraWidth'] + STYLE['columnGap']
                buttons = tuple(
                    self.button(item, (index % 3 - 1) * column_step,
                                y + block_height / 2 - STYLE['extraHeight'] / 2 - row_step * (index // 3),
                                STYLE['extraWidth'], STYLE['extraHeight'], slot=f'{group}-block-{index}')
                    for index, item in enumerate(items) if item is not None
                )
                self.blocks.append((self.rect(0, y, STYLE['extraWidth'] * 3 + 2 * STYLE['columnGap'],
                                             block_height), buttons))

    def rect(self, x, y, width, height):
        cx, cy = self.center
        return rectangle(cx + x * self.scale, cy + y * self.scale,
                         width * self.scale, height * self.scale)

    def button(self, item, x, y, width, height, suffix='', slot=''):
        return Button(item, self.rect(x, y, width, height), suffix, slot)

    def target(self, point, gesture=False, allow_extra=False):
        dx, dy = point[0] - self.center[0], point[1] - self.center[1]
        if gesture and math.hypot(dx, dy) < 24 * self.scale:
            return None
        if not gesture or allow_extra:
            for _, buttons in self.blocks:
                hit = next((button for button in buttons if button.contains(point)), None)
                if hit:
                    return hit
        hit = next((button for button in self.radial if button and button.contains(point)), None)
        if hit:
            return hit
        if gesture:
            sector = math.floor(math.atan2(dy, dx) / (math.pi / 4) + 0.5) % 8
            return self.radial[sector]
        return None


class VIEW3D_OT_pie_prototype(bpy.types.Operator):
    bl_idname = 'view3d.pie_prototype'
    bl_label = 'PieCompose'
    active = None
    marker_shape = 'bar'
    menu_id: bpy.props.StringProperty(options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and context.region is not None and context.region.type == 'WINDOW')

    def invoke(self, context, event):
        if self.__class__.active is not None:
            return {'CANCELLED'}
        try:
            refresh_library()
        except (OSError, ValueError, TypeError) as error:
            self.report({'ERROR'}, f'Could not read menus: {error}')
            return {'CANCELLED'}
        self._menu_id = self.menu_id or LIBRARY.first_menu
        if self._menu_id not in LIBRARY.menus:
            self.report({'WARNING'}, 'Menu was deleted. Reopen the editor.')
            return {'CANCELLED'}
        self.history = []
        self.area = context.area
        self.region = context.region
        self.region_id = context.region.as_pointer()
        self.point = self.mouse(event)
        self.origin = self.point
        self.gesture_start = self.point
        self.extra_gesture_ready_at = None
        hotkey = LIBRARY.menus[self._menu_id].hotkey
        self.trigger_key = hotkey['type'] if hotkey else None
        self.holding = event.type == self.trigger_key and event.value == 'PRESS'
        self.scale = max(context.preferences.system.ui_scale, 0.5)
        self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        self.handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_overlay, (), 'WINDOW', 'POST_PIXEL'
        )
        self.__class__.active = self
        context.window_manager.modal_handler_add(self)
        self.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def mouse(self, event):
        return event.mouse_x - self.region.x, event.mouse_y - self.region.y

    def menu_layout(self):
        menu = LIBRARY.menus.get(self._menu_id, LIBRARY.menus[LIBRARY.first_menu])
        return PieLayout(self.region.width, self.region.height, self.origin, self.scale, menu=menu)

    def navigate_back(self):
        if self.history:
            self._menu_id = self.history.pop()
            self.holding = False

    def open_submenu(self, target):
        if target not in LIBRARY.menus:
            self.report({'WARNING'}, 'Submenu is missing')
            return
        if target in self.history:
            index = self.history.index(target)
            self.history = self.history[:index]
        elif target != self._menu_id:
            self.history.append(self._menu_id)
        self._menu_id = target
        self.holding = False

    def start_gesture_delay(self):
        deadline = monotonic() + EXTRA_GESTURE_DELAY
        self.extra_gesture_ready_at = deadline
        operator_type = type(self)

        def redraw_when_ready():
            if (operator_type.active is self and self.holding
                    and self.extra_gesture_ready_at == deadline):
                remaining = deadline - monotonic()
                if remaining > 0:
                    return remaining
                self.area.tag_redraw()

        bpy.app.timers.register(redraw_when_ready, first_interval=EXTRA_GESTURE_DELAY)

    def gesture_target(self, layout):
        deadline = self.extra_gesture_ready_at
        return layout.target(self.point, gesture=True,
                             allow_extra=deadline is not None and monotonic() >= deadline)

    def draw_overlay(self):
        context = bpy.context
        if context.region is None or context.region.as_pointer() != self.region_id:
            return
        layout = self.menu_layout()
        theme = context.preferences.themes[0].user_interface
        scale = layout.scale
        gesture = self.holding and math.dist(self.point, self.gesture_start) >= 24 * scale
        active = self.gesture_target(layout) if gesture else layout.target(self.point)
        cx, cy = layout.center
        previous_blend = gpu.state.blend_get()
        gpu.state.blend_set('ALPHA')
        try:
            for _, buttons in layout.blocks:
                for button in buttons:
                    self.draw_button(context, button, active, scale, extra=True)
            for button in layout.radial:
                if button:
                    self.draw_button(context, button, active, scale)
            outer = layout.rect(0, 0, 42, 42)
            fill(self.shader, outer, theme_rgba(theme.wcol_pie_menu.outline), 21 * scale)
            fill(self.shader, layout.rect(0, 0, 26, 26), theme_rgba(theme.wcol_pie_menu.inner), 13 * scale)
            if self.history:
                label('‹ Back · Esc', cx, cy - 38 * scale, 11 * scale,
                      theme_rgba(theme.wcol_pie_menu.text), 'center')
        finally:
            gpu.state.blend_set(previous_blend)

    def draw_button(self, context, button, active, scale, extra=False):
        hovered = button == active
        theme = context.preferences.themes[0].user_interface
        widget = theme.wcol_tool if extra else theme.wcol_pie_menu
        color = theme_rgba(widget.inner_sel) if hovered else rgba('#1c1c1c') if extra else theme_rgba(widget.inner)
        radius = min(STYLE['radius'] * scale, (button.rect[3] - button.rect[1]) / 2)
        fill(self.shader, button.rect, theme_rgba(widget.outline), radius)
        left, bottom, right, top = button.rect
        inset = scale
        fill(self.shader, (left + inset, bottom + inset, right - inset, top - inset),
             color, max(0, radius - inset))
        text = button.item.label
        suffix = button.suffix
        if button.item.action in {'submenu', 'back'}:
            text += '  ›' if button.item.action == 'submenu' else '  ‹'
        checked = toggle_state(context, button.item)
        font_size = STYLE['fontSize'] * scale
        baseline = (bottom + top) / 2 - font_size * 0.32
        text_left = left + STYLE['padding'] * scale
        if button.item.marker_color and button.item.marker_color != 'none':
            marker_color = button.item.marker_color
            diameter = STYLE['markerSize'] * scale
            if self.marker_shape == 'bar':
                width = 3 * scale
                height = min(16 * scale, top - bottom - 12 * scale)
                marker = rectangle(text_left + diameter / 2, (bottom + top) / 2, width, height)
                fill(self.shader, marker, rgba(marker_color), width / 2)
            else:
                marker = rectangle(text_left + diameter / 2, (bottom + top) / 2, diameter, diameter)
                fill(self.shader, marker, rgba(marker_color), diameter / 2)
            text_left += diameter + 8 * scale
        if checked is not None:
            checkbox = (text_left, baseline - scale, text_left + 11 * scale, baseline + 10 * scale)
            fill(self.shader, checkbox, rgba('#ababab' if checked else '#929292'), 2 * scale)
            fill(self.shader, (checkbox[0] + 2 * scale, checkbox[1] + 2 * scale,
                               checkbox[2] - 2 * scale, checkbox[3] - 2 * scale),
                 rgba('#ababab' if checked else '#242424'), scale)
            text_left += 19 * scale
            suffix = ''
        blf.size(FONT_ID, font_size)
        available = right - text_left - (25 if suffix else 9) * scale
        if blf.dimensions(FONT_ID, text)[0] > available:
            while text and blf.dimensions(FONT_ID, text + '…')[0] > available:
                text = text[:-1]
            text += '…'
        label(text, text_left, baseline, font_size,
              theme_rgba(widget.text_sel if hovered else widget.text))
        if suffix:
            label(suffix, right - 8 * scale, baseline, (STYLE['fontSize'] - 1) * scale,
                  theme_rgba(widget.text_sel if hovered else widget.text), 'right')

    def modal(self, context, event):
        if self.handler is None:
            return {'CANCELLED'}
        if event.type in {'ESC', 'BACK_SPACE'} and event.value == 'PRESS' and self.history:
            self.navigate_back()
            self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'WINDOW_DEACTIVATE' or (event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS'):
            self.cancel(context)
            return {'CANCELLED'}
        self.point = self.mouse(event)
        layout = self.menu_layout()
        self.area.tag_redraw()

        button = None
        if event.type == getattr(self, 'trigger_key', None) and event.value == 'PRESS' and not event.is_repeat:
            self.holding = True
            self.gesture_start = self.point
            self.extra_gesture_ready_at = None
        elif event.type == getattr(self, 'trigger_key', None) and event.value == 'RELEASE' and self.holding:
            self.holding = False
            if math.dist(self.point, self.gesture_start) >= 24 * layout.scale:
                button = VIEW3D_OT_pie_prototype.gesture_target(self, layout)
        elif (event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'} and self.holding
              and self.extra_gesture_ready_at is None
              and math.dist(self.point, self.gesture_start) >= 24 * layout.scale):
            self.start_gesture_delay()
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if math.dist(self.point, layout.center) < 24 * layout.scale:
                if self.history:
                    self.navigate_back()
                else:
                    self.cancel(context)
                    return {'CANCELLED'}
                return {'RUNNING_MODAL'}
            button = layout.target(self.point)
            if button is None:
                self.cancel(context)
                return {'CANCELLED'}

        if button is None:
            return {'RUNNING_MODAL'}
        action = button.item.action
        if action in {'submenu', 'back'}:
            if action == 'back':
                self.navigate_back()
            else:
                self.open_submenu(button.item.target_menu)
            return {'RUNNING_MODAL'}

        self.cancel(context)
        try:
            if not self.execute_item(context, button.item):
                return {'CANCELLED'}
        except (RuntimeError, TypeError, ValueError, AttributeError) as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}

    def execute_item(self, context, item):
        action = item.action
        if action == 'shortcut':
            source = shortcut_command(context, item.properties)
            if source is None:
                self.report({'WARNING'}, f'{hotkey_text(item.properties)} has no available command in this context')
                return False
            item = replace(item, action=source.idname, properties=capture_operator_properties(source.properties), invoke=True)
            action = item.action
        settings = context.scene.tool_settings
        if action == 'origins':
            settings.use_transform_data_origin = not settings.use_transform_data_origin
        elif action == 'overlays':
            overlay = context.space_data.overlay
            overlay.show_overlays = not overlay.show_overlays
        elif action in {'pivot_cursor', 'pivot_median'}:
            settings.transform_pivot_point = 'CURSOR' if action == 'pivot_cursor' else 'MEDIAN_POINT'
        else:
            if action == 'wm.context_toggle' and not item.properties.get('module'):
                if resolve_boolean(context, item.properties.get('data_path'), writable=True) is None:
                    self.report({'WARNING'}, f'{item.label}: the active target is missing or read-only')
                    return False
            namespace, name = action.split('.')
            operator = getattr(getattr(bpy.ops, namespace), name)
            if not operator.poll():
                self.report({'WARNING'}, f'{item.label} is unavailable in this context')
                return False
            arguments = dict(item.properties)
            previous_toggle = toggle_state(context, item)
            if action == 'view3d.view_axis' and not arguments:
                arguments = {'type': 'FRONT'}
            rna = operator.get_rna_type()
            arguments = restore_operator_parameters(arguments, rna, interactive=item.invoke)
            result = operator('INVOKE_DEFAULT' if item.invoke else 'EXEC_DEFAULT', **arguments)
            # Blender's context-toggle operator uses CANCELLED when a setting
            # changes without needing an undo step (e.g. viewport display).
            changed_without_undo = (action == 'wm.context_toggle' and previous_toggle is not None
                                    and toggle_state(context, item) is (not previous_toggle))
            if action == 'wm.context_toggle' and previous_toggle is not None and not changed_without_undo:
                self.report({'WARNING'}, f'{item.label}: this property could not be changed in the active context')
                return False
            if 'CANCELLED' in result and not changed_without_undo:
                return False
        self.report({'INFO'}, item.label)
        return True

    def cancel(self, context):
        if self.handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handler, 'WINDOW')
            self.handler = None
            self.__class__.active = None
            self.area.tag_redraw()


KEYMAPS = []
KEYMAPS_READY = False
KEYMAP_SIGNATURE = None


def hotkey_text(hotkey):
    if hotkey is None:
        return 'No hotkey'
    parts = [label for field, label in (('ctrl', 'Ctrl'), ('shift', 'Shift'), ('alt', 'Alt'), ('oskey', 'Win'))
             if hotkey.get(field)]
    key = hotkey['type'].replace('NUMPAD_', 'Num ').replace('_', ' ').title()
    return '+'.join(parts + [key.upper() if len(key) == 1 or key.startswith('F') and key[1:].isdigit() else key])


def sync_keymaps():
    global KEYMAP_SIGNATURE
    signature = tuple((key, hotkey_signature(menu.hotkey)) for key, menu in LIBRARY.menus.items())
    if signature == KEYMAP_SIGNATURE:
        return
    addon = bpy.context.window_manager.keyconfigs.addon
    if addon is None:
        return
    for keymap, item in KEYMAPS:
        keymap.keymap_items.remove(item)
    KEYMAPS.clear()
    keymap = addon.keymaps.new(name='3D View', space_type='VIEW_3D')
    for key, menu in LIBRARY.menus.items():
        if menu.hotkey:
            item = keymap.keymap_items.new(VIEW3D_OT_pie_prototype.bl_idname,
                                          **normalize_hotkey(menu.hotkey), value='PRESS')
            item.properties.menu_id = key
            KEYMAPS.append((keymap, item))
    KEYMAP_SIGNATURE = signature


HOTKEY_ITEMS = [(item.identifier, item.name, '')
                for item in bpy.types.Event.bl_rna.properties['type'].enum_items
                if item.identifier in HOTKEY_KEYS]


def capture_operator_properties(properties, depth=0):
    if depth > 16:
        raise ValueError('Command parameters are nested too deeply')
    values = {}
    for prop in properties.bl_rna.properties:
        key = prop.identifier
        if key == 'rna_type' or not properties.is_property_set(key):
            continue
        value = getattr(properties, key)
        if prop.type == 'POINTER' and isinstance(value, bpy.types.OperatorProperties):
            # Macro operators (Duplicate + Move, Extrude + Move, etc.) own
            # nested operator settings, not references to Blender scene data.
            values[key] = capture_operator_properties(value, depth + 1)
            continue
        if prop.type in {'POINTER', 'COLLECTION'}:
            raise ValueError('This command contains a data reference or collection')
        if getattr(prop, 'is_array', False) or isinstance(value, set):
            value = list(value)
        values[key] = value
    return values


def restore_operator_parameters(values, rna, interactive=False):
    result = {}
    for name, value in values.items():
        prop = rna.properties.get(name)
        if prop is not None and prop.type == 'ENUM' and prop.is_enum_flag:
            value = set(value)
        elif prop is not None and prop.type == 'POINTER' and isinstance(value, dict):
            value = restore_operator_parameters(value, prop.fixed_type, interactive=interactive)
        result[name] = value
    if interactive:
        for prop in rna.properties:
            if (prop.type == 'POINTER' and prop.identifier != 'rna_type'
                    and prop.fixed_type.identifier.startswith('TRANSFORM_OT_')
                    and prop.fixed_type.properties.get('release_confirm') is not None):
                # The pie's initiating click/key release must not immediately
                # confirm the transform stage of Duplicate/Extrude macros.
                result.setdefault(prop.identifier, {}).setdefault('release_confirm', False)
    return result


def capture_operator(properties):
    """Copy RNA values while the source button's context is still alive."""
    namespace, name = properties.bl_rna.identifier.split('_OT_', 1)
    identifier = f'{namespace.lower()}.{name}'
    operator = getattr(getattr(bpy.ops, namespace.lower()), name)
    values = capture_operator_properties(properties)
    # JSON verifies that no reference to Blender's transient button survives.
    return identifier, operator.get_rna_type().name, json.dumps(values, ensure_ascii=False)


RADIAL_NAMES = ('Right · 6', 'Top right · 9', 'Top · 8', 'Top left · 7',
                'Left · 4', 'Bottom left · 1', 'Bottom · 2', 'Bottom right · 3')
SLOT_ITEMS = [(f'RADIAL_{index}', name, '') for index, name in enumerate(RADIAL_NAMES)]
SLOT_ITEMS += [(f'{group}_{index}', f'{title} · {index + 1}', '')
               for group, title in (('TOP', 'Top block'), ('BOTTOM', 'Bottom block'))
               for index in range(GROUP_SIZES[group])]
CATEGORY_ITEMS = (
    ('auto', 'Automatic', ''), ('transform', 'Transform', ''),
    ('view', 'View and display', ''), ('cursor', 'Cursor and pivot', ''),
    ('menu', 'Modeling and menus', ''),
)
MARKER_ITEMS = (
    ('existing', 'Choose label', 'Choose a saved color label by name'),
    ('new', 'New label', 'Save a named color label and assign it to this button'),
)


def label_action(property_name):
    def update(self, context):
        owner = operator_owner(self)
        if owner is None or owner._loading or not getattr(owner, property_name):
            return
        owner._loading = True
        setattr(owner, property_name, False)
        owner._loading = False
        owner.perform_label(property_name)
    return update


def draw_collapsible(layout, operator, property_name, title, summary='', icon_value=0):
    section = layout.box()
    header = section.row(align=True)
    expanded = getattr(operator, property_name)
    text = f'{title} · {summary}' if summary else title
    header.prop(operator, property_name, text=text,
                icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT', emboss=False)
    if icon_value:
        header.label(text='', icon_value=icon_value)
    return section.column() if expanded else None


def draw_marker_fields(layout, operator, show_header=True):
    if show_header:
        layout.separator()
        layout.label(text='Labels')
        assigned = operator._document.palette.get(operator.assigned_marker, 'None')
        layout.label(text=f'Assigned: {assigned}')
    layout.prop(operator, 'marker_mode', text='')
    if operator.marker_mode == 'new':
        layout.prop(operator, 'marker_name', text='Name')
        layout.prop(operator, 'marker_color', text='Color')
        layout.prop(operator, 'save_label', toggle=True, icon='FILE_TICK')
    elif operator.marker_mode == 'existing':
        layout.prop(operator, 'palette_choice', text='')
        edit = layout.column()
        edit.enabled = operator.palette_choice in operator._document.palette
        edit.prop(operator, 'marker_name', text='Name')
        edit.prop(operator, 'marker_color', text='Color')
        edit.prop(operator, 'update_label', toggle=True, icon='FILE_TICK')
        assign = layout.column()
        assign.enabled = operator.palette_choice in operator._document.palette and (
            hasattr(operator, 'destination_menu') or operator.item_kind != 'empty')
        assign.prop(operator, 'assign_label', toggle=True, icon='LINKED')
    remove = layout.column()
    remove.enabled = operator.assigned_marker != 'none'
    remove.prop(operator, 'remove_label', toggle=True, icon='UNLINKED')
    if operator.marker_mode == 'existing':
        usage = palette_usage(operator._document, operator.palette_choice)
        layout.separator()
        delete = layout.column()
        delete.enabled = operator.palette_choice in operator._document.palette
        delete.prop(operator, 'delete_label', toggle=True, icon='TRASH')
        if usage:
            layout.label(text=f'Used by {usage} button(s)')


def first_palette_color(library):
    return next(iter(library.palette), '__none__')


def palette_rgb(color):
    return rgba(color if color != '__none__' else STYLE['viewColor'])[:3]


MENU_ENUM_CACHE = {}
PALETTE_ENUM_CACHE = {}
SLOT_ENUM_CACHE = {}
OPERATOR_STATES = {}


def operator_state_key(operator):
    if isinstance(operator, bpy.types.Operator):
        return operator.properties.as_pointer()
    return operator.as_pointer()


def operator_owner(properties):
    return OPERATOR_STATES.get(operator_state_key(properties), {}).get('owner')


def event_draft(operator, state_key, keymap_name):
    if not isinstance(operator, bpy.types.Operator):
        return None
    state = OPERATOR_STATES.setdefault(operator_state_key(operator), {})
    if state_key not in state:
        addon = bpy.context.window_manager.keyconfigs.addon
        if addon is None:
            return None
        # This non-dispatched keymap only hosts Blender's native key recorder.
        keymap = addon.keymaps.new(name=keymap_name, space_type='EMPTY')
        item = keymap.keymap_items.new('view3d.pie_prototype', 'F8', 'PRESS')
        item.active = False
        if state_key == 'shortcut_draft':
            item.type = 'NONE'
        state[state_key] = (keymap, item)
    return state[state_key][1]


def hotkey_draft(operator):
    return event_draft(operator, 'hotkey_draft', 'Pie Menu Editor Hotkey Draft')


def shortcut_draft(operator):
    return event_draft(operator, 'shortcut_draft', 'PieCompose Action Shortcut Draft')


def discard_hotkey_draft(operator):
    state = OPERATOR_STATES.get(operator_state_key(operator), {})
    for state_key in ('hotkey_draft', 'shortcut_draft'):
        draft = state.pop(state_key, None)
        if draft:
            keymap, item = draft
            keymap.keymap_items.remove(item)
            if not keymap.keymap_items:
                bpy.context.window_manager.keyconfigs.addon.keymaps.remove(keymap)


def shortcut_value(operator):
    draft = shortcut_draft(operator)
    if draft is None:
        raise ValueError('Choose a keyboard shortcut')
    return normalize_hotkey({'type': draft.type, **{
        field: bool(getattr(draft, field)) for field in ('ctrl', 'shift', 'alt', 'oskey')
    }})


def shortcut_command(context, value):
    def available(identifier):
        try:
            namespace, name = identifier.split('.', 1)
            return getattr(getattr(bpy.ops, namespace), name).poll()
        except (AttributeError, ValueError, RuntimeError):
            return False
    return resolve_shortcut(context, value, available)


def draft_hotkey_value(operator):
    draft = hotkey_draft(operator)
    if draft is not None:
        return normalize_hotkey({'type': draft.type, **{
            modifier: bool(getattr(draft, modifier)) for modifier in ('ctrl', 'shift', 'alt', 'oskey')
        }})
    return normalize_hotkey({'type': operator.hotkey_type, **{
        modifier: getattr(operator, 'hotkey_' + modifier) for modifier in ('ctrl', 'shift', 'alt', 'oskey')
    }})


class PieOperatorState:
    """Blender calls property updates with OperatorProperties, not the operator."""

    @property
    def _document(self):
        return OPERATOR_STATES.get(operator_state_key(self), {}).get('document')

    @_document.setter
    def _document(self, value):
        OPERATOR_STATES.setdefault(operator_state_key(self), {}).update(document=value, owner=self)

    @property
    def _loading(self):
        return OPERATOR_STATES.get(operator_state_key(self), {}).get('loading', True)

    @_loading.setter
    def _loading(self, value):
        OPERATOR_STATES.setdefault(operator_state_key(self), {}).update(loading=value, owner=self)

    @property
    def _message(self):
        return OPERATOR_STATES.get(operator_state_key(self), {}).get('message', '')

    @_message.setter
    def _message(self, value):
        OPERATOR_STATES.setdefault(operator_state_key(self), {}).update(message=value, owner=self)

    def cancel(self, context):
        discard_hotkey_draft(self)
        OPERATOR_STATES.pop(operator_state_key(self), None)

    def perform_label(self, action):
        candidate = clone_library(self._document)
        try:
            if action == 'delete_label':
                deleted = self.palette_choice
                affected = palette_usage(candidate, deleted)
                delete_palette_color(candidate, deleted)
                save_library(candidate)
                self._document = clone_library(LIBRARY)
                self._loading = True
                self.palette_choice = first_palette_color(self._document)
                self.marker_color = palette_rgb(self.palette_choice)
                self.marker_name = self._document.palette.get(self.palette_choice, '')
                if self.assigned_marker == deleted:
                    self.assigned_marker = 'none'
                self._loading = False
                self._message = f'Label deleted. Cleared from {affected} button(s).'
                return
            if action == 'update_label':
                previous = self.palette_choice
                color = '#' + ''.join(f'{round(channel * 255):02x}' for channel in self.marker_color)
                color = update_palette_color(candidate, previous, self.marker_name, color)
                save_library(candidate)
                self._document = clone_library(LIBRARY)
                self._loading = True
                self.palette_choice = color
                self.marker_color = rgba(color)[:3]
                self.marker_name = self._document.palette[color]
                if self.assigned_marker == previous:
                    self.assigned_marker = color
                self._loading = False
                self._message = 'Label updated on all assigned buttons.'
                return
            if action == 'save_label':
                color = '#' + ''.join(f'{round(channel * 255):02x}' for channel in self.marker_color)
                color = add_palette_color(candidate, self.marker_name, color)
                save_library(candidate)
                self._document = clone_library(LIBRARY)
                self._loading = True
                self.marker_mode = 'existing'
                self.palette_choice = color
                self.marker_color = rgba(color)[:3]
                self._loading = False
                self._message = 'Label saved. Click Assign label to use it.'
                return
            color = 'none' if action == 'remove_label' else self.palette_choice
            if color != 'none' and color not in candidate.palette:
                raise ValueError('Choose an existing label')
            if not hasattr(self, 'destination_menu'):
                slots, index = menu_slot(candidate, self.menu_choice, self.slot)
                if slots[index] is None:
                    raise ValueError('Save the button before assigning a label')
                slots[index] = replace(slots[index], marker_color=color)
                save_library(candidate)
                self._document = clone_library(LIBRARY)
            self.assigned_marker = color
            self._message = 'Label removed.' if color == 'none' else 'Label assigned.'
        except (OSError, ValueError, TypeError, RuntimeError, KeyError) as error:
            self._loading = False
            self._message = str(error)
            self.report({'WARNING'}, self._message)


def menu_choices(self, context):
    owner = operator_owner(self) if self is not None else None
    library = getattr(owner, '_document', None) or LIBRARY
    signature = tuple((key, menu.name) for key, menu in library.menus.items())
    if signature not in MENU_ENUM_CACHE:
        MENU_ENUM_CACHE[signature] = [(key, name, '') for key, name in signature]
    return MENU_ENUM_CACHE[signature]


def capture_menu_changed(self, context):
    owner = operator_owner(self)
    if owner is not None and not owner._loading:
        remember_menu(owner.destination_menu, owner._document)


def palette_choices(self, context):
    owner = operator_owner(self) if self is not None else None
    library = getattr(owner, '_document', None) or LIBRARY
    signature = tuple(library.palette.items())
    if signature not in PALETTE_ENUM_CACHE:
        PALETTE_ENUM_CACHE[signature] = [(color, name, color, label_icon(color), index)
                                       for index, (color, name) in enumerate(signature)] or [
                                           ('__none__', 'No saved labels', 'Create a new label first', 0, 0)]
    return PALETTE_ENUM_CACHE[signature]


def palette_selection_changed(self, context):
    owner = operator_owner(self)
    if owner is not None and not owner._loading and owner.palette_choice:
        owner.marker_color = palette_rgb(owner.palette_choice)
        owner.marker_name = owner._document.palette.get(owner.palette_choice, '')


def slot_choices(self, context):
    owner = operator_owner(self) if self is not None else None
    library = getattr(owner, '_document', None) or LIBRARY
    menu_id = (getattr(owner, 'menu_choice', '') or getattr(owner, 'destination_menu', '')) if owner else ''
    menu = library.menus.get(menu_id or library.first_menu)
    signature = tuple((identifier, name, menu.groups[group][int(index)].marker_color
                       if menu.groups[group][int(index)] else 'none')
                      for identifier, name, _ in SLOT_ITEMS
                      for group, index in [identifier.rsplit('_', 1)])
    if signature not in SLOT_ENUM_CACHE:
        SLOT_ENUM_CACHE[signature] = [(identifier, name, '', label_icon(color), index)
                                     for index, (identifier, name, color) in enumerate(signature)]
    return SLOT_ENUM_CACHE[signature]


def menu_slot(library, menu_id, slot):
    group, index = slot.rsplit('_', 1)
    return library.menus[menu_id].groups[group], int(index)


LABEL_PREVIEWS = None


def label_icon(color):
    global LABEL_PREVIEWS
    if not color or color == 'none':
        return 0
    if LABEL_PREVIEWS is None:
        LABEL_PREVIEWS = bpy.utils.previews.new()
    if color not in LABEL_PREVIEWS:
        preview = LABEL_PREVIEWS.new(color)
        preview.icon_size = (16, 16)
        red, green, blue, _ = rgba(color)
        pixels = []
        for y in range(16):
            for x in range(16):
                alpha = max(0.0, min(1.0, 6.5 - math.hypot(x - 7.5, y - 7.5)))
                pixels.extend((red * alpha, green * alpha, blue * alpha, alpha))
        preview.icon_pixels_float = pixels
    return LABEL_PREVIEWS[color].icon_id


def draw_slot_grid(layout, operator, library, menu_id):
    moving = getattr(operator, 'choosing_destination', False)

    def cell(target, group, index):
        item = library.menus[menu_id].groups[group][index]
        text = item.label if item else '+'
        if item and item.action == 'submenu':
            text += ' ›'
        slot = f'{group}_{index}'
        target.enabled = not (moving and slot == operator.move_source)
        target.prop_enum(operator, 'slot', slot, text=text)

    # Shared dimensions and native gaps keep the three groups aligned;
    # captions sit between groups, following the selected visual reference.
    groups = (
        ('TOP', ((0, 1, 2), (3, 4, 5))),
        ('RADIAL', ((3, 2, 1), (4, None, 0), (5, 6, 7))),
        ('BOTTOM', ((0, 1, 2), (3, 4, 5))),
    )
    for group, rows in groups:
        if group != 'TOP':
            heading = layout.row()
            heading.alignment = 'CENTER'
            heading.scale_y = 1.2
            heading.label(text='Upper buttons' if group == 'RADIAL' else 'Lower buttons')
        grid = layout.grid_flow(row_major=True, columns=3, even_columns=True,
                                even_rows=True, align=False)
        grid.scale_y = 1.5
        for indices in rows:
            for index in indices:
                column = grid.column()
                if index is None:
                    center = column.row()
                    center.alignment = 'CENTER'
                    center.label(text='Choose slot' if moving else 'Pie Menu')
                else:
                    cell(column, group, index)


class WM_OT_pie_capture(PieOperatorState, bpy.types.Operator):
    bl_idname = 'wm.pie_capture'
    bl_label = 'Add to PieCompose'
    bl_description = 'Copy this button command and choose a slot in PieCompose'
    bl_options = {'INTERNAL'}

    command: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    parameters: bpy.props.StringProperty(default='{}', options={'HIDDEN', 'SKIP_SAVE'})
    caption: bpy.props.StringProperty(name='Button name', options={'SKIP_SAVE'})
    slot: bpy.props.EnumProperty(name='Slot', items=slot_choices, options={'SKIP_SAVE'})
    category: bpy.props.EnumProperty(name='Marker category', items=CATEGORY_ITEMS,
                                    default='auto', options={'SKIP_SAVE'})
    marker_mode: bpy.props.EnumProperty(name='Label', items=MARKER_ITEMS, default='existing', options={'SKIP_SAVE'})
    palette_choice: bpy.props.EnumProperty(name='Existing label', items=palette_choices,
                                          update=palette_selection_changed, options={'SKIP_SAVE'})
    marker_name: bpy.props.StringProperty(name='Label name', options={'SKIP_SAVE'})
    assigned_marker: bpy.props.StringProperty(default='none', options={'HIDDEN', 'SKIP_SAVE'})
    assign_label: bpy.props.BoolProperty(name='Assign label', update=label_action('assign_label'), options={'SKIP_SAVE'})
    remove_label: bpy.props.BoolProperty(name='Clear label', update=label_action('remove_label'), options={'SKIP_SAVE'})
    save_label: bpy.props.BoolProperty(name='Save label', update=label_action('save_label'), options={'SKIP_SAVE'})
    update_label: bpy.props.BoolProperty(name='Update label', update=label_action('update_label'), description='Save label name and color on all assigned buttons', options={'SKIP_SAVE'})
    delete_label: bpy.props.BoolProperty(name='Delete label', update=label_action('delete_label'), description='Delete this label and clear it from all buttons', options={'SKIP_SAVE'})
    marker_color: bpy.props.FloatVectorProperty(name='Label color', subtype='COLOR_GAMMA', size=3,
                                               min=0, max=1, default=(0.412, 0.749, 0.686), options={'SKIP_SAVE'})
    destination_menu: bpy.props.EnumProperty(name='Menu', items=menu_choices,
                                           update=capture_menu_changed, options={'SKIP_SAVE'})

    def invoke(self, context, event):
        if not self.command:
            self.report({'WARNING'}, 'Right-click a Blender button to choose a command')
            return {'CANCELLED'}
        try:
            refresh_library()
        except (OSError, ValueError, TypeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self._document = clone_library(LIBRARY)
        self._loading = True
        self.palette_choice = first_palette_color(self._document)
        self.marker_color = palette_rgb(self.palette_choice)
        self.marker_name = self._document.palette.get(self.palette_choice, '')
        self._loading = False
        explicit = self.properties.is_property_set('destination_menu')
        self.destination_menu = (self.destination_menu if explicit and self.destination_menu in LIBRARY.menus
                                 else preferred_menu(LIBRARY))
        remember_menu(self.destination_menu, LIBRARY)
        return context.window_manager.invoke_props_dialog(self, width=620,
                                                         confirm_text='Save')

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'caption')
        layout.prop(self, 'destination_menu')
        layout.label(text=self.command, icon='CONSOLE')
        if self.command == 'wm.context_toggle':
            layout.label(text='Target: ' + binding_description(json.loads(self.parameters).get('data_path')))
        layout.label(text='Choose a slot. Its current button will be replaced.')
        draw_slot_grid(layout, self, self._document, self.destination_menu)
        draw_marker_fields(layout, self)
        layout.label(text='The button is saved in your configuration.')
        if self._message:
            layout.label(text=self._message, icon='INFO')

    def execute(self, context):
        try:
            if self._document is None:
                refresh_library()
                self._document = clone_library(LIBRARY)
            destination = (self.destination_menu if self.properties.is_property_set('destination_menu')
                           else preferred_menu(self._document))
            values = json.loads(self.parameters)
            if not isinstance(values, dict):
                raise ValueError('Invalid command parameters')
            command = normalize_command_identifier(self.command)
            namespace, name = command.split('.', 1)
            getattr(getattr(bpy.ops, namespace), name).get_rna_type()
            candidate = clone_library(self._document)
            slots, index = menu_slot(candidate, destination, self.slot)
            slots[index] = Item(
                self.caption.strip() or command, command, invoke=True,
                properties=values, category=self.category, marker_color=self.assigned_marker
            )
            save_library(candidate)
        except (OSError, ValueError, TypeError, AttributeError, RuntimeError, KeyError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        remember_menu(destination, LIBRARY)
        self.report({'INFO'}, f'Button "{self.caption}" saved')
        OPERATOR_STATES.pop(operator_state_key(self), None)
        return {'FINISHED'}


def resolve_boolean_property(context, data_path):
    return resolve_boolean(context, data_path)


def toggle_state(context, item):
    if item.action == 'origins':
        return context.scene.tool_settings.use_transform_data_origin
    if item.action == 'overlays':
        return context.space_data.overlay.show_overlays
    if item.action == 'wm.context_toggle' and not item.properties.get('module'):
        target = resolve_boolean_property(context, item.properties.get('data_path'))
        if target is not None:
            return target.value
    return None


def capture_button(context):
    """Capture an operator or a supported property-backed Blender button."""
    source = getattr(context, 'button_operator', None)
    if source is not None:
        return capture_operator(source)
    pointer = getattr(context, 'button_pointer', None)
    prop = getattr(context, 'button_prop', None)
    if (isinstance(pointer, bpy.types.View3DShading) and prop is not None
            and prop.identifier in {'show_xray', 'show_xray_wireframe'}):
        # The shading popover uses properties instead of the header's operator.
        # Save the standard operator so the action follows the active viewport
        # and its Solid/Wireframe/Pose context, without retaining a data pointer.
        return 'view3d.toggle_xray', 'X-Ray', '{}'
    if pointer is not None and prop is not None and prop.type == 'BOOLEAN':
        data_path = capture_boolean_path(context, pointer, prop)
        return 'wm.context_toggle', prop.name or prop.identifier.replace('_', ' '), json.dumps({'data_path': data_path})
    return None


def draw_button_context(self, context):
    try:
        captured = capture_button(context)
        if captured is None:
            return
        command, caption, parameters = captured
    except (ValueError, TypeError, AttributeError, RuntimeError) as error:
        self.layout.separator()
        unavailable = self.layout.row()
        unavailable.enabled = False
        unavailable.label(text=f'Cannot add this button: {error}', icon='INFO')
        return
    if command == WM_OT_pie_capture.bl_idname:
        return
    self.layout.separator()
    button = self.layout.operator(WM_OT_pie_capture.bl_idname, text='Add to PieCompose…')
    button.command = command
    button.caption = caption
    button.parameters = parameters


def editor_selection_changed(self, context):
    owner = operator_owner(self)
    if owner is not None and not owner._loading:
        if owner.choosing_destination:
            owner._loading = True
            owner.move_target = owner.slot
            owner.slot = owner.move_source
            owner._loading = False
            owner.perform('move_item')
        else:
            owner.load_fields()


def editor_menu_changed(self, context):
    owner = operator_owner(self)
    if owner is not None and not owner._loading:
        owner.choosing_destination = False
        owner.move_source = ''
        owner.load_fields()


def editor_action(property_name):
    def update(self, context):
        owner = operator_owner(self)
        if owner is None or owner._loading or not getattr(owner, property_name):
            return
        owner._loading = True
        setattr(owner, property_name, False)
        owner._loading = False
        owner.perform(property_name)
    return update


class WM_OT_pie_editor(PieOperatorState, bpy.types.Operator):
    bl_idname = 'wm.pie_editor'
    bl_label = 'PieCompose: Menu Editor'
    bl_description = 'Create menus, edit buttons and link pie menus'

    menu_choice: bpy.props.EnumProperty(name='Menu', items=menu_choices,
                                       update=editor_menu_changed, options={'SKIP_SAVE'})
    slot: bpy.props.EnumProperty(name='Slot', items=slot_choices,
                                update=editor_selection_changed, options={'SKIP_SAVE'})
    menu_name: bpy.props.StringProperty(name='Menu name', options={'SKIP_SAVE'})
    item_name: bpy.props.StringProperty(name='Button name', options={'SKIP_SAVE'})
    item_kind: bpy.props.EnumProperty(name='Action', items=(
        ('empty', 'Empty slot', ''), ('command', 'Blender command', ''),
        ('shortcut', 'Keyboard shortcut', 'Run the command assigned to a single key combination in the current Blender context'),
        ('submenu', 'Open another menu', ''),
    ), options={'SKIP_SAVE'})
    item_action: bpy.props.StringProperty(name='Command',
                                        description='Operator name: mesh.bevel or bpy.ops.mesh.bevel. Set arguments in Parameters JSON',
                                        options={'SKIP_SAVE'})
    item_parameters: bpy.props.StringProperty(name='JSON parameters', default='{}',
                                            options={'SKIP_SAVE'})
    item_category: bpy.props.EnumProperty(name='Marker category', items=CATEGORY_ITEMS,
                                         default='auto', options={'SKIP_SAVE'})
    marker_mode: bpy.props.EnumProperty(name='Label', items=MARKER_ITEMS, default='existing', options={'SKIP_SAVE'})
    palette_choice: bpy.props.EnumProperty(name='Existing label', items=palette_choices,
                                          update=palette_selection_changed, options={'SKIP_SAVE'})
    marker_name: bpy.props.StringProperty(name='Label name', options={'SKIP_SAVE'})
    assigned_marker: bpy.props.StringProperty(default='none', options={'HIDDEN', 'SKIP_SAVE'})
    assign_label: bpy.props.BoolProperty(name='Assign label', update=label_action('assign_label'), options={'SKIP_SAVE'})
    remove_label: bpy.props.BoolProperty(name='Clear label', update=label_action('remove_label'), options={'SKIP_SAVE'})
    save_label: bpy.props.BoolProperty(name='Save label', update=label_action('save_label'), options={'SKIP_SAVE'})
    update_label: bpy.props.BoolProperty(name='Update label', update=label_action('update_label'), description='Save label name and color on all assigned buttons', options={'SKIP_SAVE'})
    delete_label: bpy.props.BoolProperty(name='Delete label', update=label_action('delete_label'), description='Delete this label and clear it from all buttons', options={'SKIP_SAVE'})
    marker_color: bpy.props.FloatVectorProperty(name='Label color', subtype='COLOR_GAMMA', size=3,
                                               min=0, max=1, default=(0.412, 0.749, 0.686), options={'SKIP_SAVE'})
    target_menu: bpy.props.EnumProperty(name='Submenu', items=menu_choices,
                                       options={'SKIP_SAVE'})
    move_target: bpy.props.EnumProperty(name='Destination', items=SLOT_ITEMS,
                                       options={'SKIP_SAVE'})
    new_menu: bpy.props.BoolProperty(name='New menu', update=editor_action('new_menu'),
                                    options={'SKIP_SAVE'})
    rename_menu: bpy.props.BoolProperty(name='Rename', update=editor_action('rename_menu'),
                                       options={'SKIP_SAVE'})
    remove_menu: bpy.props.BoolProperty(name='Delete menu', update=editor_action('remove_menu'),
                                       options={'SKIP_SAVE'})
    apply_item: bpy.props.BoolProperty(name='Save button', update=editor_action('apply_item'),
                                      options={'SKIP_SAVE'})
    remove_item: bpy.props.BoolProperty(name='Clear slot', update=editor_action('remove_item'),
                                       options={'SKIP_SAVE'})
    move_item: bpy.props.BoolProperty(name='Move / Swap', update=editor_action('move_item'),
                                     options={'SKIP_SAVE'})
    start_move: bpy.props.BoolProperty(name='Move button', update=editor_action('start_move'),
                                      description='Choose a destination on the diagram; occupied slots swap buttons',
                                      options={'SKIP_SAVE'})
    cancel_move: bpy.props.BoolProperty(name='Cancel move', update=editor_action('cancel_move'),
                                       options={'SKIP_SAVE'})
    choosing_destination: bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    move_source: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    hotkey_enabled: bpy.props.BoolProperty(name='Enable hotkey', options={'SKIP_SAVE'})
    hotkey_type: bpy.props.EnumProperty(name='Key', items=HOTKEY_ITEMS, default='F8', options={'SKIP_SAVE'})
    hotkey_ctrl: bpy.props.BoolProperty(name='Ctrl', options={'SKIP_SAVE'})
    hotkey_shift: bpy.props.BoolProperty(name='Shift', options={'SKIP_SAVE'})
    hotkey_alt: bpy.props.BoolProperty(name='Alt', options={'SKIP_SAVE'})
    hotkey_oskey: bpy.props.BoolProperty(name='Win', options={'SKIP_SAVE'})
    save_hotkey: bpy.props.BoolProperty(name='Save hotkey', update=editor_action('save_hotkey'), options={'SKIP_SAVE'})
    clear_hotkey: bpy.props.BoolProperty(name='Clear hotkey', update=editor_action('clear_hotkey'),
                                        description='Remove the shortcut from this menu', options={'SKIP_SAVE'})
    show_hotkey: bpy.props.BoolProperty(name='Hotkey', default=False, options={'SKIP_SAVE'})
    show_labels: bpy.props.BoolProperty(name='Labels', default=False, options={'SKIP_SAVE'})
    show_parameters: bpy.props.BoolProperty(name='Parameters', default=False, options={'SKIP_SAVE'})

    def invoke(self, context, event):
        try:
            refresh_library()
        except (OSError, ValueError, TypeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self._loading = True
        self.choosing_destination = False
        self.move_source = ''
        self.show_hotkey = self.show_labels = self.show_parameters = False
        self._document = clone_library(LIBRARY)
        self._message = 'Use the save buttons to apply your changes.'
        self.menu_choice = preferred_menu(LIBRARY)
        self.slot = 'RADIAL_0'
        self.move_target = 'RADIAL_0'
        self.load_fields()
        return context.window_manager.invoke_props_dialog(self, width=1060,
                                                         confirm_text='Try menu')

    def load_fields(self):
        previous_label = getattr(self, 'palette_choice', '__none__')
        self._loading = True
        menu = self._document.menus[self.menu_choice]
        self.menu_name = menu.name
        hotkey = menu.hotkey or {'type': 'F8'}
        self.hotkey_enabled = menu.hotkey is not None
        self.hotkey_type = hotkey['type']
        for modifier in ('ctrl', 'shift', 'alt', 'oskey'):
            setattr(self, 'hotkey_' + modifier, hotkey.get(modifier, False))
        draft = hotkey_draft(self)
        if draft is not None:
            draft.type = hotkey['type'] if menu.hotkey is not None else 'NONE'
            for modifier in ('ctrl', 'shift', 'alt', 'oskey'):
                setattr(draft, modifier, hotkey.get(modifier, False))
        slots, index = menu_slot(self._document, self.menu_choice, self.slot)
        item = slots[index]
        self.item_name = item.label if item else ''
        self.item_kind = ('submenu' if item and item.action == 'submenu' else
                          'shortcut' if item and item.action == 'shortcut' else 'command' if item else 'empty')
        self.item_action = item.action if item else ''
        self.item_parameters = json.dumps(item.properties if item else {}, ensure_ascii=False)
        state = OPERATOR_STATES.get(operator_state_key(self), {}) if isinstance(self, bpy.types.Operator) else {}
        if self.item_kind == 'shortcut' or 'shortcut_draft' in state:
            event = shortcut_draft(self)
            if event is not None:
                values = item.properties if self.item_kind == 'shortcut' else {}
                event.type = values.get('type', 'NONE')
                for field in ('ctrl', 'shift', 'alt', 'oskey'):
                    setattr(event, field, values.get(field, False))
        self.item_category = item.category if item else 'auto'
        color = item.marker_color if item else ''
        self.marker_mode = 'existing'
        self.assigned_marker = color or 'none'
        self.palette_choice = (color if color in self._document.palette else
                               previous_label if previous_label in self._document.palette else
                               first_palette_color(self._document))
        self.marker_color = palette_rgb(self.palette_choice)
        self.marker_name = self._document.palette.get(self.palette_choice, '')
        self.target_menu = item.target_menu if item and item.target_menu else next(
            (key for key in self._document.menus if key != self.menu_choice), self.menu_choice
        )
        remember_menu(self.menu_choice, self._document)
        self._loading = False

    def perform(self, action):
        if action == 'start_move':
            slots, index = menu_slot(self._document, self.menu_choice, self.slot)
            if slots[index] is None:
                return
            self.move_source = self.slot
            self.choosing_destination = True
            self._message = 'Choose a destination on the diagram. Occupied slots swap buttons.'
            return
        if action == 'cancel_move':
            self.choosing_destination = False
            self.move_source = ''
            self._message = 'Move cancelled. No buttons were changed.'
            return
        candidate = clone_library(self._document)
        selected_menu = self.menu_choice
        displaced = []
        try:
            menu = candidate.menus[selected_menu]
            slots, index = menu_slot(candidate, selected_menu, self.slot)
            if action == 'new_menu':
                names = {item.name for item in candidate.menus.values()}
                name = 'New menu'
                number = 2
                while name in names:
                    name = f'New menu {number}'
                    number += 1
                selected_menu = create_menu(candidate, name)
            elif action == 'rename_menu':
                if not self.menu_name.strip():
                    raise ValueError('Enter a menu name')
                menu.name = self.menu_name.strip()
            elif action == 'remove_menu':
                delete_menu(candidate, selected_menu)
                selected_menu = candidate.first_menu
            elif action == 'save_hotkey':
                displaced = assign_hotkey(candidate, selected_menu, draft_hotkey_value(self))
            elif action == 'clear_hotkey':
                menu.hotkey = None
            elif action == 'remove_item':
                slots[index] = None
            elif action == 'move_item':
                move_item(candidate, selected_menu, self.slot, self.move_target)
            elif action == 'apply_item':
                if self.item_kind == 'empty':
                    slots[index] = None
                else:
                    name = self.item_name.strip()
                    shortcut = shortcut_value(self) if self.item_kind == 'shortcut' else None
                    if self.item_kind == 'shortcut' and not name:
                        name = hotkey_text(shortcut)
                    if self.item_kind == 'submenu' and not name:
                        name = candidate.menus[self.target_menu].name
                    if not name:
                        raise ValueError('Enter a button name')
                    if self.item_kind == 'shortcut':
                        slots[index] = Item(name, 'shortcut', True, shortcut,
                                            category=self.item_category,
                                            marker_color=slots[index].marker_color if slots[index] else 'none')
                    elif self.item_kind == 'submenu':
                        slots[index] = Item(name, 'submenu',
                                           category=self.item_category, target_menu=self.target_menu,
                                           marker_color=slots[index].marker_color if slots[index] else 'none')
                    else:
                        values = json.loads(self.item_parameters)
                        command = normalize_command_identifier(self.item_action)
                        if command not in {'back', 'origins', 'overlays', 'pivot_median', 'pivot_cursor'}:
                            namespace, operator_name = command.split('.', 1)
                            getattr(getattr(bpy.ops, namespace), operator_name).get_rna_type()
                        slots[index] = Item(name, command, True,
                                           values, self.item_category, marker_color=slots[index].marker_color if slots[index] else 'none')
            save_library(candidate)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as error:
            self._message = str(error)
            self.report({'WARNING'}, self._message)
            return
        self._document = clone_library(LIBRARY)
        self._loading = True
        self.menu_choice = selected_menu
        label_draft = (self.marker_mode, self.palette_choice, self.marker_name, tuple(self.marker_color))
        if action == 'move_item':
            self.slot = self.move_target
            self.choosing_destination = False
            self.move_source = ''
        self.load_fields()
        if action == 'apply_item':
            self._loading = True
            self.marker_mode, self.palette_choice, self.marker_name, self.marker_color = label_draft
            self._loading = False
        self._message = 'Saved. Menus are saved automatically.'
        if displaced:
            names = ', '.join(candidate.menus[key].name for key in displaced)
            self._message = f'Hotkey reassigned from {names}.'

    def draw(self, context):
        layout = self.layout
        split = layout.split(factor=0.22)
        menus_column = split.column()
        menus_column.enabled = not self.choosing_destination
        menus_column.label(text='Menus')
        for key, menu in self._document.menus.items():
            menus_column.prop_enum(self, 'menu_choice', key, text=menu.name)
        menus_column.separator()
        menus_column.prop(self, 'new_menu', toggle=True, icon='ADD')
        menus_column.prop(self, 'menu_name', text='')
        menus_column.prop(self, 'rename_menu', toggle=True, icon='GREASEPENCIL')
        menus_column.separator()
        selected_menu = self._document.menus[self.menu_choice]
        hotkey_section = draw_collapsible(menus_column, self, 'show_hotkey', 'Hotkey',
                                          hotkey_text(selected_menu.hotkey) if selected_menu.hotkey else 'None')
        if hotkey_section is not None:
            draft = hotkey_draft(self)
            if draft is not None:
                hotkey_section.prop(draft, 'type', text='', full_event=True)
            hotkey_section.label(text='Click the shortcut, then press keys.')
            hotkey_section.prop(self, 'save_hotkey', toggle=True, icon='FILE_TICK')
            clear_key = hotkey_section.row()
            clear_key.enabled = selected_menu.hotkey is not None or (draft is not None and draft.type != 'NONE')
            clear_key.prop(self, 'clear_hotkey', toggle=True, icon='X')
        menus_column.separator()
        remove = menus_column.column()
        remove.enabled = len(self._document.menus) > 1
        remove.prop(self, 'remove_menu', toggle=True, icon='TRASH')
        menus_column.label(text='Deleting a menu also')
        menus_column.label(text='clears links to it.')

        content = split.split(factor=0.62)
        diagram = content.column()
        draw_slot_grid(diagram, self, self._document, self.menu_choice)
        details = content.column()
        details.label(text='Selected button')
        if self.choosing_destination:
            slots, index = menu_slot(self._document, self.menu_choice, self.move_source)
            details.label(text=slots[index].label, icon='FORWARD')
            details.label(text='Choose a destination')
            details.label(text='on the diagram.')
            details.separator()
            details.label(text='Occupied slots swap buttons.')
            details.prop(self, 'cancel_move', toggle=True, icon='X')
            layout.separator()
            layout.label(text=self._message, icon='INFO')
            return
        details.prop(self, 'item_kind', text='')
        if self.item_kind != 'empty':
            details.prop(self, 'item_name', text='')
            if self.item_kind == 'submenu':
                details.prop(self, 'target_menu', text='')
            elif self.item_kind == 'shortcut':
                event = shortcut_draft(self)
                if event is not None:
                    details.prop(event, 'type', text='', full_event=True)
                    details.label(text='Click the field, then press a key combination.')
                    if event.type != 'NONE':
                        try:
                            source = shortcut_command(context, shortcut_value(self))
                        except ValueError:
                            details.label(text='Choose a keyboard key', icon='INFO')
                        else:
                            if source is None:
                                details.label(text='No available command in this context', icon='INFO')
                            else:
                                namespace, name = source.idname.split('.', 1)
                                details.label(text='Command: ' + getattr(getattr(bpy.ops, namespace), name).get_rna_type().name)
            else:
                details.prop(self, 'item_action', text='', placeholder='mesh.bevel or bpy.ops.mesh.bevel')
                if self.item_action == 'wm.context_toggle':
                    try:
                        data_path = json.loads(self.item_parameters).get('data_path')
                    except (ValueError, AttributeError):
                        data_path = None
                    details.label(text='Target: ' + binding_description(data_path))
                parameters = draw_collapsible(details, self, 'show_parameters', 'Parameters')
                if parameters is not None:
                    parameters.prop(self, 'item_parameters', text='')
            assigned = self._document.palette.get(self.assigned_marker, 'None')
            label_controls = draw_collapsible(details, self, 'show_labels', 'Labels', assigned,
                                              label_icon(self.assigned_marker))
            if label_controls is not None:
                draw_marker_fields(label_controls, self, show_header=False)
        details.separator()
        slots, index = menu_slot(self._document, self.menu_choice, self.slot)
        button_actions = details.box()
        button_actions.label(text='Button actions')
        actions = button_actions.column(align=False)
        for action_index, (property_name, icon) in enumerate((
            ('apply_item', 'FILE_TICK'), ('remove_item', 'X'), ('start_move', 'FORWARD'),
        )):
            if action_index:
                actions.separator(factor=0.35)
            action = actions.row()
            action.enabled = property_name == 'apply_item' or slots[index] is not None
            action.prop(self, property_name, toggle=True, icon=icon)
        layout.separator()
        layout.label(text=self._message, icon='INFO')

    def execute(self, context):
        discard_hotkey_draft(self)
        window, area = context.window, context.area
        if area is None or area.type != 'VIEW_3D':
            self.report({'INFO'}, 'Menu saved. Open Menu Editor in the 3D Viewport to try it.')
            return {'FINISHED'}
        menu_id = self.menu_choice

        def preview():
            if not any(current == area for current in window.screen.areas):
                return None
            region = next((region for region in area.regions if region.type == 'WINDOW'), None)
            if region:
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.view3d.pie_prototype('INVOKE_DEFAULT', menu_id=menu_id)
            return None

        bpy.app.timers.register(preview, first_interval=0.1)
        OPERATOR_STATES.pop(operator_state_key(self), None)
        return {'FINISHED'}


class VIEW3D_PT_pie_menus(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PieCompose'
    bl_label = 'PieCompose'

    def draw(self, context):
        self.layout.operator('wm.pie_editor', text='Menu Editor', icon='PREFERENCES')
        self.layout.operator('wm.pie_import_configuration', text='Import configuration', icon='IMPORT')
        self.layout.operator('wm.pie_export_configuration', text='Export configuration', icon='EXPORT')


class WM_OT_pie_export_configuration(bpy.types.Operator, ExportHelper):
    bl_idname = 'wm.pie_export_configuration'
    bl_label = 'PieCompose: Export Configuration'
    bl_description = 'Export all menus, commands, submenu links, labels and hotkeys to JSON'
    filename_ext = '.json'
    filepath: bpy.props.StringProperty(default='pie-configuration.json', subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.json', options={'HIDDEN'})

    def execute(self, context):
        try:
            refresh_library()
            if Path(self.filepath).resolve() in {STORE.path.resolve(), STYLE_PATH.resolve()}:
                raise ValueError('Choose a destination outside the active settings files')
            write_json_atomic(self.filepath, LIBRARY.to_document())
        except (OSError, ValueError, TypeError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Configuration exported.')
        return {'FINISHED'}


class WM_OT_pie_import_configuration(bpy.types.Operator):
    bl_idname = 'wm.pie_import_configuration'
    bl_label = 'PieCompose: Import Configuration'
    bl_description = 'Replace the menu library from JSON; a backup is saved before importing'
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.json', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            candidate = library_from_document(json.loads(Path(self.filepath).read_text(encoding='utf-8-sig')))
            supported = {item[0] for item in HOTKEY_ITEMS}
            if any(menu.hotkey and menu.hotkey['type'] not in supported for menu in candidate.menus.values()):
                raise ValueError('The file contains a key unsupported by this Blender version')
            refresh_library()
            backup = STORE.path.with_name(f'{STORE.path.stem}.before-import-{uuid4().hex}.json')
            write_json_atomic(backup, LIBRARY.to_document())
            candidate.revision = LIBRARY.revision
            save_library(candidate)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Configuration imported. Backup: {backup.name}')
        return {'FINISHED'}


class PieDockPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    def draw(self, context):
        layout = self.layout
        layout.label(text='Open the editor in the 3D Viewport: N > PieCompose > Menu Editor')
        layout.label(text='Configuration is kept outside the add-on and survives updates.')
        layout.label(text=str(STORE.path), icon='FILE_FOLDER')
        layout.operator('wm.pie_import_configuration', text='Import configuration', icon='IMPORT')
        layout.operator('wm.pie_export_configuration', text='Export configuration', icon='EXPORT')


CLASSES = (PieDockPreferences, VIEW3D_OT_pie_prototype, WM_OT_pie_capture, WM_OT_pie_editor,
           WM_OT_pie_import_configuration,
           WM_OT_pie_export_configuration, VIEW3D_PT_pie_menus)


def register():
    global FONT_ID, KEYMAPS_READY
    if hasattr(bpy.types, 'WM_OT_pie_editor'):
        raise RuntimeError('Close the other PieCompose instance before enabling this extension.')
    if STYLE_PATH.exists():
        try:
            load_style()
        except (OSError, ValueError, TypeError) as error:
            print(f'PieCompose: could not load style; using current settings: {error}')
    try:
        if STORE.path.exists():
            refresh_library()
        else:
            save_library(clone_library(LIBRARY))
    except (OSError, ValueError, TypeError, StorageConflict) as error:
        raise RuntimeError(
            f'PieCompose could not load configuration at {STORE.path}. '
            'The existing file has not been reset. ' + str(error)
        ) from error
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.UI_MT_button_context_menu.append(draw_button_context)
    KEYMAPS_READY = True
    sync_keymaps()


def unregister():
    global KEYMAPS_READY, KEYMAP_SIGNATURE, LABEL_PREVIEWS
    KEYMAPS_READY = False
    KEYMAP_SIGNATURE = None
    if VIEW3D_OT_pie_prototype.active is not None:
        VIEW3D_OT_pie_prototype.active.cancel(bpy.context)
    for keymap, item in KEYMAPS:
        keymap.keymap_items.remove(item)
    KEYMAPS.clear()
    for state in list(OPERATOR_STATES.values()):
        owner = state.get('owner')
        if owner is not None:
            discard_hotkey_draft(owner)
    bpy.types.UI_MT_button_context_menu.remove(draw_button_context)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    OPERATOR_STATES.clear()
    SLOT_ENUM_CACHE.clear()
    PALETTE_ENUM_CACHE.clear()
    if LABEL_PREVIEWS is not None:
        bpy.utils.previews.remove(LABEL_PREVIEWS)
        LABEL_PREVIEWS = None


