# Menu Editor QA — November 17–19, 2026

Historical development log. Entries describe successive prototypes, including
choices later superseded. Use `AGENTS.md` and README for current behavior.

## Marker comparison and editor refinements

`design-preview/markers-comparison.png` compares Dots and Bars side by side.
Both were captured in Blender with identical theme, layout, colors, text padding
and hover. Dots were 5 px; rounded bars were 3×16 px before scaling. At this
comparison stage dots remained the default; `--pie-marker-bar` enabled bars only
in previews. Captures used `tests/blender_gestures.py` with
`--pie-ui-preview --pie-marker-compare --pie-ui-hover --pie-ui-auto-close`.
Both runs passed gesture checks. No Computer Use.

The compact editor collapses Hotkey, Labels and Parameters by default. Headers
show the assigned shortcut and label name/color, or None. Parameters reveals
JSON; other fields and Button actions remain visible. Disclosure state is not
stored in configuration, survives slot selection and resets on dialog opening.

`tests/blender_editor_ui.py`, including `--pie-ui-expanded-preview`, verified
both states. Folding preserves unsaved JSON/shortcut drafts and does not change
the library revision. Existing callbacks passed menu/button creation, labels,
move/swap and shortcut transfer/clear. Native screenshots:
`design-preview/editor-collapsed.png`, `design-preview/editor-expanded.png`.
No Computer Use.

The user-approved diagram is upper block → centered Upper buttons heading →
radial slots → centered Lower buttons heading → lower block. Groups share three
columns, `scale_y=1.5` and native gaps; headings share `scale_y=1.2`. Compared the
reference with `design-preview/editor-grid-reference.png`: matching columns,
equal button heights and heading positions. The editor test passed in a separate
temporary Blender window; working-menu layout and slot data were unchanged.

An earlier grid refinement replaced three containers with different
`scale_y` 1.3/1.6 and extra separators with one 3-column × 7-row `grid_flow`,
`scale_y=1.5`. Heights, columns and gaps became uniform; the center label and
fixed indices were preserved. Upper/Lower headings stayed outside the grid.
Runtime layout was unchanged.

Compared native before/after images of the same test window:
`design-preview/editor-grid-before.png`, `design-preview/editor-grid-after.png`.
Unequal group heights/gaps were confirmed in the user's and baseline images.
Afterward columns/gaps, labels and selection were checked. Editor callbacks and
gesture tests passed. Verification covered native rendering and existing
callbacks, without claiming a complete accessibility audit.

`Run interactively` was removed. Saved commands now follow Blender UI invocation;
legacy `invoke` values normalize on load while parameters/names remain intact.
`wm.tool_set_by_id(name='builtin.move')` selects a tool; `transform.translate`
invokes Move/G. Both workflow phases, configuration round trip and editor UI
callbacks passed in a separate window.

## Macro capture and November 19 changes

Macro capture was corrected for nested `OperatorProperties`, including Duplicate
Objects and Duplicate Linked. Real data references remain unsupported. Nested
parameters serialize recursively; enum flags restore as sets. Interactive macro
transforms default to `release_confirm=False` unless explicitly overridden.

Both workflow phases passed in separate processes: normal/linked duplication,
independent/shared geometry, offset (1.25, 2.5, 3.75), nested `snap_elements`
and restoration after restart. A manual Computer Use test followed cube context
menu → right-click Duplicate Objects → Add to Pie Menu → Save → F8 → Duplicate
Objects. It created Cube.001; after the release_confirm fix, movement stayed
interactive until confirmation. The test scene was closed, capture helpers
stopped and Windows cursors reloaded.

Rounded runtime buttons and dark extra-button backgrounds (#1c1c1c) were restored.
Checkboxes use explicit neutral grays, including checked state; hover/text still
follow Blender's theme. The menu name above the runtime center was removed.
`Clear label` follows `Assign label`; palette deletion is separate.

The main-menu concept was removed from UI/model. New documents omit `rootMenu`,
while old files remain readable. Without `menu_id`, the first menu is only a
technical fallback, not a special role or setting.

Occupied shortcuts now transfer atomically: previous owner gets `hotkey=null`,
selected menu gets the shortcut. Persistence/restart and real callbacks verified
F8 transfer between menus and back, leaving one active F8 and preserving other
shortcuts. Invalid JSON with duplicate bindings still fails validation.

17 unit tests, configuration round trip, both workflow phases, gestures and
editor UI passed. Checked a native runtime screenshot with the enabled checkbox
under the cursor. No Computer Use for these checks.

Configuration transfer was simplified to `Import configuration` / `Export
configuration`: one JSON for menus, commands, links, palette and shortcuts,
compatible with earlier menu-library exports. Separate style transfer was
removed. Storage remains one `pie-menus.json`; default export name is
`pie-configuration.json`.

At an earlier stage, `Clear label` cleared an assignment; `Delete label` removed
an unused palette entry; `Clear hotkey` immediately saved no binding and removed
the keymap item. Conflicting shortcuts were then rejected without modifying
data/bindings, verified through a real RNA callback. This was later replaced
by shortcut transfer as described above.

An intermediate theme pass read runtime backgrounds, selection, text, outlines
and rounding from `wcol_pie_menu` / `wcol_tool` and used Blender's font. User label
colors survived; the global theme stayed unchanged. Passed 15 unit tests,
configuration round trip, both workflow phases, gestures, callbacks and native
editor/runtime hover screenshots. No Computer Use. Later refinements restored
explicit rounding, dark extra buttons and neutral checkbox colors.

An earlier export pass added `Import menus`, `Export menus` and `Export style`
in the add-on sidebar. Menu export included parameters, submenus, labels and
shortcuts; style used separate JSON compatible with Import style. Import created
a unique `*.before-import-*.json`; invalid input preserved the library. Export
could not overwrite active internal settings files. These separate actions
were subsequently consolidated into configuration import/export.

At that stage, Delete label required an unused entry; Remove label cleared only
the assignment. Empty palettes were supported without automatic pruning. The
list heading became Menus and the repeated selected-menu heading disappeared.
Run interactively had a Move example tooltip. Main menu still selected editor/
capture defaults independently of hotkeys; both controls were removed later.

That pass verified 15 unit tests, both workflow phases, actual import/export
operators in `tests/blender_settings.py` with temporary data/style paths, backups,
invalid-file rejection and label-deletion callbacks. Native dialog screenshot
checked; no Computer Use.

Further refinements made the list names-only, removed repeated shortcut/Main
text, renamed saved-label selection to `Choose label`, and removed a duplicate
color swatch while retaining the icon. Lower buttons was then placed below its
block; all three button actions received equal gaps. A separate editor test
window produced `design-preview/blender-menu-editor.png`. The final heading
positions were later adjusted to the approved diagram described above.

Runtime/editor extra blocks became 3 columns × 2 rows without changing saved
indices/commands. Shortcut release uses Button priority: exact radial/extra
button first, otherwise direction. Whole-block bounds no longer intercept
gestures; row/column gaps allow radial selection. The center dead zone remains.

`tests/blender_gestures.py` checked eight directions, release over every extra
button, gaps, empty sectors, small viewports, scale 1.5, corners and real modal
release branches. Both workflow phases and editor callbacks passed. Native
preview: `design-preview/blender-button-priority.png`. No Computer Use.

## Earlier November 18 behavior

UI, errors and tooltips moved to English without translating saved user names.
Initial palettes then contained Mint, Blue, Sand and Lavender. Passed 12 unit
tests, Blender write/read and a separate editor dialog. No localization added.

Visual movement replaced destination dropdowns: select source → Move button →
diagram target. Occupied slots swap; Cancel move writes nothing. Source is not
a valid target; settings/menu selection are temporarily hidden or disabled.
Switching menus cancels movement. UI tests covered empty destinations, swaps,
preservation of both contents and cancellation without revision changes.

Library persistence, visual editing and linked menus were implemented. Label
actions were split into Save label (palette), Assign label (button) and Remove
label (clear assignment without palette deletion). Save button did not assign
the palette selection. The Pie Menu center label was centered and columns equal.

Per-menu `hotkey` stored a key and Ctrl/Shift/Alt/Win booleans, or null. Legacy
files without it received F8 only on the old main menu. Duplicate shortcuts were
initially rejected before save. Changes updated our keymap items immediately;
unregister removed them. Gesture release followed the invoking key instead of
hard-coding F8. Set as main menu was then independent of shortcuts.

That stage passed 14 unit tests, separate write/read processes, gestures with
the new key and UI callbacks for labels and shortcut assignment/disable. Native
editor screenshot checked without Computer Use.

## Historical prototype usage

`powershell -ExecutionPolicy Bypass -File .\launch_blender.ps1` opened Blender
5.2 and loaded the project script. Automatic installation was not implemented yet.

- Initially F8 opened the main menu. Hotkey input captured a combination followed
  by Save hotkey. Disabling Enable hotkey also required saving. Set as main menu
  selected the main menu independently of shortcuts.
- The sidebar and F3 both opened the menu editor.
- Select a menu on the left, a diagram slot in the center and its content on the right.
- Create, rename, save, clear and move actions saved immediately.
- Move button selected a target; occupied targets swapped; Cancel move wrote nothing.
- Submenu items opened their target. Esc, Backspace or center returned; Esc at
  the first menu closed it. Empty-space clicks closed the entire menu.
- Under Color labels, Assign label applied a saved entry; Remove label cleared
  its assignment. Save label created a name/color before assignment. New commands
  had no label; saving the command did not assign the palette selection. Capture
  applied the label to the new button when the dialog was confirmed.
- Try menu closed the editor and opened the selected menu.
- Right-click supported Blender buttons → Add to Pie Menu selected a menu/slot.

Prototype commands/links lived in project-local `pie-menus.json`; appearance in
`pie-style.json`. Later Labels and Button actions grouping, centered headings,
circular diagram/palette icons and theme-based native button fills followed.
Custom individual fills would require custom UI rendering.

Saving submenu links into empty slots without a caption was fixed by using the
target name. UI regression cleared a slot, selected submenu, left the name blank
and verified the link. A separate manual window captured Ctrl+F11, saved it,
invoked the menu and followed the link from the formerly empty slot. The inactive
draft keymap/item was removed on editor close. Capture helpers were stopped and
Windows cursors restored after the manual test.

Atomic saving with revision checks prevented stale dialogs overwriting newer
changes. Operator parameters and empty sectors survived persistence.

## Initial checks and label development

- Initially eight model/storage unit tests passed.
- `blender_workflow.py` write/read in separate processes with one temporary JSON
  verified FRONT/TOP parameters, create/rename/move, submenu links, reload/execute.
- `blender_editor_ui.py` exercised actual RNA callbacks in a real dialog with
  temporary data, rather than only calling editor methods.
- UI checks covered menu/slot selection, Smooth from an extra block and submenus.
- Esc press returned to the parent; Esc release must not close it.
- Global Blender themes and Blender 4.4 settings were unchanged.

On November 18, all runtime buttons became 186×35 before scaling. Legacy style
import normalized extra sizes to radial sizes. Capture confirmation became Save
for both empty and occupied destinations.

Per-command `marker_color` initially held HEX, `none`, or an empty string for
category color. Older libraries loaded; movement/restart preserved explicit
colors. Nine unit tests, both workflow phases (sizes, empty clicks, center) and
real editor callbacks passed. Screenshots were native; no Computer Use.

Named palettes replaced automatic category choice. New color mode selected a
shade/name such as Selection or UV. At that stage saving a button also added its
color to the shared palette; Existing colors showed names/swatches. Initial
colors were mint, blue, sand and lavender. Later Save label became independent.

Buttons stored HEX; shared `palette` mapped HEX to name. Reusing HEX reused the
entry; duplicate names for different shades were rejected. Changing one button
did not recolor others. Legacy automatic marks froze to explicit colors and
legacy custom shades were added to the palette.

Twelve unit tests and Blender restart verified named-color creation, reuse,
no-color and movement. UI callbacks covered color choice, saving and disabling.
