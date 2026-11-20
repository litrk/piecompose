# PieCompose 0.1.12

A Blender 5.2 add-on for gesture pie menus with eight fixed directions,
independent upper/lower button groups, submenu links and named color labels.

## Install

1. Start Blender without loading the development prototype script.
2. Open Edit → Preferences → Get Extensions → menu → Install from Disk.
3. Select `piecompose-0.1.12.zip` and enable PieCompose.
4. Open the 3D Viewport sidebar: N → PieCompose → Menu Editor.

A fresh installation starts with one empty New menu, no labels and no shortcuts.
Existing configurations are kept when reinstalling. Add commands through the
right-click context menu or the editor. Every menu can have its own shortcut.
Click the shortcut field, press a combination, then click Save hotkey.
Clear hotkey removes the binding. Assigning an occupied shortcut transfers it
from the previous menu to the selected menu.

## Back up or transfer a configuration

Use Export configuration in N → PieCompose to save your menus, commands, labels
and shortcuts in one JSON file. Use Import configuration to load it. Importing
backs up your current configuration.

## Use

- In the editor, choose Keyboard shortcut for a button, click the event field,
  press a combination such as Ctrl+B, then Save button. A blank name uses the
  combination. This is separate from the menu's Hotkey. At invocation, the
  current mode/tool keymap supplies the command and its parameters; Ctrl+B uses
  Bevel in Mesh Edit Mode. It follows user keymap changes. Missing/unavailable
  commands report a message. Single press combinations only; GG sequences and
  physical keyboard simulation are not supported.
- Manual command input accepts mesh.bevel, bpy.ops.mesh.bevel and empty ().
  Enter arguments separately in Parameters JSON; no Python code is evaluated.
- Right-click a supported Blender command button → Add to PieCompose.
- The editor and capture dialog reuse the last selected editing menu during
  the current Blender session. A deleted destination falls back to the first
  available menu. Explicit destinations supplied by scripts take priority.
- Writable scalar checkboxes use a common RNA capture mechanism: active object,
  object data/material, scene/world, viewport, preferences and nested settings.
  For example, In Front follows the active object; a modifier checkbox follows
  its active modifier. The capture/editor dialog shows the target. Collections
  without an active member retain their RNA key. Missing, incompatible or
  read-only targets are unavailable. Numeric fields, Boolean arrays and enums
  are outside this scalar checkbox support.
- Hold a menu shortcut, move and release. During the first 0.5 seconds of a
  gesture, release selects a radial target. After that, an exact hit in an
  upper or lower block takes priority. Clicks work immediately.
- Tap a shortcut without moving to leave the menu open for clicking.
- Click a submenu button to enter it. Esc, Backspace or the center returns.
- At the first menu, Esc or a center click closes it. Clicking empty space closes.
- Move button → select a slot on the diagram. Occupied positions swap buttons.
- Labels: Save label creates a palette entry; Assign label applies it.
  Choose an existing label, edit Name/Color and click Update label to change it
  on every assigned button. Clear label removes only the selected button's
  assignment; Delete label removes the entry and clears it from all buttons.
- Selecting an unlabelled button keeps the current palette selection ready for
  Assign label. A labelled button shows its own label. Navigation does not
  assign colors or save changes.
- Select sectors with gestures/clicks. There are no numeric hints or NumPad
  sector shortcuts; menu invocation shortcuts remain configurable.
- Hotkey, Labels and Parameters sections are collapsed by default.

Color labels use vertical bars in the working menu. The editor uses colored dots.

## Storage

To update PieCompose, use Install from Disk with the new version's ZIP. The configuration
path stays the same across versions. Existing files are loaded without being
rewritten during registration. If reading fails, the add-on reports an error
and does not activate an empty library or reset the file.

The installed add-on stores one `pie-menus.json` under Blender's user
configuration directory in `piecompose/`. The file is outside the add-on code
and is retained when the add-on is updated or disabled.

No scripts are evaluated from JSON. Commands are Blender operator identifiers
with JSON parameters. Commands with live references to scene data are not
captured; nested operator settings of macros are supported.

Tested with Blender 5.2. Older versions are not claimed as supported.
License: GPL-3.0-or-later; see LICENSE.txt.
