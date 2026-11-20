# Style Transfer into Blender

Verification date: November 17, 2026. Historical prototype report; later UI
decisions are recorded in `AGENTS.md` and `menu-editor-qa.md`.

## Visual source and result

Source: the user's current web-editor settings,
`design-preview/blender-transfer.jpg`, 1743×1190. It used recommended hover
`#185b56` and separate light hover text `#dedede`.

Result: `design-preview/blender-round-markers.png`, 1280×960, captured natively
in Blender 5.2 LTS. Splash was disabled in the separate test session. Components
were at 100%; dimensions were physical pixels relative to UI scaling. Source
and result were inspected together over the menu region.

## Comparison

- Typography: Segoe UI loaded from Windows fonts, with the selected 14 px size
  transferred from the editor. Other platforms fell back to Blender's available
  font. Browser/GPU antialiasing differences were acceptable.
- Geometry: radial buttons 144×35, extra buttons 186×24, radius 15, dots 5 px,
  row/column gaps 8. Eight directions and both six-button grids were fully visible.
- Colors: user dark backgrounds, border, normal text, muted numbers, four marker
  colors and hover transferred through JSON. Light hover text remained distinct
  from normal gray text.
- Content: functional prototype commands, while web examples repeated some
  captions. Category color was inferred from commands; custom color was slot-bound.
- Images: no new runtime bitmap assets. Blender captured its own screenshot.

The first capture showed wider captions in Blender's default font. Loading
Segoe UI resolved the P2 typography mismatch; the next capture showed the full
Frame Selected caption.

## Behavior checks

- Import, unregister and re-register all operators.
- Load user appearance at startup.
- Hit all eight directions and all twelve extra buttons.
- Extra-button priority and placement in small viewports.
- Transform, cursor and submenu categories.
- Native JSON import operator with file persistence.
- Invalid import preserved previous appearance in memory/on disk.
- Missing newly introduced fields received defaults.
- Actual Blender window rendering, including hover; test error log was empty.

User evaluation of interaction feel remained pending. Rendering was verified on
Windows in Blender 5.2 LTS.

Final result: passed.
