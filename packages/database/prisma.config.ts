import { defineConfig } from "prisma/config";

const databaseUrl =
  process.env.PRISMA_DATABASE_URL ??
  "postgresql://agent:agent@127.0.0.1:5432/agent_crossing";

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
  },
  datasource: {
    url: databaseUrl,
  },
});
