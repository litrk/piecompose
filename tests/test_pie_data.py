import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pie_data import (
    Item, MenuLibrary, MenuStore, PieMenu, StorageConflict, create_menu,
    delete_menu, library_from_document, move_item, add_palette_color, delete_palette_color, update_palette_color, assign_hotkey,
    normalize_command_identifier,
)


class MenuStorageTests(unittest.TestCase):
    def test_shortcut_action_roundtrip_and_invalid_event(self):
        self.library.menus['main'].groups['RADIAL'][0] = Item(
            'Ctrl+B', 'shortcut', properties={'type': 'B', 'ctrl': True})
        self.store.save(self.library)
        item = self.store.load().menus['main'].groups['RADIAL'][0]
        self.assertEqual(item.action, 'shortcut')
        self.assertEqual(item.properties, {'type': 'B', 'ctrl': True, 'shift': False, 'alt': False, 'oskey': False})
        before = self.store.path.read_bytes()
        self.library.menus['main'].groups['RADIAL'][0] = Item('Bad', 'shortcut', properties={'type': 'GG'})
        with self.assertRaises(ValueError):
            self.store.save(self.library)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_operator_input_normalization_and_rejection(self):
        for value in ('mesh.bevel', 'bpy.ops.mesh.bevel', 'mesh.bevel()', ' bpy.ops.mesh.bevel( ) '):
            self.assertEqual(normalize_command_identifier(value), 'mesh.bevel')
        self.assertEqual(normalize_command_identifier('origins'), 'origins')
        for value in ('', 'mesh', 'bpy.ops.mesh.bevel(offset=1)', 'mesh.bevel; other',
                      '__import__("os")', 'bpy.ops.mesh.bevel.__call__', None):
            with self.assertRaises(ValueError):
                normalize_command_identifier(value)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = MenuStore(Path(self.directory.name) / 'menus.json')
        self.library = MenuLibrary({'main': PieMenu('Главное')})

    def test_round_trip_preserves_parameters_categories_and_empty_sectors(self):
        groups = self.library.menus['main'].groups
        groups['RADIAL'][3] = Item('Сдвиг', 'transform.translate', True,
                                    {'value': [1.25, 2, 3], 'constraint_axis': [True, False, False]},
                                    'transform')
        groups['TOP'][0] = Item('Спереди', 'view3d.view_axis', properties={'type': 'FRONT'})
        groups['TOP'][1] = Item('Сверху', 'view3d.view_axis', properties={'type': 'TOP'})
        self.store.save(self.library)
        restored = self.store.load()
        self.assertEqual(restored.to_document(), self.library.to_document())
        self.assertIsNone(restored.menus['main'].groups['RADIAL'][2])

    def test_named_palette_round_trip_and_duplicate_rules(self):
        color = add_palette_color(self.library, '  Выделение  ', '#FF8000')
        self.assertEqual(color, '#ff8000')
        self.assertEqual(add_palette_color(self.library, 'Another name', '#ff8000'), color)
        self.assertEqual(self.library.palette[color], 'Выделение')
        with self.assertRaises(ValueError):
            add_palette_color(self.library, 'выделение', '#112233')
        with self.assertRaises(ValueError):
            add_palette_color(self.library, ' ', '#112233')
        self.store.save(self.library)
        self.assertEqual(self.store.load().palette, self.library.palette)

    def test_delete_used_label_clears_assignments_and_preserves_commands(self):
        self.library.palette = {'#ff8000': 'Tools'}
        groups = self.library.menus['main'].groups
        groups['RADIAL'][0] = Item('Smooth', 'object.shade_smooth', marker_color='#ff8000')
        child = create_menu(self.library, 'Child')
        self.library.menus[child].groups['BOTTOM'][2] = Item('Move', 'transform.translate', marker_color='#ff8000')
        delete_palette_color(self.library, '#ff8000')
        self.store.save(self.library)
        self.assertEqual(self.store.load().palette, {})
        self.assertEqual(groups['RADIAL'][0], Item('Smooth', 'object.shade_smooth', marker_color='none'))
        self.assertEqual(self.store.load().menus[child].groups['BOTTOM'][2].marker_color, 'none')

    def test_update_label_recolors_all_menus_and_survives_reload(self):
        self.library.palette = {'#ff8000': 'Tools', '#83a9d5': 'View'}
        child = create_menu(self.library, 'Child')
        for menu_id, group, index in [('main', 'RADIAL', 0), ('main', 'TOP', 2), (child, 'BOTTOM', 5)]:
            self.library.menus[menu_id].groups[group][index] = Item(
                'Move', 'transform.translate', True, {'value': [1, 2, 3]}, marker_color='#ff8000')
        self.library.menus['main'].groups['RADIAL'][1] = Item('View', 'view3d.view_selected', marker_color='#83a9d5')
        update_palette_color(self.library, '#ff8000', '  Modeling  ', '#00FF80')
        self.store.save(self.library)
        restored = self.store.load()
        self.assertEqual(restored.palette, {'#00ff80': 'Modeling', '#83a9d5': 'View'})
        for menu_id, group, index in [('main', 'RADIAL', 0), ('main', 'TOP', 2), (child, 'BOTTOM', 5)]:
            item = restored.menus[menu_id].groups[group][index]
            self.assertEqual(item.marker_color, '#00ff80')
            self.assertEqual(item.properties, {'value': [1, 2, 3]})
        self.assertEqual(restored.menus['main'].groups['RADIAL'][1].marker_color, '#83a9d5')

    def test_update_label_rejects_collisions_without_mutation(self):
        self.library.palette = {'#ff8000': 'Tools', '#83a9d5': 'View'}
        before = self.library.to_document()
        for name, color in [('Tools', '#83a9d5'), ('view', '#ff8000'), (' ', '#ff8000'), ('Tools', '#broken')]:
            with self.assertRaises(ValueError):
                update_palette_color(self.library, '#ff8000', name, color)
            self.assertEqual(self.library.to_document(), before)
        update_palette_color(self.library, '#ff8000', 'Renamed', '#ff8000')
        self.assertEqual(self.library.palette['#ff8000'], 'Renamed')

    def test_older_library_gets_palette_without_losing_marks(self):
        document = self.library.to_document()
        document.pop('palette')
        document['menus']['main']['groups']['TOP'][0] = {
            'label': 'Custom', 'action': 'object.shade_smooth', 'marker_color': '#ff8000'}
        restored = library_from_document(document)
        self.assertEqual(restored.palette['#69bfaf'], 'Mint')
        self.assertEqual(restored.menus['main'].groups['TOP'][0].marker_color, '#ff8000')

    def test_invalid_palette_does_not_overwrite_file(self):
        self.store.save(self.library)
        original = self.store.path.read_bytes()
        self.library.palette['#broken'] = 'Broken'
        with self.assertRaises(ValueError):
            self.store.save(self.library)
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_hotkeys_round_trip_and_conflict_validation(self):
        child = create_menu(self.library, 'Tools')
        self.library.menus['main'].hotkey = {'type': 'F8'}
        self.library.menus[child].hotkey = {'type': 'F9', 'ctrl': True}
        self.store.save(self.library)
        restored = self.store.load()
        self.assertEqual(restored.menus['main'].hotkey['type'], 'F8')
        self.assertTrue(restored.menus[child].hotkey['ctrl'])
        original = self.store.path.read_bytes()
        restored.menus[child].hotkey = {'type': 'F8'}
        with self.assertRaises(ValueError):
            self.store.save(restored)
        self.assertEqual(self.store.path.read_bytes(), original)
        restored.menus[child].hotkey = None
        self.store.save(restored)
        self.assertIsNone(self.store.load().menus[child].hotkey)

    def test_legacy_hotkey_and_invalid_modifiers(self):
        document = self.library.to_document()
        document['menus']['main'].pop('hotkey')
        restored = library_from_document(document)
        self.assertEqual(restored.menus['main'].hotkey['type'], 'F8')
        document['menus']['main']['hotkey'] = {'type': 'F8', 'ctrl': 'true'}
        with self.assertRaises(ValueError):
            library_from_document(document)

    def test_reassign_hotkey_moves_binding_without_touching_other_menus(self):
        child = create_menu(self.library, 'Tools')
        other = create_menu(self.library, 'Other')
        assign_hotkey(self.library, 'main', {'type': 'F8', 'ctrl': True})
        assign_hotkey(self.library, other, {'type': 'F9'})
        self.assertEqual(assign_hotkey(self.library, child, {'type': 'F8', 'ctrl': True}), ['main'])
        self.assertIsNone(self.library.menus['main'].hotkey)
        self.assertEqual(self.library.menus[other].hotkey['type'], 'F9')
        self.store.save(self.library)
        restored = self.store.load()
        self.assertIsNone(restored.menus['main'].hotkey)
        self.assertTrue(restored.menus[child].hotkey['ctrl'])
        self.assertEqual(assign_hotkey(self.library, child, {'type': 'F8', 'ctrl': True}), [])

    def test_old_main_menu_metadata_is_not_exported(self):
        child = create_menu(self.library, 'Tools')
        document = self.library.to_document()
        document['rootMenu'] = child
        restored = library_from_document(document)
        self.assertEqual(restored.first_menu, 'main')
        self.assertNotIn('rootMenu', restored.to_document())

    def test_older_short_groups_are_padded_without_moving_items(self):
        document = self.library.to_document()
        document['menus']['main']['groups'] = {'RADIAL': [None, {'label': 'View', 'action': 'view3d.view_all'}]}
        restored = library_from_document(document)
        self.assertEqual(restored.menus['main'].groups['RADIAL'][1].label, 'View')
        self.assertEqual(len(restored.menus['main'].groups['TOP']), 6)
        self.assertEqual(restored.menus['main'].groups['RADIAL'][1].marker_color, '')

    def test_marker_colors_survive_move_and_reload(self):
        groups = self.library.menus['main'].groups
        groups['RADIAL'][0] = Item('Custom', 'object.shade_smooth', marker_color='#e68040')
        groups['TOP'][0] = Item('Hidden', 'object.shade_flat', marker_color='none')
        move_item(self.library, 'main', 'RADIAL_0', 'BOTTOM_5')
        self.store.save(self.library)
        restored = self.store.load().menus['main'].groups
        self.assertEqual(restored['BOTTOM'][5].marker_color, '#e68040')
        self.assertEqual(restored['TOP'][0].marker_color, 'none')
        restored['TOP'][1] = Item('Invalid', 'object.shade_flat', marker_color='#invalid')
        with self.assertRaises(ValueError):
            library_from_document(MenuLibrary({'main': PieMenu('Main', restored)}).to_document())

    def test_move_swaps_an_occupied_destination(self):
        groups = self.library.menus['main'].groups
        groups['RADIAL'][0] = Item('First', 'object.shade_smooth')
        groups['BOTTOM'][5] = Item('Second', 'object.shade_flat')
        move_item(self.library, 'main', 'RADIAL_0', 'BOTTOM_5')
        self.assertEqual(groups['RADIAL'][0].label, 'Second')
        self.assertEqual(groups['BOTTOM'][5].label, 'First')

    def test_delete_clears_links_and_preserves_an_existing_menu(self):
        child = create_menu(self.library, 'Дочернее')
        self.library.menus['main'].groups['RADIAL'][0] = Item('Child', 'submenu', target_menu=child)
        delete_menu(self.library, child)
        self.assertEqual(self.library.first_menu, 'main')
        self.assertIsNone(self.library.menus['main'].groups['RADIAL'][0])
        with self.assertRaises(ValueError):
            delete_menu(self.library, 'main')

    def test_submenu_cycles_are_preserved_as_explicit_navigation(self):
        child = create_menu(self.library)
        self.library.menus['main'].groups['RADIAL'][0] = Item('Child', 'submenu', target_menu=child)
        self.library.menus[child].groups['RADIAL'][0] = Item('Root', 'submenu', target_menu='main')
        self.store.save(self.library)
        self.assertEqual(self.store.load().menus[child].groups['RADIAL'][0].target_menu, 'main')

    def test_stale_writer_cannot_overwrite_another_window(self):
        self.store.save(self.library)
        first, second = self.store.load(), self.store.load()
        first.menus['main'].name = 'Первое окно'
        self.store.save(first)
        second.menus['main'].name = 'Второе окно'
        with self.assertRaises(StorageConflict):
            self.store.save(second)
        self.assertEqual(self.store.load().menus['main'].name, 'Первое окно')

    def test_failed_replace_preserves_file_and_revision(self):
        self.store.save(self.library)
        original = self.store.path.read_bytes()
        revision = self.library.revision
        self.library.menus['main'].name = 'New'
        with patch.object(Path, 'replace', side_effect=OSError('Disk unavailable')):
            with self.assertRaises(OSError):
                self.store.save(self.library)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(self.library.revision, revision)
        self.assertEqual(list(self.store.path.parent.glob('*.tmp')), [])

    def test_invalid_content_and_missing_targets_do_not_overwrite_file(self):
        self.store.save(self.library)
        original = self.store.path.read_bytes()
        self.library.menus['main'].groups['RADIAL'][0] = Item('Missing', 'submenu', target_menu='missing')
        with self.assertRaises(ValueError):
            self.store.save(self.library)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.store.path.write_text('{bad json', encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            self.store.load()


if __name__ == '__main__':
    unittest.main()
