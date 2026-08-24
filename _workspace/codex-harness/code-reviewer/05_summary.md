# Mock-only UI audit summary

## Confirmed gaps

1. Replace or label the seed-event panel as demo data until diffusion state exists.
2. Make resident follow and control hints scene-aware; add interior NPC interaction.
3. Subscribe enlarged interiors to live agent state.
4. Decide whether semantic map interactables are user controls; wire them or remove interactive affordance expectations.
5. Replace mobile wheel guidance with pinch support or mobile-specific instructions.
6. Add focused frontend regression tests so dead controls cannot ship behind a green zero-test command.

## Verification evidence

- Public clock advanced after WebSocket connection while seed-event copy and progress remained unchanged.
- Public DOM exposed only the inspector toggle and two resident-follow buttons as React controls.
- `pnpm --filter @agent-crossing/frontend build` passed with the existing large-chunk warning.
