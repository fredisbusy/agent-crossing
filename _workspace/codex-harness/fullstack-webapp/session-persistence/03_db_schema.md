# Database schema

The canonical schema is `packages/database/prisma/schema.prisma`. The checked-in SQL migration includes pgvector and constraints Prisma cannot express directly. FastAPI models are consumers of this schema, never migration owners.

