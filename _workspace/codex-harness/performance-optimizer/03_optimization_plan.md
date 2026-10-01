# Optimization plan: long-running session snapshot growth

## Scope and conclusion

This is a diagnosis and remediation plan only. No production code, database data,
container, or configuration was changed.

The primary defect is not a generally busy database or the bounded dashboard and
position logs. It is a pair-scope bug in organic perception deduplication:
`WorldRuntime._dispatch_tick_plan_disruption_check()` iterates directed
`(observer, observed_agent)` pairs, but records the last observation under only
the observer's ID. With three or more agents, the first observer repeatedly
alternates between different observed agents and therefore creates approximately
one new embedded memory per tick even when nobody's action changes. A second,
architectural defect then amplifies that bad stream: every autosave materializes
all memories and their 1,024 float embeddings as JSON, stores that complete copy
in `game_sessions.snapshot`, deletes the normalized projection, and reconstructs
the whole projection.

At turn 10,700 this combination had already produced a 295,437,753-byte
serialized snapshot. At turn 29,900 the attempted payload was approximately
795,187,992 characters. PostgreSQL rejected every autosave from turn 10,750
onward with its 268,435,455-byte JSONB array-element limit. The autosave loop then
repeated this high-allocation, high-I/O failure every 50 turns, 384 times.

## Evidence and root-cause chain

### 1. Pair-scope bug creates a false memory on almost every tick (direct evidence)

- The runtime declares `_last_perceived_action` as `dict[str, str]` at
  `packages/backend/src/world/runtime.py:179`.
- The dispatcher iterates every directed pair with
  `itertools.permutations(self.active_agents, 2)` at
  `packages/backend/src/world/runtime.py:654`.
- It builds an observation containing the *other* agent at line 658, but uses
  only the observer ID as `agent_key` at line 659 and compares/updates that
  observer-only slot at lines 660-662.
- It starts one worker and returns at lines 663-669. For the first observer in a
  stable 10-agent roster, successive calls revisit `other_1`, then `other_2`;
  each differs from the single stored string, so the state never converges.
- The worker stores the false change through
  `create_observation_from_text()` at lines 671-698, which creates both an
  embedding and a memory.
- The existing two-agent unchanged-observation test at
  `packages/backend/tests/test_world_runtime.py:863-897` converges because each
  observer has only one possible partner. The three-agent test at lines 836-860
  checks only that one expected observation eventually appears; it never asserts
  that dispatches stop after all directed pairs have initialized, so it misses
  the alternating-partner defect.

The database confirms the exact skew predicted by the iteration order. In the
active turn-10,700 projection, 병용 owns 10,265 of 12,736 total memories (about
81%), while every other resident has only 242-494. 병용's memory JSON is about
203 MB and contains 10,511,360 embedding floats. A more specific query counted
10,239 of those records as `OBSERVATION`. The measured average serialized size
was about 20,743 bytes per bad observation.

The snapshot grew by 499,750,239 bytes between turns 10,700 and 29,900, or about
26,028 bytes per additional turn. This is consistent with one new 1,024-float
embedded observation per tick plus reflection/content overhead. This consistency
is an inference from the two observed snapshot sizes; the per-record skew and
bad key are direct evidence.

### 2. Full JSON embedding copies turn a logic bug into a RAM/JSONB failure (direct evidence)

- `MemoryStream.memories` is an unbounded Python list
  (`packages/backend/src/agents/memory/memory_stream.py:17-19`), and `snapshot()`
  returns the whole stream at lines 21-24.
- Each memory must carry an embedding (`persistence/contracts.py:36-44`), whose
  configured dimension is 1,024 (`packages/backend/src/settings.py:12`).
- `WorldRuntime.export_save_state()` walks every memory of every agent and
  converts each NumPy vector into Python float lists at
  `packages/backend/src/world/runtime.py:1331-1350`. The expression at line 1348
  first calls `.tolist()` and then builds another list with `float(...)`, creating
  avoidable temporary objects.
- `RuntimeSaveState.characters` embeds all of those `CharacterSave.memories`
  lists (`packages/backend/src/persistence/contracts.py:68-78,198-220`).
- `GameSessionRepository.save()` then performs a second whole-tree conversion
  with `state.model_dump(mode="json")` at
  `packages/backend/src/persistence/repository.py:217-232`.

Consequently, a save can simultaneously retain NumPy embeddings in the live
runtime, Python-float copies in `RuntimeSaveState`, a deep JSON-ready model dump,
the driver's serialized JSON parameter, and PostgreSQL's parse representation.
The exact peak-copy multiplier was not measured because the backend had already
been stopped, but multiple whole-snapshot representations are evident in code.
The stopped container reports an OOM flag and had no CPU or memory limit; treat
that flag as corroborating rather than sufficient proof of the final termination
cause until its event timeline is confirmed.

The persisted turn-10,700 row is already at the boundary: its whole snapshot
serializes to 295,437,753 bytes; PostgreSQL reports 252 MB for its `characters`
component and 157 MB for the compressed/toasted snapshot column. Position history
is only 1.3 MB and dashboard events only 1.07 MB. This rules those bounded logs out
as the dominant snapshot-growth source.

### 3. Every autosave rewrites the full normalized projection (direct evidence)

- Autosave is enabled every 50 ticks by default
  (`packages/backend/src/settings.py:66-69`) and the loop retries at every later
  divisible turn (`packages/backend/src/api/main.py:265-293`).
- A save replaces the giant JSON snapshot, calls `_delete_projection()`, and
  calls `_write_projection()` at
  `packages/backend/src/persistence/repository.py:217-233`.
- `_delete_projection()` removes relationship events/states, position history,
  cognitive logs, dialogue state, and finally session characters at lines
  331-361. Deleting characters cascades to memories/citations/plans.
- `_write_projection()` recreates a new character UUID and one ORM object for
  every memory, including its full embedding, at lines 364-444; citations,
  position history, cognitive logs, and relationship records are then recreated
  at lines 445-564.

Thus save work is O(total accumulated state), not O(changes since the last save).
With memory count growing roughly linearly in turns, cumulative autosave work is
quadratic over session lifetime. Database statistics match this pattern:

- `session_memories`: 1,386,394 inserts and 6,277,018 deletes for only 12,736
  current active-session rows.
- Citation activity: 6,277,018 sequential scans and about 9.51 billion tuples
  read; plan items: 67,211 sequential scans and about 108 million tuples read.
- PostgreSQL container block I/O: approximately 406 GB read and 262 GB written.
- PostgreSQL reported about 65 GB of WAL since August 27. The `game_sessions`
  TOAST relation recorded roughly 9.0 million chunk inserts and 8.9 million
  deletes, consistent with repeated replacement of the giant JSON value.
- Database size: 624 MB. `game_sessions` occupies 412 MB, almost entirely TOAST;
  `session_memories` occupies 188 MB, including 169 MB TOAST. The active compact
  pgvector embeddings account for about 50 MB, while the JSON `characters`
  component is about 252 MB.

After the first JSONB failure, the same code still constructed the full snapshot
and ORM projection before transaction flush/rollback. Repeating that 384 times is
the most plausible direct mechanism for severe CPU, allocator/RSS, database I/O,
WAL, and log pressure late in the run. Database-side failed-save duration grew
from about 44 seconds at the first failure to about 220 seconds at the last,
excluding `export_save_state()`. During that interval `_save_current_session_locked()`
has already stopped the spatial stream and paused the scheduler
(`packages/backend/src/api/main.py:519-548`), so each progressively slower failed
autosave also directly freezes simulation progress until its `finally` block
resumes the runtime.

### 4. Bounded or secondary structures (direct evidence)

- Dashboard events use `deque(maxlen=500)`
  (`packages/backend/src/world/observability.py:36-44`) and export at most 500
  events (`world/runtime.py:1390-1420`).
- Position history uses `deque(maxlen=5000)`
  (`packages/backend/src/world/spatial.py:69-96`) and records only state changes
  (`spatial.py:290-323`). It creates database churn because it is fully rewritten,
  but it does not explain hundreds of megabytes of snapshot growth.
- Active conversation sessions are removed when complete
  (`packages/backend/src/world/runtime.py:1146-1152`); only currently active
  sessions are exported at lines 1431-1433. Conversation history is not the
  dominant accumulation path.
- The relationship ledger is not implicated in this incident and has a 10,000
  event validation ceiling (`persistence/contracts.py:251-252`). It should still
  become append-only in the persistence redesign to avoid unnecessary rewrites.

## Prioritized remediation

### P0-A — Correct deduplication to be observer/observed-pair scoped

**Change**

Replace the observer-only dictionary key with a directed pair key, for example
`tuple[observer_agent_id, observed_agent_id]`. Compare only the observed agent's
canonical action state in that pair's slot. Keep the structure bounded to active
directed roster pairs (`N * (N - 1)`, currently at most 90), pruning keys when a
resident is removed from the authored roster. A restart may repopulate each pair
once; that bounded warm-up is acceptable and does not require adding the cache to
the durable snapshot.

The current one-worker-at-a-time policy may remain for the minimal fix, but its
loop must eventually converge for all directed pairs. A small queue or rotating
cursor is preferable later if fairness under frequent simultaneous changes is
important.

**Expected effect**

- Eliminate the approximately one false embedded observation per tick.
- Prevent the observed first-agent skew and remove roughly 20.7 KB/tick of this
  incident's dominant serialized growth (about 398 MB over the 19,200-turn failed
  interval before reflection/other overhead).
- Eliminate the corresponding embedding and importance LLM calls on static
  observations, reducing external-model CPU/latency as well as backend memory.

**Risks**

- If the key is made unordered, reverse-direction perception will be lost; it
  must be a directed pair.
- If a state changes several times while another pair's worker is active, the
  single-thread dispatcher may observe only the latest state. That is already the
  runtime's effective policy, but it should be documented and tested.
- Do not deduplicate only by content globally: two residents observing the same
  textual action are distinct memory events.

**Required tests**

Add regression tests beside `test_tick_plan_disruption_dispatches_across_three_agents`:

1. Initialize a static three-agent runtime, dispatch/join until all six directed
   pairs are seen, then dispatch 100 additional times; call and memory counts must
   remain exactly six.
2. Change only Minji's action; exactly the two directed observers of Minji should
   receive one additional observation each, and no pair should repeat it.
3. Run a static 10-agent fixture for at least 500 dispatches; organic perception
   memories must be at most 90 after warm-up and must not be concentrated in the
   first roster entry.
4. Preserve the two-agent behavior asserted at lines 863-897.

### P0-B — Add a cheap save budget and an autosave circuit breaker

**Change**

Before constructing a database parameter or thousands of ORM rows, calculate a
cheap state budget from per-agent memory counts and sampled/rolling serialized
bytes per memory. Refuse a save with a typed `SnapshotBudgetExceeded` error while
the last valid save remains untouched. Use substantial headroom below PostgreSQL's
268,435,455-byte JSONB container limit; do not set the application ceiling equal
to the database maximum.

On `SnapshotBudgetExceeded` or `ProgramLimitExceeded`, open a circuit for that
session/save generation instead of retrying every 50 turns. Surface one bounded
operator diagnostic with current turn, last successful save turn/version, largest
agent component, estimated bytes, and remediation state. Retry only after the
state becomes smaller, the persistence schema supports it, or an explicit
operator action resets the circuit. Preserve the existing safe-boundary and
resume behavior.

**Expected effect**

- Turn 10,750 would have failed before a ~295 MB driver parameter and full ORM
  graph were allocated.
- The following 383 giant retries would not have occurred.
- The existing version-215 save would remain available, exactly as it does now.

**Risks**

- This is containment, not durable capacity. A circuit breaker intentionally
  reports that autosave protection is degraded; it must be visible in the
  dashboard/health diagnostics rather than silently claiming saves continue.
- A count-only threshold can be wrong when content lengths vary. Use rolling byte
  estimates plus a final bounded serializer check, and unit-test multibyte Korean
  content.
- Increasing `SESSION_AUTOSAVE_TICK_INTERVAL` alone is not a fix; it reduces
  frequency but still reaches the same oversized state and increases recovery
  loss.

### P1-A — Make normalized memory/pgvector storage authoritative and incremental

**Change**

Stop embedding full memory vectors inside `game_sessions.snapshot`. The repository
already has `session_memories`, citations, and pgvector columns containing all
canonical fields (`packages/backend/src/db/models.py:158-200`). Store only bounded
runtime state plus per-agent memory high-water marks/version references in the
session snapshot. Restore memory streams by joining the normalized rows within the
same consistent save version.

Use stable session-character IDs and incremental writes:

- insert memories whose `runtime_local_id` is above the persisted high-water mark;
- update only dirty `last_accessed_at` values;
- insert citations after their referenced memory IDs are stable;
- append new position/cognitive/relationship events;
- upsert current character, planning, and relationship-state rows;
- never delete and recreate the entire projection during a normal autosave.

Keep the JSON update and normalized deltas atomic under the existing session row
lock/save-version transaction. Add a schema version and dual-read migration:
legacy v4 rows load their embedded memories; the new version loads normalized
memories. Backfill/convert the current v4 session before removing legacy support.
Update `SPEC.md` section 4.3 and the corresponding `TODO.md` item in the same
change, because the current contract explicitly says the snapshot contains
memory/citation state (`SPEC.md:101-111`, `TODO.md:554-564`).

**Expected effect**

- Snapshot size becomes independent of historical memory count and remains far
  below the JSONB container ceiling.
- Embeddings remain in pgvector's compact representation: measured active
  embeddings use about 50 MB there versus roughly 252 MB for the JSON
  `characters` component containing those and other fields.
- Autosave work changes from O(all historical memories/logs) to O(delta since
  last save), eliminating the observed delete/reinsert churn and most associated
  WAL, TOAST, vacuum, and block I/O.

**Risks**

- This is a persistence-contract migration, not a local refactor. Snapshot and
  projection must be read at one save generation or a crash could mix state.
- Citation referential integrity and zero-based runtime IDs must survive lazy
  restoration.
- Existing legacy snapshots near the JSONB limit need a streaming/externalizing
  migration path; loading and redumping the entire value can reproduce the OOM.
- Do not delete the 10,239 repeated observations as a quick fix. Some reflections
  may cite their local IDs, and timestamps/importance affect retrieval. Externalize
  first; any semantic compaction must remap citations and be separately approved.

### P1-B — Bound runtime RAM with a durable hot/cold memory stream

**Change**

After normalized storage is authoritative, keep only a bounded recent/hot window
of full `MemoryObject` embeddings in each process and retrieve cold candidates
from PostgreSQL/pgvector. Preserve stable IDs and the specification's recency,
importance, relevance, min-max normalization, and top-k tie-breaking. A safe
staged implementation is:

1. query database-side candidate metadata and vector similarity;
2. compute or fetch the global normalization extrema required by `SPEC.md`;
3. rerank deterministically with the existing formula;
4. update `last_accessed_at` only for returned memories.

The current implementation scores and sorts the entire Python list on every
retrieval (`packages/backend/src/agents/memory/memory_stream.py:61-129`), so even
after the false-perception fix a genuinely long simulation remains O(memories ×
1,024 dimensions) per query and unbounded in resident RSS.

**Expected effect**

- Backend RSS reaches a steady state instead of retaining every historical NumPy
  embedding.
- Retrieval latency no longer scales linearly in Python with session age.

**Risks**

- Approximate nearest-neighbor-only retrieval can change the specified result;
  verify exactness or explicitly revise the contract.
- Eviction must never make cited memories unloadable or renumber local IDs.
- Reflection-on-reflection tests and restoration tests must cover cold citations.

### P2 — Remove serialization duplication and batch ORM writes

**Change**

Even during migration, remove the `.tolist()` followed by a second
`[float(value) ...]` copy at `world/runtime.py:1348`. Avoid whole-model
`model_dump(mode="json")` for large collections; serialize bounded metadata and
write vector rows in chunks/bulk statements. Expunge batch ORM objects between
chunks if SQLAlchemy remains in the path.

This optimization should follow P1-A: making the current 795 MB JSON conversion
slightly more efficient does not make it valid or bounded.

## Benchmark and acceptance plan

Use deterministic stub embedding/LLM providers so the benchmark measures the
runtime and persistence code rather than model-server variance. Record peak RSS,
snapshot/component bytes, export time, save p50/p95/max, rows inserted/updated/
deleted, WAL bytes, database block I/O, database/TOAST sizes, memory count per
agent/node type, and retrieval p95.

### Benchmark A — static multi-agent perception

- 10 agents, unchanged actions, 30,000 dispatch opportunities.
- Before fix: preserve a short baseline demonstrating first-agent linear growth.
- After P0-A: no more than 90 initial directed-pair observations and zero organic
  memory growth after warm-up.
- Peak-to-final memory imbalance attributable to this dispatcher: zero repeated
  observations for every agent.

### Benchmark B — controlled action changes

- 10 agents; change one resident's canonical action every 100 ticks.
- Each change must yield exactly one observation for each eligible directed
  observer, subject to documented active/dialogue gating; unchanged pairs yield
  none.
- Verify every generated observation still reaches plan-disruption evaluation.

### Benchmark C — long autosave/load soak

- Run 30,000 ticks with autosave every 50 ticks, including conversations,
  reflections, position changes, and at least one restart/load cycle.
- No `ProgramLimitExceeded`, OOM, autosave circuit opening, or save-version loss.
- New-format snapshot size at tick 30,000 must be no more than 2× its size at
  tick 1,000; historical memories live in normalized tables, not the JSON field.
- RSS between ticks 10,000 and 30,000 must stay within a predeclared 10% steady-
  state band after GC, excluding database cache. If hot/cold memory is deferred,
  report this criterion as intentionally unmet rather than hiding it.
- Rows touched by an autosave must be proportional to state changed since the
  previous save, not total session history. In a static interval, memory inserts
  and deletes must both be zero.
- Load must reproduce memory count, contents, citations, last-access times,
  planning state, positions, dashboard tail, and relationship revision exactly.

### Benchmark D — failure containment

- Inject an artificially low snapshot budget.
- Assert one early typed failure, preservation of the last successful save and
  save version, runtime resume according to prior state, one bounded diagnostic,
  and no repeated serialization/DB attempt at later autosave multiples until the
  circuit reset condition is met.
- Include multibyte Korean content and one oversized single diagnostic field.

### Database before/after evidence

Capture `pg_stat_user_tables`, relation/TOAST sizes, WAL LSN delta, checkpoint and
temporary-file counters, and container block I/O over equal 5,000-tick windows.
The acceptance result should show no full-projection delete/reinsert cycle and no
growth resembling the current millions of deletes, billions of sequential tuples
read, or hundreds of GB of block I/O.

## Recommended execution order

1. Implement and regression-test P0-A before restarting a long session.
2. Add P0-B so a future accumulator cannot create the same failure loop.
3. Design and migrate P1-A with schema-versioned dual reads; convert the existing
   near-limit save without loading/redumping it as one giant object.
4. Add P1-B to make truly long sessions memory- and retrieval-bounded without
   deleting history.
5. Apply P2 only as supporting work, then run all four benchmarks and the existing
   backend/session-persistence suite.

This order stops new false data first, prevents a repeated resource spiral second,
and then removes the architectural full-history rewrite without sacrificing the
project's durable-memory contract.
