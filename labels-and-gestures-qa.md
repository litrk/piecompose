# Label Editing and Pointer Selection — November 19, 2026

Target: private development build 0.1.3, Blender 5.2.0 LTS on Windows.

## Changes and affected workflows

- Removed numeric radial-button hints and NumPad sector selection. Menu
  invocation shortcuts, gestures, clicks and Esc/Backspace are preserved.
- Existing labels expose editable Name/Color and an explicit Update label
  action. Updating replaces the palette entry and all matching assignments
  across menus in one save. It does not assign the palette selection to an
  unrelated selected button or discard command/shortcut drafts.
- Delete label now clears all matching assignments and removes the palette
  entry in one save; commands, positions and shortcuts stay intact. Clear label
  still affects only the selected button. There is no automatic palette pruning.
- Conflicting names/colors are rejected without replacing another label.
- No JSON format or storage-path change. Existing configurations stay readable.

## Checks

- All 19 unit tests passed, including editing a label used by three buttons
  across menus, persistence, rename-only updates, collision rejection without
  mutation, deletion of used labels and an empty final palette.
- `blender_editor_ui.py -- --pie-ui-expanded-preview --pie-ui-auto-close` passed
  actual RNA callbacks for global recoloring/deletion, selected-assignment
  refresh, unchanged commands/hotkeys, retained drafts and file round trip,
  plus existing create/move/swap/shortcut checks. Error log was empty.
- `blender_empty_ui.py` passed first command, label and shortcut creation.
- Both `blender_workflow.py` phases passed in separate processes, including
  capture/execution, nested macro settings, submenu navigation, Esc release and
  gestures using reassigned invocation keys.
- `blender_settings.py` passed import/export, backup and invalid-file rejection.
- `blender_gestures.py` passed all existing direction/block/gap/center/scale
  checks and now asserts empty numeric suffixes and no sector activation from
  any of the eight former NumPad sector keys.
- Native preview (`--pie-ui-preview --pie-ui-auto-close`) verified the working
  menu renders without numbers: `design-preview/blender-button-priority.png`.
  The expanded native editor screenshot showed the new label controls and an
  enabled Delete label for a used palette entry.
- Build and native ZIP validation passed.
- Lifecycle with the previously delivered 0.1.2 ZIP passed clean installation,
  live Install from Disk to 0.1.3, full configuration byte/in-memory comparison,
  bindings, restart, reinstall and invalid-configuration protection.

## Exact tested archives

- Source: private build g<1>
  SHA-256: `9eb74945e0719683c47541033bbd17fa5d4f2e95c6f94921ebca5e2b039b95fc`
- Target: private build g<1>
  SHA-256: `62028d50a410d12ef278bea7ef715e2a508002dd983f9f3c2e9489ab3f34f1dd`

Scope: automated functional checks and native Windows UI inspection; no new
manual gesture-feel evaluation or cross-platform rendering check. Tests used
temporary settings/profiles and native Blender screenshots, without Computer Use.
The user's working configuration was not changed.
