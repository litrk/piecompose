"""Path parsing and target validation without a running Blender process."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from piecompose.property_bindings import path_steps, resolve_boolean


class BindingPathTests(unittest.TestCase):
    def test_collection_keys_are_data_not_expressions(self):
        path = 'active_object.modifiers["quoted \\\" name"].show_viewport'
        self.assertEqual(path_steps(path)[-2:], [('item', 'quoted " name'), ('attr', 'show_viewport')])
        for path in ('active_object.__class__', 'active_object.get("x")',
                     '__import__("os")', 'scene.objects[active_object.name].hide_render',
                     'active_object.show_in_front; invalid', 'unrelated.flag'):
            with self.assertRaises((ValueError, SyntaxError)):
                path_steps(path)

    def test_missing_readonly_and_non_boolean_targets(self):
        prop = SimpleNamespace(type='BOOLEAN', is_array=False, is_readonly=False)
        obj = SimpleNamespace(show_in_front=False, bl_rna=SimpleNamespace(properties={'show_in_front': prop}),
                              is_property_readonly=lambda name: False)
        context = SimpleNamespace(active_object=obj)
        self.assertFalse(resolve_boolean(context, 'active_object.show_in_front', writable=True).value)
        prop.is_readonly = True
        self.assertIsNone(resolve_boolean(context, 'active_object.show_in_front', writable=True))
        self.assertFalse(resolve_boolean(context, 'active_object.show_in_front').value)
        prop.is_readonly = False
        obj.show_in_front = 1
        self.assertIsNone(resolve_boolean(context, 'active_object.show_in_front'))
        context.active_object = None
        self.assertIsNone(resolve_boolean(context, 'active_object.show_in_front', writable=True))

    def test_boolean_custom_property_keys(self):
        obj = {'flag "quoted"': True, 'number': 1}
        context = SimpleNamespace(active_object=obj)
        self.assertTrue(resolve_boolean(context, 'active_object[\'flag "quoted"\']').value)
        self.assertIsNone(resolve_boolean(context, 'active_object["number"]'))


if __name__ == '__main__':
    unittest.main()
