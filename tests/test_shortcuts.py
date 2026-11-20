from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from piecompose.shortcuts import matches, resolve_shortcut


def binding(identifier, **overrides):
    fields = dict(idname=identifier, type='B', value='PRESS', ctrl=1, shift=0,
                  alt=0, oskey=0, any=False, active=True, key_modifier='NONE')
    fields.update(overrides)
    return SimpleNamespace(**fields)


class ShortcutTests(unittest.TestCase):
    def test_chord_matching_modifiers_and_disabled_events(self):
        key = {'type': 'B', 'ctrl': True}
        self.assertTrue(matches(binding('mesh.bevel'), key))
        self.assertTrue(matches(binding('mesh.bevel', shift=-1), key))
        self.assertTrue(matches(binding('mesh.bevel', any=True), {'type': 'B'}))
        for changes in ({'active': False}, {'type': 'C'}, {'value': 'RELEASE'},
                        {'shift': 1}, {'ctrl': 0}, {'key_modifier': 'D'}):
            self.assertFalse(matches(binding('mesh.bevel', **changes), key))

    def test_mode_priority_poll_and_live_keymap_changes(self):
        mesh = binding('mesh.bevel')
        viewport = binding('view3d.render_border')
        maps = {'Mesh': SimpleNamespace(name='Mesh', is_modal=False, keymap_items=[mesh]),
                '3D View': SimpleNamespace(name='3D View', is_modal=False, keymap_items=[viewport])}
        context = SimpleNamespace(area=SimpleNamespace(type='VIEW_3D'), mode='EDIT_MESH',
                                  window_manager=SimpleNamespace(keyconfigs=SimpleNamespace(
                                      user=SimpleNamespace(keymaps=maps))))
        chord = {'type': 'B', 'ctrl': True}
        self.assertIs(resolve_shortcut(context, chord, lambda name: True), mesh)
        context.mode = 'OBJECT'
        self.assertIs(resolve_shortcut(context, chord, lambda name: True), viewport)
        context.mode = 'EDIT_MESH'
        mesh.active = False
        new = binding('mesh.subdivide')
        maps['Mesh'].keymap_items.append(new)
        self.assertIs(resolve_shortcut(context, chord, lambda name: True), new)
        self.assertIs(resolve_shortcut(context, chord, lambda name: name.startswith('view3d.')), viewport)
        self.assertIsNone(resolve_shortcut(context, chord, lambda name: False))


if __name__ == '__main__':
    unittest.main()
