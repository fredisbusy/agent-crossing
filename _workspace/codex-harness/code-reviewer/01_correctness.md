# Correctness

The scheduler correctly submits one cognitive task per active, disjoint dialogue pair, but awaits every task before the next world tick. A slower queued LLM request therefore delays the entire world clock.

Plan generation is serial both in the runtime list comprehension and in the coordinator-wide lock. Parallel threads alone would not change that behavior safely.
