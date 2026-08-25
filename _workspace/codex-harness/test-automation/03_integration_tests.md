# Integration tests

`packages/backend/tests/test_session_persistence.py` contains an opt-in PostgreSQL test guarded by `RUN_DATABASE_TESTS=1`. It writes a uniquely named session, asserts normalized character/memory rows, verifies JSON snapshot load, checks stale optimistic versions, then deletes only its own session.

