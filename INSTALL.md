# PieCompose 0.1.12

Installable add-on for Blender 5.2 LTS.

1. Save your scene and close Blender running the prototype. Start Blender normally without `launch_blender.ps1`.
2. Open Edit → Preferences → Get Extensions → menu → Install from Disk. Select `dist/piecompose-0.1.12.zip` and enable PieCompose.

Editor: N → PieCompose → Menu Editor or F3 → PieCompose: Menu Editor. Without an
existing configuration, a fresh installation contains one empty New menu with
no commands, labels or shortcut. Add commands and assign a shortcut in the
editor. Reinstallation preserves saved settings.

The working menu uses vertical color-label bars; the editor uses circular icons.
The installed add-on keeps data in Blender's user configuration directory,
outside the add-on code. Use Export configuration for portable backups.

Support for earlier Blender versions is not claimed yet.

To update PieCompose, use Install from Disk with the new version's ZIP. The permanent path
is `CONFIG/piecompose/pie-menus.json`, independent of the add-on version. Saved
menus, labels and shortcuts load without resetting. If an existing file cannot
be read, the add-on reports an error instead of activating an empty library.
