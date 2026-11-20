# Tools and Viewport Checkbox Capture — November 19, 2026

Target: private development build 0.1.4, Blender 5.2.0 LTS on Windows.

## Problem and implementation

Affect Only Origins in N → Tool exposes `ToolSettings.use_transform_data_origin`
as a property button. Execution already supported the legacy `origins` action,
but context capture handled operators and only special-cased X-Ray properties.

Added common capture of writable scalar Booleans on `scene.tool_settings`,
`space_data.shading`, `space_data.overlay` and `space_data`. Viewport paths require
SpaceView3D. Captured items store `wm.context_toggle` plus a context-relative
`data_path`, never a fixed value or source pointer. X-Ray retains its specialized
operator mapping so Solid/Wireframe/Pose semantics stay unchanged.

The runtime resolves checkbox state in the active context and displays a neutral
checkbox. Blender's context-toggle operator may return CANCELLED after changing
a viewport setting that needs no undo step; success is accepted only when the
supported Boolean actually flips. Numeric, array, read-only and unrelated object
properties are not generalized into toggles. Unsupported Boolean owners show a
reason in the context menu.

## Related workflows verified

- `blender_toggles.py`: capture actual RNA properties for Origins, Locations,
  Parents, shadows, grid floor and gizmos; save through the capture operator;
  reload JSON; switch both ways; check state; execute against a different scene
  and viewport without modifying the original. Rejected numeric/unsupported
  properties and invalid paths. Capturing itself did not alter source values.
- `blender_xray.py`: both X-Ray property buttons and the standard operator,
  persistence and Solid/Wireframe toggling passed. Other shading Booleans now
  use the common capture path.
- Both `blender_workflow.py` phases passed in separate processes, now including
  Origins capture, reload and execution, plus existing command parameters,
  macros, submenu, shortcut and gesture checks.
- `blender_settings.py` passed configuration import/export and backup checks.
- All 19 model/storage unit tests passed.
- Native runtime preview with `--pie-ui-property-toggle --pie-ui-checkbox`
  passed existing gesture checks and displayed captured Origins checked under
  hover: `design-preview/property-toggle-on.png`. Error log was empty.
- Expanded `blender_editor_ui.py` passed actual editor callbacks; error log empty.
- Build and ZIP validation passed. Live update from the delivered 0.1.3 ZIP,
  full configuration comparison, restart, reinstall and read-error protection
  passed in the isolated lifecycle profile.

## Exact tested archives

- Source: private build g<1>
  SHA-256: `62028d50a410d12ef278bea7ef715e2a508002dd983f9f3c2e9489ab3f34f1dd`
- Target: private build g<1>
  SHA-256: `c1c29a96e70a6ca1228d8ba876ce4d1aaab0cb11a012c636cc542657653abce8`

Limits: supported scalar properties on the listed owners, not every Blender
property. Verification used automated callbacks/context metadata and native UI
inspection; no new manual gesture-feel or cross-platform evaluation. Tests used
temporary configurations/profiles and Blender screenshots, without Computer Use.
The user's working configuration was not modified.
