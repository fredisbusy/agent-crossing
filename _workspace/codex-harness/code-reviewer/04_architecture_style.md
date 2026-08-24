# Architecture and test review

- The React-to-Phaser Zustand selection bridge works in `MainScene`, but the scene-specific subscription makes the same UI request inert in `InteriorScene`.
- Persistent React HUD instructions should derive from the active Phaser scene/capabilities.
- There is no frontend test script, test runner, or frontend test file. Root `pnpm test` can succeed while running zero frontend tests.
- The closed inspector is translated offscreen rather than made hidden/inert, leaving a keyboard-focus risk.
