# PieCompose Workflow Regression Checks

Verify the complete user journey. Fixing one step must not break state created
by an earlier step or a previous build.

## Before delivering any new ZIP

1. Identify the archive actually delivered previously. Retain it and record its
   SHA-256. Give the new build a new version.
2. Run `python -m unittest discover -s tests`.
3. Build/validate the ZIP with `python scripts/build_extension.py`.
4. Run `python tests/run_extension_lifecycle.py --previous-archive <path>`.
   This covers fresh installation, existing data, enable/disable, Install from
   Disk in a running process, restart, reinstall and configuration read errors.
5. Run affected workflow checks below. Record results, versions and the exact
   tested new ZIP's SHA-256 in the QA report.

Update checks compare the file byte for byte and the entire in-memory library:
names, commands, parameters, labels, shortcuts, submenu links and empty slots.
If format migration becomes necessary, add explicit migration and user-value
preservation checks alongside byte comparisons; never weaken tests just to pass.
Do not write tests into the user's working configuration.

## Checks by change area

| Change | Related workflows and checks |
| --- | --- |
| Context capture, command parameters | Add → save → execute in the required context → reload after restart. Test operator buttons and Boolean property buttons separately. Both `blender_workflow.py` phases; X-Ray, Tools/Viewport toggles and both `blender_property_capture.py` phases. Change active object/material/collection member; rename/delete targets; remove the active target; check read-only/incompatible fields. |
| Editor, labels, movement | Create/replace, assign/clear labels, retain selection across unlabelled buttons/menus without auto-assignment, update/delete the selected label, empty palette/recreation, move/swap, cancel, close/reopen. `blender_editor_ui.py`; `blender_empty_ui.py` for empty startup. |
| Last editing menu | Editor → capture → repeat capture; cancel, save, rename/delete, replacement library and explicit scripted destinations. `blender_menu_memory_ui.py` with `--enable-event-simulate`; selecting menus must not write configuration. |
| Shortcuts, event handling | Assign → reassign → clear → hold/release the new key → restart. `blender_workflow.py`, `blender_editor_ui.py`, `blender_gestures.py`. |
| Keyboard shortcut button action | Native editor save → restart → resolve current mode/tool/user keymaps → interactive invocation. Both `blender_shortcut_ui.py` phases with `--enable-event-simulate` and isolated profile: Ctrl+B/Ctrl+Shift+B, live remap/parameters, click release, missing binding, draft cleanup. Import/export must retain shortcut items. This is distinct from menu invocation Hotkey. |
| Manual operator names | Accept bare and fully qualified bpy.ops names with optional empty (); reject code/arguments without writing. Both `blender_operator_input.py` phases and `blender_bevel_ui.py` for actual interactive click invocation. |
| Dimensions, layout, target selection | Eight directions, both blocks, gaps, empty slots, center, submenus, scaling and viewport edges. Extra blocks accept clicks immediately. A gesture release over an extra button selects the radial target before 0.5 seconds from movement and the exact extra button afterward. `blender_gestures.py` plus auto-closing UI preview; `blender_gesture_blocks_ui.py` with event simulation for real rapid movement, highlight/release agreement and held-key click/submenu safety. |
| JSON, storage path, import/export | Old data, full library after restart/update, invalid JSON without reset. Unit tests, both workflow phases, `blender_settings.py`, lifecycle. |
| Packaging, registration, version | Fresh installation and updating the previously delivered ZIP; data/bindings immediately afterward and after restart. Lifecycle plus `blender_installed_ui.py`. |

## Update coverage

Test real Install from Disk in a running Blender process before testing restart.
Use the version already delivered as the update source. Verify both configuration
bytes and the active menu library and bindings. A corrupt configuration must
stop registration without being overwritten.

For bugs discovered after delivery, record reproduction, the missed workflow
and a regression test. Data recovery may help the user, but cannot replace
fixing and verifying the update itself.
