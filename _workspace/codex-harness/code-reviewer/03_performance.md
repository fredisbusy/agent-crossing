# Performance

- `runtime.py:757-768` generates plans sequentially for the whole roster.
- `planning/lifecycle.py:328-336` holds a coordinator-wide lock over LLM-backed planning, so naive fan-out remains serial.
- Dialogue pairs are concurrently submitted, then joined at `runtime.py:660-692`.
- Organic disruption work is bounded to one changed observation per tick, not one call per agent; its worker is nevertheless joined before the next tick.
- The repository has no configured `OLLAMA_NUM_PARALLEL` or context setting. Model-server settings and latency need live verification.
