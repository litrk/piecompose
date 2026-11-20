"""Resolve a single key chord through Blender's current user key configuration."""
from .pie_data import normalize_hotkey


MODE_KEYMAPS = {
    'OBJECT': ('Object Mode',), 'EDIT_MESH': ('Mesh',),
    'EDIT_CURVE': ('Curve',), 'EDIT_SURFACE': ('Curve',),
    'EDIT_CURVES': ('Curves',), 'EDIT_ARMATURE': ('Armature',),
    'EDIT_METABALL': ('Metaball',), 'EDIT_LATTICE': ('Lattice',),
    'EDIT_TEXT': ('Font',), 'POSE': ('Pose',), 'SCULPT': ('Sculpt',),
    'PAINT_VERTEX': ('Vertex Paint',), 'PAINT_WEIGHT': ('Weight Paint',),
    'PAINT_TEXTURE': ('Image Paint',), 'PARTICLE': ('Particle',),
    'SCULPT_CURVES': ('Sculpt Curves',),
}


def matches(item, shortcut):
    if not item.active or item.type != shortcut['type'] or item.value not in {'PRESS', 'ANY'}:
        return False
    if item.key_modifier != 'NONE':
        return False
    if item.any:
        return True
    return all(getattr(item, field) == -1 or bool(getattr(item, field)) == shortcut.get(field, False)
               for field in ('ctrl', 'shift', 'alt', 'oskey'))


def context_keymaps(context):
    if context.area is None or context.area.type != 'VIEW_3D':
        return
    maps = context.window_manager.keyconfigs.user.keymaps
    yielded = set()
    # Follow Blender's active-tool map before the mode/viewport handlers.
    try:
        from bl_ui.space_toolsystem_common import ToolSelectPanelHelper, _keymap_from_item
        cls = ToolSelectPanelHelper._tool_class_from_space_type('VIEW_3D')
        tool, _, _ = cls._tool_get_active(context, 'VIEW_3D', context.mode)
        tool_map = _keymap_from_item(context, tool) if tool is not None else None
        if tool_map is not None and not tool_map.is_modal:
            yielded.add(tool_map.name)
            yield tool_map
    except (ImportError, AttributeError, KeyError, TypeError, RuntimeError):
        pass
    names = (*MODE_KEYMAPS.get(context.mode, ()), 'Object Non-modal',
             '3D View', '3D View Generic', 'Screen', 'Window')
    for name in names:
        keymap = maps.get(name)
        if keymap is not None and name not in yielded and not keymap.is_modal:
            yielded.add(name)
            yield keymap


def resolve_shortcut(context, value, operator_available):
    shortcut = normalize_hotkey(value)
    if shortcut is None:
        return None
    for keymap in context_keymaps(context):
        for item in keymap.keymap_items:
            if matches(item, shortcut) and operator_available(item.idname):
                return item
    return None
