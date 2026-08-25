# Session persistence input

- Domain: Agent Crossing generative-agent RPG session persistence
- Database: PostgreSQL 16 with pgvector on OrbStack
- Schema owner: Prisma ORM schema and migrations
- Runtime access: FastAPI uses SQLAlchemy/psycopg against the Prisma-managed schema
- User flows: create a new session, save the current session, list saved sessions, load a saved session
- Required state: world clock/counters, character persona and movement, full plan cache, private memories and citations, reflection counter, dialogue state, encounter cooldown, and sanitized cognitive logs
- Scope decision: one `GameSession` is one overwritable RPG save slot. Multi-checkpoint saves and execution epochs remain compatible future extensions.

