# Agent Crossing WebSocket port fix

- Scope: resolve the local port 8000 collision and restore the public HTTPS WebSocket.
- Frontend: Vite/React served through Caddy on `agentcrossing.byfred.io`.
- Backend: FastAPI/Uvicorn bound to loopback port `8001`.
- Proxy: route `/ws/world` to the backend and all other traffic to Vite on `3010`.
- Constraints: preserve the existing live-development frontend and avoid unrelated changes.

## 2026-08-24 two-agent day lifecycle

- Make Jiho and Sujin live an accelerated in-game day using day/hour/minute plans.
- Connect active plans to canonical Briar Cove movement, encounters, and the observer UI.
- Persona premise: Jiho privately likes Sujin; Sujin knows him as a friend and retains independent goals and boundaries.
- Generation model: `ollama_chat/qwen3.8:27b-mlx`; embedding model: `bge-m3:latest`.

## 2026-08-24 readable resident bubbles

- Replace emoji-only bubbles with visible Korean text.
- Render actual speech without parentheses.
- Render public thought summaries and actions inside one pair of parentheses.
- Never expose model chain-of-thought, self-critique, or governance traces.

## 2026-08-24 resident card interaction fix

- Symptom: tapping the Jiho Park or Sujin Lee rows in the mobile observer panel has no effect.
- Expected behavior: selecting a resident follows that NPC with the existing Phaser camera behavior.
- Mobile acceptance: close the observer panel after selection so the followed resident is visible immediately.
- Constraint: keep React-to-Phaser state sharing in the Zustand bridge and do not implement the unfinished memory/plan/reflection inspector.

## 2026-08-24 mock-only UI remediation

- Replace fabricated main-event copy/progress with selected-resident active-minute state.
- Keep resident follow, controls, and live updates correct across world/interior scenes.
- Expose canonical Tiled agent affordances when visible world objects are selected.
- Add mobile pinch zoom, truthful status fallbacks, and frontend regression tests.
- Preserve the concurrent readable-bubble contract and avoid backend/API/DB expansion.

## 2026-08-24 cognitive observability dashboard

- Add `agentcrossing.byfred.io/dashboard` inside the existing Vite + React architecture.
- Show actual agent state, hierarchical plans, memory stream, reflections, decisions,
  actions, dialogue, and governance diagnostics.
- Keep internal diagnostics out of the public spatial WebSocket contract.
- Preserve existing `/` Phaser behavior and avoid fabricated dashboard data.

## 2026-08-24 directional relationship summaries

- When an agent is selected, summarize how that agent currently perceives every other agent.
- Keep private and asymmetric knowledge directional; never infer the reverse perspective.
- Show evidence-backed qualitative affinity because the runtime has no canonical numeric relationship score.

## 2026-08-26 modeled relationship approval

- Replace the former `not_modeled` contract with session-scoped directional scores.
- Actions and conversations change familiarity, trust, affinity, tension, and romantic interest through fixed rules.
- Persist the relationship state with each game session and redesign the Relationship tab around it.
