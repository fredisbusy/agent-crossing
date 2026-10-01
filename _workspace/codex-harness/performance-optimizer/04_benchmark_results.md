# Baseline and acceptance benchmark

## Status

This investigation was diagnosis-only. No optimized build exists yet, so this file records the measured failure baseline and the acceptance benchmark required after implementation.

## Measured baseline

| Metric | Observed value |
|---|---:|
| Last successful active-session turn | 10,700 |
| Last successful save version | 215 |
| Last successful serialized snapshot | 295,437,753 bytes |
| Final failed snapshot parameter | approximately 795,187,992 characters |
| Failed autosaves after the last success | 384 |
| First failed repository-save duration | approximately 44 seconds |
| Final failed repository-save duration | approximately 220 seconds |
| Active-session memories at turn 10,700 | 12,736 |
| Memories owned by 병용 | 10,265 (80.6%) |
| 병용 observation memories | 10,239 |
| Distinct 병용 observation contents | 224 |
| Average serialized observation record | approximately 20.7 KB |
| PostgreSQL WAL since 2026-08-27 reset | 65 GB |
| PostgreSQL cumulative container block I/O | approximately 406 GB read / 262 GB write |
| Backend container limit | none configured |
| Backend Docker state after shutdown | `OOMKilled=true` (corroborating only; event timestamp unavailable) |

## Post-stop control sample

- PostgreSQL was idle at roughly 135-147 MiB and 0% CPU; database size alone was not causing current pressure.
- Host memory pressure reported 91% free, with 1.48 GiB of 3 GiB swap currently used. Lifetime swap counters cannot be attributed to this run.
- Agent Crossing frontend remained small at roughly 33-41 MiB and below 0.4% CPU.
- Unrelated workloads still consumed CPU after the backend stopped: `fast-trade-scanner` ranged from about 13-100%, while `local-sokoban-agent` remained around 40-50%. These can still make the computer feel busy independently of Agent Crossing.

## Required post-fix soak benchmark

Run a fresh 30,000-tick session with a static ten-agent phase and a representative movement/dialogue phase. Capture per-tick and per-save metrics.

Acceptance gates:

1. After directed-pair warm-up, 100 unchanged static ticks create zero new organic-perception memories.
2. A static ten-agent run creates at most 90 pair-initialization observations, without first-roster-agent concentration.
3. Snapshot size remains bounded and below the application budget; no PostgreSQL JSONB limit error occurs.
4. Autosave P95 remains below 2 seconds and never pauses the scheduler for tens of seconds.
5. Save work scales with changed rows, not total accumulated memory count.
6. No autosave retry storm: a typed deterministic size failure opens a circuit/backoff and emits one bounded diagnostic.
7. Backend RSS reaches a stable plateau; capture peak RSS and allocations during export/save.
8. WAL and block-I/O per 1,000 ticks remain approximately stable rather than increasing with session age.
9. Retrieval, reflection citations, session restore, and relationship state remain correct after memory archival/normalization.

## Instrumentation needed

- Per-agent memory count and distinct-content ratio.
- Snapshot component byte estimates before serialization.
- Export, model-dump, driver-send, database-flush, and projection-stage timings.
- Backend RSS/CPU and PostgreSQL WAL bytes per save.
- Rows inserted/updated/deleted per save and autosave skip/backoff reason.
