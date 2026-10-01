# Performance review: Agent Crossing long-running slowdown

## Review verdict

**Approved with mandatory attribution wording below.** The profiling, bottleneck,
optimization, and benchmark lanes converge on one coherent causal chain. No
optimized build was produced or benchmarked; this run establishes diagnosis and
post-fix acceptance criteria only.

The dominant Agent Crossing cause was a directed-pair perception deduplication
bug that concentrated repeated observations in the first resident, followed by
an architectural amplifier: each autosave copied the entire unbounded memory
history and its 1,024-float embeddings into a monolithic JSON snapshot and rebuilt
the full normalized projection. Once the snapshot exceeded PostgreSQL's JSONB
array-element limit, the same deterministic failure was retried every 50 turns,
with the runtime paused and save work growing from tens of seconds to minutes.

## Final ranked causes

| Rank | Cause | Evidence status | Likely contribution |
|---:|---|---|---|
| 1 | Observer-only `_last_perceived_action` key while iterating directed resident pairs | Direct code defect plus matching DB skew; exact historical per-tick frequency is a very high-confidence inference | Created the abnormal memory growth and first-resident concentration |
| 2 | Whole-history JSON snapshot plus full delete/reinsert projection on every autosave | Direct code, snapshot decomposition, and table statistics | Largest CPU/RAM allocation and PostgreSQL write-amplification mechanism |
| 3 | No circuit breaker after deterministic JSONB size failure | 384 backend failures, fixed save version, payload/timing growth | Repeated long simulation freezes and continued allocator, WAL, checkpoint, and I/O pressure |
| 4 | Cascade/FK scan cost, TOAST churn, and retained relation space | Direct schema/statistics; exact per-statement share is inferred | Strong database-side amplifier, not the originating defect |
| 5 | Unbounded backend resources and an OOM event flag | `OOMKilled=true` is direct metadata; timestamp, RSS, and allocation stack are unavailable | Corroborates memory pressure but does not prove the final graceful shutdown was OOM-driven |
| 6 | Other running containers after backend shutdown | Direct short post-stop samples | Explains current residual CPU load, not the historical Agent Crossing persistence failure |
| 7 | Rotated error logs and build cache | Direct size/configuration evidence | Secondary; logs are a bounded symptom and build cache is disk, not RAM |

## Arithmetic and evidence reconciliation

- Failed autosaves: turns 10,750 through 29,900 inclusive at 50-turn intervals
  yield `(29,900 - 10,750) / 50 + 1 = 384`. The plan's “following 383 retries”
  correctly excludes the first failure.
- Snapshot growth: `795,187,992 - 295,437,753 = 499,750,239` bytes/characters
  over 19,200 turns, or about 26.0 KB per turn. The estimated 20,743-byte repeated
  observation records account for about 398 MB of that interval; the remainder is
  consistent with other content/reflection growth, but that split is inferential.
- Resident skew: `10,265 / 12,736 = 80.6%`; 10,239 of those records are
  observations. This matches the code defect's predicted first-roster-resident
  concentration.
- The reported 295,437,753-byte JSON form, approximately 281 MiB JSON text, and
  157 MB compressed/toasted JSONB column are different representations of the
  same saved state, not contradictory measurements. The whole document can exceed
  268,435,455 bytes while a prior save succeeds because the observed PostgreSQL
  error applies to a JSONB array element/container; the later `characters` array
  crossed that boundary.
- Backend logs count 384 autosave failures while PostgreSQL logs count 382 limit
  errors. This does not invalidate the retry count: some backend failures may not
  have reached the same PostgreSQL error/log surface, and the logs are rotated.
- The 65 GB WAL and roughly 407 GB read / 262 GB write counters are cumulative
  since the stated reset/container lifetime. They strongly demonstrate write
  amplification but cannot be assigned wholly to the 384 failed transactions.

## Mandatory corrections for the user-facing synthesis

1. **Do not say the final backend stop was caused by OOM.** The final exit was
   graceful (`ExitCode=0`). `OOMKilled=true` establishes an OOM event during the
   container run, but its time and victim allocation are unknown.
2. **Do not attribute OrbStack's 19.3 GB peak entirely to Agent Crossing.** It is
   the aggregate VM/helper peak across containers. The giant snapshot copy path
   makes Agent Crossing memory pressure highly plausible, but no historical
   per-process RSS trace exists.
3. **Do not present cumulative WAL/block I/O as exact per-session or failed-save
   totals.** Use them as workload/amplification indicators. The database contains
   no competing application workload, but maintenance, successful saves, and the
   diagnostic queries also contribute.
4. **Separate simulation freeze from whole-machine/API freeze.** Pausing the
   stream and scheduler during save directly freezes world progress. Host/API
   unresponsiveness is supported by timeouts and resource pressure but its exact
   CPU/RSS attribution was not captured live.
5. **Keep current unrelated CPU separate from the historical diagnosis.** After
   Agent Crossing stopped, `fast-trade-scanner` sampled at roughly 25-99% CPU and
   `local-sokoban-agent` at roughly 42-43%. They can make the Mac feel busy now;
   the samples do not establish their relative contribution during the prior
   four-day Agent Crossing run.
6. **Do not claim a measured improvement.** `04_benchmark_results.md` is a
   baseline and acceptance specification. No production fix, cleanup, vacuum,
   restart, or post-fix soak benchmark was performed.

## Remediation and regression gate review

The proposed order is sound: fix the directed-pair key first; add a snapshot
budget and retry circuit breaker; then make normalized memory/pgvector storage
authoritative and incremental; finally bound in-process hot memory. Adding the
missing citation FK index is worthwhile containment, but it must not replace the
incremental persistence redesign.

Before restarting a long session, the minimum regression gate is a static
three- and ten-agent test proving directed-pair warm-up converges and unchanged
ticks add zero observations. Completion requires the proposed 30,000-tick soak
with stable RSS, bounded snapshot size, autosave P95 below 2 seconds, stable WAL
and block I/O per 1,000 ticks, no retry storm, and exact restore/citation behavior.

## Bottom line

The best-supported explanation is not “PostgreSQL became large” and not “logs
filled the disk.” A perception-cache key bug generated a pathological embedded
memory stream; whole-state persistence multiplied its cost; and an unbounded
autosave retry loop repeatedly exercised the failing path. PostgreSQL scans,
TOAST/WAL churn, and OOM pressure were consequential amplifiers. Separately, the
currently running scanner and Sokoban containers explain why the computer may
still feel CPU-busy after Agent Crossing has stopped.
