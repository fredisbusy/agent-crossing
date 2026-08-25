# Security review

- PostgreSQL host publishing is restricted to `127.0.0.1` for local Prisma and FastAPI access.
- Credentials remain environment-configurable; production must override local defaults.
- Session mutation names and UUIDs are validated at the API boundary.
- Save/load operations are serialized by an application lifecycle lock.
- Raw prompts, provider responses, credentials, and unbounded payloads are excluded from the persisted cognitive-log projection.
- Private memories are not returned from the session-list API.

