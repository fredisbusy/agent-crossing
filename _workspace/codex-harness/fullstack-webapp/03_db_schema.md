# Database impact

## 2026-08-24 mock-only UI remediation

No database schema or migration is required. This work changes frontend presentation, scene lifecycle, input handling, and tests only.

## 2026-08-24 cognitive observability dashboard

No migration was added. The MVP reads the real in-process memory stream and keeps the
latest 500 completed cognitive events in a bounded runtime buffer. Persistent history
across backend restarts remains a separate append-only event-journal enhancement.

## 2026-08-24 directional relationship summaries

No migration is required. Summaries are derived at read time from existing persona and
memory data; numeric relationship state is intentionally not persisted or fabricated.
