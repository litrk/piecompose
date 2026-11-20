"""Context-relative RNA property bindings; never evaluate a saved expression."""
import ast
from collections import deque
from dataclasses import dataclass


# These are semantic targets, not lists of supported checkbox identifiers.
# More specific roots precede their containing datablocks.
CAPTURE_ROOTS = (
    'active_object.active_material.node_tree', 'active_object.active_material',
    'active_object.data', 'active_pose_bone', 'active_bone', 'active_object',
    'scene.world.node_tree', 'scene.world', 'scene', 'view_layer', 'space_data',
    'preferences',
)
ROOT_NAMES = {path.split('.')[0] for path in CAPTURE_ROOTS} | {'tool_settings', 'object'}


def path_steps(path):
    if not isinstance(path, str) or not path or len(path) > 4096:
        raise ValueError('Invalid property path')
    node = ast.parse(path, mode='eval').body

    def visit(value):
        if isinstance(value, ast.Name):
            return [('attr', value.id)]
        if isinstance(value, ast.Attribute):
            return visit(value.value) + [('attr', value.attr)]
        if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Constant):
            key = value.slice.value
            if type(key) in {str, int}:
                return visit(value.value) + [('item', key)]
        raise ValueError('Only property names and collection keys are allowed')

    steps = visit(node)
    if len(steps) > 32 or steps[0][1] not in ROOT_NAMES:
        raise ValueError('Unsupported property context')
    if any(kind == 'attr' and (not key.isidentifier() or key.startswith('_')) for kind, key in steps):
        raise ValueError('Invalid property name')
    return steps


def follow(owner, steps):
    for kind, key in steps:
        owner = getattr(owner, key) if kind == 'attr' else owner[key]
        if owner is None:
            raise ValueError('Property target is unavailable')
    return owner


@dataclass
class BooleanTarget:
    owner: object
    kind: str
    key: object

    @property
    def value(self):
        return getattr(self.owner, self.key) if self.kind == 'attr' else self.owner[self.key]


def resolve_boolean(context, path, writable=False):
    try:
        steps = path_steps(path)
        owner = follow(context, steps[:-1])
        kind, key = steps[-1]
        target = BooleanTarget(owner, kind, key)
        if type(target.value) is not bool:
            return None
        if kind == 'attr':
            prop = owner.bl_rna.properties.get(key)
            if prop is None or prop.type != 'BOOLEAN' or prop.is_array:
                return None
            if writable and (prop.is_readonly or owner.is_property_readonly(key)):
                return None
        elif writable:
            data = getattr(owner, 'id_data', None)
            if data is not None and not getattr(data, 'is_editable', True):
                return None
        return target
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, SyntaxError, ReferenceError, RecursionError, RuntimeError):
        return None


def relative_path(root, source):
    if root == source:
        return ''
    if getattr(root, 'id_data', None) != getattr(source, 'id_data', None):
        return None
    try:
        base = '' if root == root.id_data else root.path_from_id()
        full = '' if source == source.id_data else source.path_from_id()
    except (AttributeError, TypeError, ValueError):
        return None
    if not base:
        return full
    if full.startswith(base + '.') or full.startswith(base + '['):
        return full[len(base):].lstrip('.')
    return None


def find_owner_path(context, source):
    roots = []
    for root_path in CAPTURE_ROOTS:
        if root_path == 'space_data' and getattr(getattr(context, 'space_data', None), 'type', None) != 'VIEW_3D':
            continue
        try:
            root = follow(context, path_steps(root_path))
        except (AttributeError, KeyError, TypeError, ValueError, ReferenceError, RuntimeError):
            continue
        roots.append((root_path, root))
        suffix = relative_path(root, source)
        if suffix is not None:
            return root_path + ('' if not suffix else ('' if suffix.startswith('[') else '.') + suffix)
    for root_path, root in roots:
        # Standard ID-backed RNA exposes a path directly, including collection
        # members. For preferences and pointers into another ID, inspect the
        # pointer graph, never enumerate collections or bind to named datablocks.
        pending = deque([(root_path, root, 0)])
        visited = set()
        while pending and len(visited) < 256:
            path, owner, depth = pending.popleft()
            # Embedded RNA structures can share an address with their parent.
            identity = (owner.bl_rna.identifier, owner.as_pointer())
            if identity in visited:
                continue
            visited.add(identity)
            suffix = relative_path(owner, source)
            if suffix is not None:
                return path + ('' if not suffix else ('' if suffix.startswith('[') else '.') + suffix)
            if depth >= 4:
                continue
            for prop in owner.bl_rna.properties:
                name = prop.identifier
                if prop.type not in {'POINTER', 'COLLECTION'} or name in {'rna_type', 'id_data', 'original'} or name.startswith('_'):
                    continue
                try:
                    child = getattr(owner, name)
                    if prop.type == 'COLLECTION':
                        if not hasattr(child, 'active'):
                            continue
                        active = child.active
                        if active is not None and not hasattr(active, 'bl_rna'):
                            continue
                        source_name = getattr(source, 'name', None)
                        if source_name is not None and child.get(source_name) == source:
                            return path + '.' + name + '.active'
                        child = active
                        name += '.active'
                    if child is not None and hasattr(child, 'bl_rna'):
                        pending.append((path + '.' + name, child, depth + 1))
                except (AttributeError, TypeError, ValueError, ReferenceError, RuntimeError):
                    continue
    return None


def capture_boolean_path(context, source, prop):
    if prop.type != 'BOOLEAN' or prop.is_array or prop.is_readonly:
        raise ValueError('Choose an editable single checkbox')
    owner_path = find_owner_path(context, source)
    if owner_path is None:
        raise ValueError('This checkbox has no binding to the active context')
    # RNA can describe custom Boolean properties with an item key rather than
    # an attribute. Keep collection/custom-property keys escaped as Python
    # string literals, but resolution itself uses no eval or exec.
    name = prop.identifier
    if source.bl_rna.properties.get(name) is not None:
        path = owner_path + '.' + name
    else:
        path = owner_path + '[' + repr(name) + ']'
    # Collections with an active member (modifiers, constraints, nodes, bones,
    # etc.) follow that member instead of pinning its captured name or index.
    steps = path_steps(path)
    owner, normalized = context, ''
    for kind, key in steps:
        if (kind == 'item' and hasattr(owner, 'active')
                and (owner.active is None or hasattr(owner.active, 'bl_rna'))):
            normalized += '.active'
            owner = owner.active
        else:
            if kind == 'attr':
                normalized += ('.' if normalized else '') + key
            else:
                normalized += '[' + repr(key) + ']'
            owner = getattr(owner, key) if kind == 'attr' else owner[key]
        if owner is None:
            raise ValueError('Select an active target before capturing this checkbox')
    path = normalized
    if resolve_boolean(context, path, writable=True) is None:
        raise ValueError('This checkbox is unavailable or read-only in the active context')
    return path


def binding_description(path):
    if not isinstance(path, str):
        return 'Current context'
    for fragment, description in (
        ('.modifiers.active', 'Active modifier of the active object'),
        ('.constraints.active', 'Active constraint'), ('.nodes.active', 'Active node'),
        ('active_object.active_material', 'Active material'),
        ('active_object.data', 'Active object data'), ('active_object', 'Active object'),
        ('active_pose_bone', 'Active pose bone'), ('active_bone', 'Active bone'),
        ('scene.world', 'Current world'), ('scene', 'Current scene'),
        ('view_layer', 'Current view layer'), ('space_data', 'Current viewport'),
        ('preferences', 'Blender preferences'),
    ):
        matches = fragment in path if fragment.startswith('.') else (
            path == fragment or path.startswith(fragment + '.') or path.startswith(fragment + '['))
        if matches:
            return description
    return 'Current context'
