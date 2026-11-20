# Common RNA Checkbox Capture — November 19, 2026

Target: private development build 0.1.5, Blender 5.2.0 LTS on Windows.

## Mechanism and binding policy

`property_bindings.py` replaces the previous owner/property restrictions with
one RNA mechanism for writable scalar Booleans. It finds a source owner relative
to semantic active roots, using RNA paths and bounded pointer-graph discovery.
Root IDs are distinguished from nested structures; embedded RNA structures are
identified by both type and address because addresses may overlap.

Bindings follow active object/data/material, current scene/world/view layer,
pose/bone, viewport or preferences. Nested collection paths use their active
member where Blender provides one (modifiers, nodes, vertex groups, etc.). Other
collection paths retain their RNA member key. Renaming an active member does
not pin the old name. Missing/incompatible/read-only targets refuse execution;
there is no fallback to the original captured object.

The saved format remains `wm.context_toggle` with a relative `data_path`.
Resolution accepts only attributes and literal collection keys, with no
expression evaluation in our resolver. Before executing, the target must be a
writable scalar Boolean. Actual value changes determine success, including
Blender's non-undoable CANCELLED return. No-op setters are reported as failures.
Capture/editor dialogs show a human-readable target. Existing X-Ray operator
mapping preserves Blender's mode-dependent behavior.

## Verification

- 22 unit tests passed: existing storage/labels plus restricted path parsing,
  escaped keys, expression rejection, missing/read-only/non-Boolean targets
  and Boolean item-key resolution.
- `blender_property_capture.py` write/read passed in separate Blender processes:
  captured In Front, material Backface Culling, render transparency, active
  modifier visibility and Clamp Overlap, mesh mirror, world shadows, object
  render visibility, vertex-group lock and node Mute. Checked expected relative
  paths, no source mutation, saved JSON and execution after restart.
- Switched cube → sphere and verified active-object/material/modifier behavior
  without changing the original object. Renamed modifier/group/node, switched
  to an incompatible modifier/data type, deleted modifier/material and cleared
  the active object. Missing/read-only targets returned warnings without
  modifying unrelated data. A preferences checkbox was captured through pointer
  discovery without changing or saving preferences.
- Both legacy workflow phases passed, including nested macro settings,
  Origins persistence/execution, submenu and shortcut-release behavior.
- Tools/Viewport toggle, X-Ray, import/export and gesture regressions passed.
- Native capture preview passed and displayed `Target: Active object`:
  `design-preview/generic-property-capture.png`. Expanded editor callbacks also
  passed. Both UI error logs were empty.
- Build and native ZIP validation passed. The archive includes the new shared
  module and excludes personal data/tests.
- Lifecycle update from the actually delivered 0.1.4 archive passed fresh
  installation, live Install from Disk, exact saved-file/full in-memory library
  comparison, keymaps, restart, reinstall and invalid-configuration protection.

## Exact tested archives

- Source: private build g<1>
  SHA-256: `c1c29a96e70a6ca1228d8ba876ce4d1aaab0cb11a012c636cc542657653abce8`
- Target: private build g<1>
  SHA-256: `fae113c4c2b5d988984b7f73d8820260a7bea4e4bf52d377b5ebb81daa1f08a6`

## Limits

This is shared RNA discovery, not a guarantee for arbitrary custom UI widgets
or every possible context. A source with no active-context binding is rejected
with a reason. Numeric fields, Boolean arrays and enum-flag checkboxes remain
outside scalar Boolean capture. Menus currently execute in the 3D Viewport;
unrelated editor-specific state is not silently mapped into that viewport.
Preferences were capture-tested without toggling user settings. No new manual
gesture-feel evaluation or cross-platform rendering check was performed.

Tests used temporary libraries/profiles and native Blender screenshots, without
Computer Use. The user's working configuration was not changed.
