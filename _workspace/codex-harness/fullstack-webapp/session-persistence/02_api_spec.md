# Session API

- `GET /sessions` -> current session ID plus bounded saved-session summaries.
- `POST /sessions` `{ name }` -> create, persist, and switch to a fresh 06:00 session.
- `POST /sessions/current/save` `{ expected_save_version }` -> atomically overwrite the current slot.
- `POST /sessions/{session_id}/load` -> validate, restore, and switch to a saved slot.

Mutation conflicts return 409. Invalid input returns 422. Missing saves return 404. Persistence unavailability returns 503.

