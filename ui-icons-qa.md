# Editor Action Icons — November 19, 2026

Target: private development build 0.1.2, Blender 5.2.0 LTS on Windows.

## Change and related workflows

Native action buttons mixed captions with and without icons, producing
different text alignment. Added matching native icons to the remaining actions:

| Action | Blender icon |
| --- | --- |
| Save button, Save label, Save hotkey | FILE_TICK |
| Rename | GREASEPENCIL |
| Assign label | LINKED |
| Clear label | UNLINKED |
| Clear hotkey | X |

Existing Add, Delete, Clear slot and Move icons remain. All action captions now
reserve the same native icon space. Dialog footer buttons remain a matching
pair without icons. Selection rows and input fields are not action buttons.

Related workflows: save a command, manage labels, rename a menu, save/clear
shortcuts and update an existing installation. No data schema, storage path,
event handling or runtime pie geometry changed.

## Verification

- Confirmed all selected icon identifiers exist in the installed Blender API.
- Ran `blender_editor_ui.py -- --pie-ui-expanded-preview --pie-ui-auto-close`
  before and after the change. Both passed actual editor callbacks, including
  creation, saving, labels, move/swap and shortcut transfer/clear.
- Visually compared native screenshots at matching window size and state:
  `design-preview/action-icons-before.png` and `design-preview/action-icons-after.png`.
  Save button now aligns with Clear slot and Move button; label/shortcut actions
  also have consistent icon spacing. Both error logs were empty.
- All 17 unit tests passed. Native extension build and ZIP validation passed.
- The live update test from private build 0.1.1 passed
  fresh installation, actual live Install from Disk update to 0.1.2, restart,
  reinstall and invalid-configuration rejection. File bytes and full in-memory
  configuration/bindings were preserved through the update.

## Exact tested archives

- Source: private build g<1>
  SHA-256: `dd84174e5827fa264c04957ec9c006d67392836f9d658c180b03f267c6126f85`
- Target: private build g<1>
  SHA-256: `9eb74945e0719683c47541033bbd17fa5d4f2e95c6f94921ebca5e2b039b95fc`

Scope: native Windows rendering and existing functional callbacks in Blender
5.2. Cross-platform rendering and a full accessibility audit were not tested.
Temporary libraries/profiles were used; the user's configuration was not changed.
Screenshots used Blender's native API; no Computer Use capture was started.
