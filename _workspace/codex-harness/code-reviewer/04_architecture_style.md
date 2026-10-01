# Architecture and style

Any planner parallelization must separate per-agent generation from a short, authoritative validation/install critical section. Keep atomic plan coverage and the SPEC world-clock gate intact. Add bounded concurrency rather than unbounded worker fan-out.
