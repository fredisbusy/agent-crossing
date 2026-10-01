# Bottleneck analysis: long-running Agent Crossing session

## Scope and evidence limits

This lane used read-only PostgreSQL queries, Docker statistics/logs, and static inspection of the save path. The backend had already been stopped, so there is no direct peak RSS/CPU sample from the slow period. Current PostgreSQL usage (`144.3 MiB`, `0.00% CPU`) is a post-stop idle sample, not evidence of historical peak usage.

The ranked findings below separate direct observations from causal inference. PostgreSQL counters are cumulative; `pg_stat_wal` and `pg_stat_bgwriter` report a reset at `2026-08-27 00:12:41 UTC`. Table counters are also cumulative and should be treated as workload indicators, not exact per-session timings.

## Ranked bottlenecks

### 1. Unbounded memory history plus 1,024-float embeddings made every autosave an increasingly large whole-state serialization (very high confidence, very high impact)

Direct evidence:

- The active persisted session is only at turn `10,700`, save version `215`, but its snapshot occupies `157 MB` in stored/compressed JSONB. Extracting the JSONB `characters` component measures `252 MB`; the other bounded components are small by comparison: position history `1.3 MB`, dashboard events `1.07 MB`, relationship events `263 kB`, and relationship states `26 kB`.
- The active projection contains `12,736` memories. One resident, `byeongyong`, owns `10,265` of them (80.6%), with `10,511,360` embedding scalar values. His saved `memories` array alone measures `203 MB`. Every memory has a 1,024-dimensional embedding; the normalized projection stores about `50 MB` of embeddings for the active session, while their decimal JSON representation is much larger.
- The other active residents have only 6-494 memories each, so this is not ordinary even growth across ten residents. It is dominated by one resident's unbounded stream.
- `WorldRuntime.export_save_state()` enumerates every memory and converts every NumPy embedding to a Python list of floats. `GameSessionRepository.save()` then calls `state.model_dump(mode="json")` for the monolithic snapshot and also materializes the full normalized projection.
- Autosave runs every 50 turns. The first failure at turn `10,750` attempted a `295,470,082`-character parameter. By turn `29,900`, the attempted parameter had reached `795,187,992` characters, a 2.69x increase while the database remained pinned at save version 215.

Inference:

- This is the most likely source of backend memory pressure and long Python CPU pauses. A save simultaneously retains live NumPy arrays, copied Python-float lists, Pydantic objects, a JSON-ready object graph, SQLAlchemy projection objects, and the database driver serialization. Peak memory therefore plausibly exceeded the final 0.3-0.8 GB payload by a large multiplier, but peak RSS is unknown because the backend is stopped.
- The extreme `byeongyong` skew is the dominant growth source. Why that resident accumulated observations far faster than the others requires a separate cognitive/runtime root-cause trace; the database establishes the skew but not its upstream cause.

### 2. Repeated oversized JSONB failures consumed minutes of CPU/I/O and paused the simulation every 50 turns (very high confidence, very high impact)

Direct evidence:

- PostgreSQL rejects the snapshot with `ProgramLimitExceeded: total size of jsonb array elements exceeds the maximum of 268435455 bytes`.
- Backend logs contain **384** `Periodic session autosave failed` events from the first failure at turn 10,750 through the final turn 29,900. Each retry kept `save_version=216` as its attempted value; none committed.
- `repository.save()` records its `now` timestamp before `model_dump`, projection construction, and `flush`. Comparing that timestamp to the exception log gives approximately **44 seconds** for the first failed repository save (`02:37:32` to `02:38:15`) and approximately **220 seconds** for the final one (`15:30:20` to `15:34:00`). `export_save_state()` happens before this interval, so total pause cost was at least that long.
- `_save_current_session_locked()` stops the stream and pauses the scheduler before exporting/saving, then resumes only in `finally`. Thus every failing autosave creates a user-visible/runtime stall rather than merely a background database error.

Inference:

- The worsening save duration closely tracks payload growth and likely accounts for the progressive “computer gets slower” experience: hundreds of increasingly expensive serialization/JSONB parsing attempts, each initiated again after 50 more turns despite a deterministic size-limit failure.
- Because `_write_projection()` constructs the entire replacement projection before `db.flush()`, even a flush that fails on the `game_sessions` JSONB update still incurs Python allocation/work for thousands of rows.

### 3. Full delete-and-reinsert projection saves caused severe PostgreSQL write amplification and storage churn (high confidence, high impact before the first failure)

Direct evidence:

- Each successful save calls `_delete_projection()` for relationship events/states, position history, cognitive logs, dialogue state, and characters; cascading deletes remove memories, citations, and plans. `_write_projection()` then inserts the complete current state again.
- Cumulative table statistics show the scale of this rewrite pattern:
  - `session_memories`: 1,386,394 inserts and 6,277,018 deletes.
  - `session_position_history`: 1,001,501 inserts and 2,921,501 deletes.
  - `session_cognitive_logs`: 72,311 inserts and 264,311 deletes.
  - `session_memory_citations`: 65,955 inserts and 279,459 deletes.
- The normalized `session_memories` table is `188 MB`, including `169 MB` of TOAST, even though only 19,252 memory rows are currently live across all sessions.
- PostgreSQL generated `65 GB` of WAL since the Aug 27 statistics reset (`89.6 million` WAL records and `6.79 million` full-page images). Docker reports cumulative PostgreSQL block I/O of **406 GB read / 262 GB write**.
- Checkpoint statistics since the same reset show 4.22 million buffers written by checkpoints and 9.68 million buffers written by backends. PostgreSQL logs repeatedly show checkpoints writing roughly 9,300 buffers and advancing about 60.8 MB of WAL during the failing-save period.

Inference:

- The projection rewrite design is responsible for substantial SSD/container I/O and WAL amplification. The exact fraction of Docker's 262 GB writes caused by Agent Crossing autosave versus PostgreSQL maintenance cannot be separated, but this database has no other application workload and the write/checkpoint cadence correlates with save attempts.
- Failed giant updates can still produce WAL/dirty TOAST pages before transaction abort. The checkpoint/WAL cadence continuing after turn 10,750 is consistent with this, although the available statistics do not attribute WAL to individual statements.

### 4. TOAST footprint and churn increased the cost of snapshot reads/writes; some retained free space is likely (high confidence for footprint, medium confidence for bloat estimate)

Direct evidence:

- The database is `624 MB`. `game_sessions` is `412 MB`, of which the base heap is only `8 kB`, indexes `48 kB`, and virtually all remaining space is its TOAST relation (`406 MB` heap plus `6.5 MB` index).
- The persisted snapshots' `pg_column_size` values sum to materially less than the `game_sessions` TOAST relation; the two large live rows are `157 MB` and `34 MB`, while the remaining 13 rows are mostly 0.1-33 MB.
- `pg_toast_16751` (for `game_sessions`) reports about 9.01 million inserted and 8.93 million deleted TOAST chunks over its life, with only about 104,165 estimated live chunks. Autovacuum ran 206 times through the last successful-save window.
- `session_memories` adds another `166 MB` TOAST heap and shows 4.16 million TOAST inserts and 18.83 million deletes over its life.

Inference:

- The discrepancy between current live payload sizes and the 412 MB relation indicates retained/free space and/or estimate/compression differences after repeated large updates. Exact bloat percentage was not measured because `pgstattuple` was not installed/enabled and no extension or maintenance operation was authorized.
- Bloat is secondary to the workload that created it: even a perfectly compact table would not make an 795 MB JSON payload valid or inexpensive.

### 5. Projection query patterns add CPU work but are secondary to serialization and writes (medium-high confidence, medium impact)

Direct evidence:

- `session_memory_citations` accumulated 6,277,018 sequential scans and 9.51 billion sequential tuples read. `session_plan_items` accumulated 67,211 sequential scans and 108 million tuples read. `session_relationship_states` shows 11,980 sequential scans and 10.1 million tuples read.
- Several indexes have never been scanned (`session_memories_character_local_key`, `session_memories_character_created_idx`, and multiple uniqueness/primary-key indexes), while delete/cascade and replacement work dominates the counters.
- Database cache hit ratio was `92.22%`, with 26.1 million blocks read and 309.4 million hits in the baseline sample. This is not a catastrophic cache miss rate, but the absolute access volume is high for a `624 MB` database.

Inference:

- Foreign-key checks/cascades during wholesale deletion likely explain much of the citation scan count. Index review may help, but incremental persistence/removing duplicate snapshot storage will have much larger leverage.

## What is not supported by the database evidence

- PostgreSQL is not presently consuming large RAM or CPU: after backend shutdown it is idle at `144.3 MiB` and `0% CPU`. This does not rule out historical I/O/CPU pressure during saves.
- There were no deadlocks and the pre-diagnostic baseline had no PostgreSQL temp-file spill. A later `1.85 GB` temp counter was caused by this investigation's large read-only JSONB decomposition queries and must not be attributed to the original slowdown.
- `track_io_timing` is off, so PostgreSQL cannot provide historical read/write latency in milliseconds.
- No live backend peak RSS, CPU sample, flame graph, host memory-pressure trace, or per-process disk bandwidth was preserved. Claims about exact backend peak memory remain inference.

## Recommended remediation order (not applied)

1. **Stop retrying deterministically invalid snapshots.** Add a preflight serialized-size/component limit and mark autosave degraded after a size-limit failure; back off rather than retrying every 50 turns. Keep the runtime responsive and surface a diagnostic.
2. **Remove embeddings from the monolithic JSONB snapshot.** Persist memories once in the normalized/pgvector model and reference them by stable IDs/version. If a portable snapshot is required, store compact binary float32 data or a separate bounded artifact, not decimal arrays embedded in one JSONB array.
3. **Bound or compact memory history per agent.** Investigate why `byeongyong` reached 10,265 memories while peers remained below 500; enforce retention/archival/summarization rules that preserve the retrieval/reflect spec rather than silently dropping required memory.
4. **Replace full projection rewrites with incremental upsert/append.** Position history, memories, citations, logs, and relationship events are naturally append/update workloads. Persist deltas and update current state rows transactionally.
5. **Avoid storing two full copies of the same state.** Choose the normalized schema as the authoritative representation or split a small resumable session header from large versioned components.
6. **After the write path is fixed, measure and reclaim bloat safely.** Run `pgstattuple`/relation-level bloat analysis, then schedule `VACUUM (ANALYZE)` or an online rewrite/`VACUUM FULL` only with an explicit maintenance plan and backup. Do not use vacuuming as the primary fix.
7. **Add observability.** Record autosave stage timings (export, Pydantic conversion, JSON encode/send, database update, projection persistence), payload/component byte counts, per-agent memory counts, WAL rate, backend RSS, and skip/backoff counts.

## Bottom line

The dominant slowdown was not “PostgreSQL is simply large.” It was an unbounded in-memory memory stream—overwhelmingly one resident—duplicated into a giant decimal-embedding JSONB snapshot and a normalized projection. Autosave then repeatedly stopped the runtime, rebuilt the whole state, attempted an invalid 295-795 MB JSONB update, and drove heavy WAL/checkpoint/container I/O. Database bloat and inefficient cascade scans amplified the cost but are downstream effects, not the root cause.
