---
name: agent-crossing-portraits
description: Generate or update Agent Crossing resident pixel portraits and wire them into the dashboard while preserving the project's established character style, alpha, sizing, and fallback conventions. Use for 주민 얼굴, 초상화, avatar, portrait, or matching-character-art requests in this repository; not for Phaser world sprites or animation sheets.
---

# Agent Crossing Portraits

Create production assets that belong to the resident persona and remain visually
consistent with the checked-in roster.

## Source of truth

- Read the resident's `packages/backend/persona/<Name>.json` before prompting.
- Use explicit age, gender, traits, fixed persona, hobbies, and occupation. Do not
  infer demographics from the name or turn MBTI into a visual stereotype.
- Inspect existing files in `packages/frontend/public/portraits/`. Use one to
  three of them as local style references when extending the roster, and label
  them as style references rather than edit targets.
- Read [references/prompt-template.md](references/prompt-template.md) before an
  image-generation call.

## Asset workflow

1. Use the built-in image generator for one distinct call per resident. Request
   one original head-and-shoulders portrait with genuine transparency, no text,
   no frame, and no copyrighted-character resemblance.
2. Inspect every output. Reject identity drift, childlike proportions, clipped
   hair, background scenery, illegible facial features at thumbnail size, and
   duplicated clothing or faces from a style reference.
3. Keep the generator original in its default generated-images location. Copy a
   prepared project asset to
   `packages/frontend/public/portraits/<lowercase-agent-id>.png`.
4. Run `scripts/prepare_portrait.sh`. Use `--checkerboard` only when the apparent
   transparency is actual white/gray checker pixels. The script refuses to
   overwrite by default; use `--force` only when the user requested replacement.
5. Run `scripts/validate_portraits.sh` before wiring or finishing.

## Product integration

- Resolve portraits by lowercase `agent_id` in
  `packages/frontend/src/dashboard/residentPortraits.ts`.
- Keep image paths out of the backend API, runtime state, personas, and save
  snapshots. These are frontend presentation assets.
- Preserve the name-initial fallback for unknown residents.
- List images are decorative when the adjacent resident name is visible (`alt=""`).
  The overview image uses a Korean resident-specific alt such as
  `하은의 초상화`.
- Use `object-fit: cover` for compact list thumbnails and `contain` for the large
  overview portrait. Preserve `image-rendering: pixelated`.

## Verification and handoff

- Add or update mapping and fallback tests.
- Run `pnpm --filter @agent-crossing/frontend test` and `pnpm -r build`.
- Confirm every production image is present in `dist/portraits`, then inspect
  the list and overview at desktop and 390px when runtime data is available.
- Update `SPEC.md`, `TODO.md`, and the relevant dashboard topic documents when
  the asset contract or roster coverage changes.
- Report the final project paths, prompt set, generation mode, validation result,
  and any resident still using the fallback.
