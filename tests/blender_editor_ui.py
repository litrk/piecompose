import os
from pathlib import Path
import runpy
import tempfile
import sys
import bpy
from dataclasses import replace

os.environ["PIE_MENU_DATA_PATH"] = str(Path(tempfile.mkdtemp(prefix="pie-editor-ui-")) / "menus.json")
bpy.context.preferences.view.show_splash = False
demo = runpy.run_path(str(Path(__file__).resolve().parents[1] / "pie_prototype.py"))
runpy.run_path(str(Path(__file__).resolve().with_name('demo_library.py')))['install'](demo)
editor_class = demo["WM_OT_pie_editor"]
original_invoke = editor_class.invoke
original_load_fields = editor_class.load_fields
instances = {}


def observed_load_fields(self):
    original_load_fields(self)
    if '--pie-ui-expanded-preview' in sys.argv and not instances.get('expanded_preview_started'):
        instances['expanded_preview_started'] = True
        self.show_hotkey = self.show_labels = self.show_parameters = True
    if '--pie-ui-move-preview' in sys.argv and not instances.get('move_preview_started'):
        instances['move_preview_started'] = True
        self.start_move = True


editor_class.load_fields = observed_load_fields
def observed_invoke(self, context, event):
    instances["editor"] = self
    return original_invoke(self, context, event)
editor_class.invoke = observed_invoke
demo["register"]()
if '--pie-ui-duplicate-preview' in sys.argv:
    bpy.ops.wm.pie_capture(command='object.duplicate_move', caption='Duplicate Objects', parameters='{}',
                          destination_menu='main', slot='RADIAL_0')
if '--pie-ui-manual' in sys.argv:
    bpy.ops.wm.save_as_mainfile(filepath=str(demo['STORE'].path.parent / 'Pie Editor QA.blend'))
output = Path(__file__).resolve().parents[1] / "design-preview"

def capture():
    bpy.ops.screen.screenshot(filepath=str(output / "blender-menu-editor.png"))
    print("EDITOR_UI_CALLBACKS_PASSED", flush=True)
    if '--pie-ui-auto-close' in sys.argv:
        bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=1)
    return None

def exercise():
    editor = instances["editor"]
    expected_open = '--pie-ui-expanded-preview' in sys.argv
    assert (editor.show_hotkey, editor.show_labels, editor.show_parameters) == (expected_open,) * 3
    revision = demo['LIBRARY'].revision
    editor.item_parameters = '{"value": [1, 0, 0]}'
    draft = demo['hotkey_draft'](editor)
    draft.type, draft.ctrl = 'F10', True
    for property_name in ('show_hotkey', 'show_labels', 'show_parameters'):
        setattr(editor, property_name, not expected_open)
        setattr(editor, property_name, expected_open)
    assert editor.item_parameters == '{"value": [1, 0, 0]}'
    assert draft.type == 'F10' and draft.ctrl
    assert demo['LIBRARY'].revision == revision
    editor.load_fields()
    if editor.choosing_destination:
        editor.cancel_move = True
    editor.new_menu = True
    child = editor.menu_choice
    editor.menu_name = "Modeling tools"
    editor.rename_menu = True
    editor.item_kind = "command"
    editor.item_name = "Smooth"
    editor.item_action = "object.shade_smooth"
    editor.item_parameters = "{}"
    editor.marker_mode = 'new'
    editor.marker_name = 'UV'
    editor.marker_color = (1.0, 0.5, 0.0)
    editor.save_label = True
    assert demo['LIBRARY'].palette['#ff8000'] == 'UV'
    assert demo['LIBRARY'].menus[child].groups['RADIAL'][0] is None
    assert editor.assigned_marker == 'none'
    editor.apply_item = True
    assert demo["LIBRARY"].menus[child].groups["RADIAL"][0].label == "Smooth"
    assert demo['LIBRARY'].menus[child].groups['RADIAL'][0].marker_color == 'none'
    editor.palette_choice = '#ff8000'
    editor.assign_label = True
    assert demo["LIBRARY"].menus[child].groups["RADIAL"][0].marker_color == '#ff8000'
    assert demo['LIBRARY'].palette['#ff8000'] == 'UV'
    assert editor.marker_mode == 'existing'
    assert editor.palette_choice == '#ff8000'
    # Painting several unlabelled buttons must retain the selected label.
    for slot in ('RADIAL_1', 'RADIAL_2'):
        before = demo['LIBRARY'].to_document()
        editor.slot = slot
        assert editor.palette_choice == '#ff8000'
        assert editor.assigned_marker == 'none'
        assert demo['LIBRARY'].to_document() == before
        editor.item_kind = 'command'
        editor.item_name = 'Extra smooth'
        editor.item_action = 'object.shade_smooth'
        editor.item_parameters = '{}'
        editor.apply_item = True
        assert demo['LIBRARY'].menus[child].groups['RADIAL'][int(slot[-1])].marker_color == 'none'
        assert editor.palette_choice == '#ff8000'
        editor.assign_label = True
        assert demo['LIBRARY'].menus[child].groups['RADIAL'][int(slot[-1])].marker_color == '#ff8000'
    before = demo['LIBRARY'].to_document()
    editor.slot = 'TOP_0'
    assert editor.palette_choice == '#ff8000' and editor.assigned_marker == 'none'
    editor.menu_choice = 'modeling'
    assert editor.palette_choice == '#ff8000'
    editor.menu_choice = 'main'
    assert editor.palette_choice == '#83a9d5', 'A labelled button must show its own label'
    editor.menu_choice = child
    assert editor.palette_choice == '#83a9d5' and editor.assigned_marker == 'none'
    assert demo['LIBRARY'].to_document() == before
    editor.slot = 'RADIAL_0'
    assert editor.palette_choice == '#ff8000'
    editor.hotkey_enabled = True
    draft = demo['hotkey_draft'](editor)
    draft.type = 'F9'
    draft.ctrl = True
    editor.save_hotkey = True
    assert demo['LIBRARY'].menus[child].hotkey['type'] == 'F9'
    assert demo['LIBRARY'].menus[child].hotkey['ctrl'] is True
    assert any(item.type == 'F9' and item.ctrl and item.properties.menu_id == child for _, item in demo['KEYMAPS'])
    draft = demo['hotkey_draft'](editor)
    draft.type, draft.ctrl = 'F8', False
    editor.save_hotkey = True
    assert demo['LIBRARY'].menus['main'].hotkey is None
    assert demo['LIBRARY'].menus[child].hotkey['type'] == 'F8'
    assert sum(item.type == 'F8' for _, item in demo['KEYMAPS']) == 1
    assert any(item.type == 'F8' and item.properties.menu_id == child for _, item in demo['KEYMAPS'])
    editor.menu_choice = 'main'
    draft = demo['hotkey_draft'](editor)
    draft.type, draft.ctrl = 'F8', False
    editor.save_hotkey = True
    assert demo['LIBRARY'].menus[child].hotkey is None
    editor.menu_choice = child
    draft = demo['hotkey_draft'](editor)
    draft.type, draft.ctrl = 'F9', True
    editor.save_hotkey = True
    assert any(item.type == 'F9' and item.ctrl and item.properties.menu_id == child for _, item in demo['KEYMAPS'])
    revision = demo['LIBRARY'].revision
    editor.start_move = True
    assert editor.choosing_destination and editor.move_source == 'RADIAL_0'
    editor.cancel_move = True
    assert not editor.choosing_destination and demo['LIBRARY'].revision == revision
    editor.start_move = True
    editor.slot = 'TOP_0'
    assert not editor.choosing_destination and editor.slot == 'TOP_0'
    assert demo["LIBRARY"].menus[child].groups["TOP"][0].label == "Smooth"
    assert demo['LIBRARY'].menus[child].groups['RADIAL'][0] is None
    editor.menu_choice = "main"
    editor.slot = 'RADIAL_0'
    original = demo['LIBRARY'].menus['main'].groups['RADIAL'][0]
    occupied = demo['LIBRARY'].menus['main'].groups['TOP'][0]
    editor.start_move = True
    editor.slot = 'TOP_0'
    assert demo['LIBRARY'].menus['main'].groups['TOP'][0] == original
    assert demo['LIBRARY'].menus['main'].groups['RADIAL'][0] == occupied
    editor.start_move = True
    editor.slot = 'RADIAL_0'
    assert demo['LIBRARY'].menus['main'].groups['RADIAL'][0] == original
    assert demo['LIBRARY'].menus['main'].groups['TOP'][0] == occupied
    editor.slot = 'RADIAL_7'
    editor.remove_item = True
    assert editor.item_kind == 'empty'
    editor.item_kind = 'submenu'
    editor.item_name = ''
    editor.target_menu = child
    editor.apply_item = True
    link = demo['LIBRARY'].menus['main'].groups['RADIAL'][7]
    assert link.target_menu == child and link.label == 'Modeling tools'
    editor.start_move = True
    editor.menu_choice = child
    assert not editor.choosing_destination
    editor.menu_choice = 'main'
    editor.slot = "RADIAL_6"
    editor.item_kind = "submenu"
    editor.item_name = "Modeling tools"
    editor.target_menu = child
    editor.apply_item = True
    assert demo["LIBRARY"].menus["main"].groups["RADIAL"][6].target_menu == child
    editor.menu_choice = child
    editor.slot = 'TOP_0'
    assert editor.marker_mode == 'existing'
    assert abs(editor.marker_color[1] - 128 / 255) < 1e-6
    editor.palette_choice = '#83a9d5'
    assert abs(editor.marker_color[0] - 131 / 255) < 1e-6
    editor.apply_item = True
    assert demo['LIBRARY'].menus[child].groups['TOP'][0].marker_color == '#ff8000'
    editor.assign_label = True
    assert demo['LIBRARY'].menus[child].groups['TOP'][0].marker_color == '#83a9d5'
    editor.remove_label = True
    assert demo['LIBRARY'].menus[child].groups['TOP'][0].marker_color == 'none'
    assert '#83a9d5' in demo['LIBRARY'].palette
    editor.palette_choice = '#ff8000'
    editor.delete_label = True
    assert '#ff8000' not in demo['LIBRARY'].palette
    assert demo['LIBRARY'].menus[child].groups['TOP'][0].marker_color == 'none'
    editor.clear_hotkey = True
    assert not any(item.properties.menu_id == child for _, item in demo['KEYMAPS'])
    assert demo['hotkey_draft'](editor).type == 'NONE'
    # Update a used label across menus without losing command/hotkey drafts.
    editor.palette_choice = '#83a9d5'
    assert editor.marker_name == 'Blue'
    editor.item_parameters = '{"draft": true}'
    draft = demo['hotkey_draft'](editor)
    draft.type = 'F12'
    before = demo['clone_library'](demo['LIBRARY'])
    assert demo['palette_usage'](before, '#83a9d5') >= 3
    editor.marker_name = 'Views'
    editor.marker_color = (1.0, 0.0, 1.0)
    editor.update_label = True
    assert editor.item_parameters == '{"draft": true}' and draft.type == 'F12'
    assert editor.palette_choice == '#ff00ff' and editor.marker_name == 'Views'
    assert '#83a9d5' not in demo['LIBRARY'].palette
    editor.slot = 'TOP_1'
    assert editor.palette_choice == '#ff00ff' and editor.assigned_marker == 'none'
    for key, menu in before.menus.items():
        assert demo['LIBRARY'].menus[key].hotkey == menu.hotkey
        for group, slots in menu.groups.items():
            for index, item in enumerate(slots):
                expected = replace(item, marker_color='#ff00ff') if item and item.marker_color == '#83a9d5' else item
                assert demo['LIBRARY'].menus[key].groups[group][index] == expected
    editor.menu_choice = 'main'
    editor.slot = 'RADIAL_0'
    assert editor.assigned_marker == '#ff00ff'
    before = demo['clone_library'](demo['LIBRARY'])
    editor.delete_label = True
    assert editor.assigned_marker == 'none' and '#ff00ff' not in demo['LIBRARY'].palette
    fallback = editor.palette_choice
    assert fallback in demo['LIBRARY'].palette
    editor.menu_choice = child
    editor.slot = 'TOP_1'
    assert editor.palette_choice == fallback, 'Deleted selections must fall back to an existing label'
    for key, menu in before.menus.items():
        for group, slots in menu.groups.items():
            for index, item in enumerate(slots):
                expected = replace(item, marker_color='none') if item and item.marker_color == '#ff00ff' else item
                assert demo['LIBRARY'].menus[key].groups[group][index] == expected
    assert demo['STORE'].load().to_document() == demo['LIBRARY'].to_document()
    editor.menu_choice = 'main'
    editor.slot = 'RADIAL_0'
    assert demo['label_icon']('#83a9d5') > 0
    bpy.app.timers.register(capture, first_interval=1)
    return None

def open_editor():
    area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.wm.pie_editor("INVOKE_DEFAULT")
    bpy.app.timers.register(exercise, first_interval=1)
    return None

bpy.app.timers.register(open_editor, first_interval=2)

