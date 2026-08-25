# Performance review

- Session list: index `savedAt DESC`.
- Character lookup: unique `(sessionId, agentId)`.
- Plan lookup: `(characterId, level, startTime, endTime)`.
- Memory timeline: `(characterId, gameCreatedAt DESC)`.
- Log tail: `(sessionId, sequence DESC)` and `(characterId, sequence DESC)`.
- Save uses one short transaction and replaces bounded projections after a quiescent in-memory snapshot.
- Do not add a vector ANN index yet: the authoritative retrieval formula also needs recency and importance, and current per-character volume is small.

