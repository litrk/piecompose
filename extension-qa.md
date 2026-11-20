# PieCompose extension verification

## First public release candidate — 0.1.12

- Blender 5.2.0 LTS on Windows. All 26 unit tests passed. The native Blender
  extension tools built and validated the exact release ZIP.
- An isolated profile started with one empty menu, no hotkey and no labels.
  A fixture in another directory remained untouched. Live Install from Disk
  over the previous private PieCompose build preserved the full configuration,
  file bytes and bindings. Restart, reinstall, import and invalid-file
  protection passed. The editor opened from the installed release ZIP in a
  separate isolated profile. Older Blender versions were outside this check.
- Update source: `dist/piecompose-0.1.11.zip`, SHA-256
  `bce51e2fd4134a0ff8667f863eaf78f128ed2fb981897bd932a2e168256dbd6d`.
- Release candidate: `dist/piecompose-0.1.12.zip`, SHA-256
  `e8d698982ab80810103b95394c0e67a27bec0df379db19cf71b064d0ee4b74ec`.
