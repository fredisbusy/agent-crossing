CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN
  CREATE TYPE "GameSessionStatus" AS ENUM ('ACTIVE', 'SAVED', 'ERROR');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE "PlanLevel" AS ENUM ('DAY', 'HOURLY', 'MINUTE');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE "MemoryNodeType" AS ENUM ('OBSERVATION', 'REFLECTION', 'PLAN');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS "vector_memories" (
  "id" SERIAL PRIMARY KEY,
  "description" TEXT NOT NULL,
  "importance" INTEGER NOT NULL,
  "embedding" vector(1024) NOT NULL,
  "created_at" TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "game_sessions" (
  "id" UUID PRIMARY KEY,
  "name" VARCHAR(80) NOT NULL,
  "status" "GameSessionStatus" NOT NULL DEFAULT 'SAVED',
  "map_id" VARCHAR(80) NOT NULL,
  "world_time" TIMESTAMP(6) NOT NULL,
  "turn" BIGINT NOT NULL,
  "revision" BIGINT NOT NULL,
  "parse_failures" INTEGER NOT NULL DEFAULT 0,
  "silent_turns" INTEGER NOT NULL DEFAULT 0,
  "last_dialogue_end_at" TIMESTAMP(6),
  "scheduler_was_running" BOOLEAN NOT NULL DEFAULT TRUE,
  "planning_error" TEXT,
  "schema_version" INTEGER NOT NULL DEFAULT 1,
  "save_version" INTEGER NOT NULL DEFAULT 1,
  "snapshot" JSONB NOT NULL,
  "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "saved_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "game_sessions_name_check" CHECK (char_length(btrim("name")) BETWEEN 1 AND 80),
  CONSTRAINT "game_sessions_version_check" CHECK ("schema_version" > 0 AND "save_version" > 0)
);

CREATE TABLE "session_characters" (
  "id" UUID PRIMARY KEY,
  "session_id" UUID NOT NULL REFERENCES "game_sessions"("id") ON DELETE CASCADE,
  "agent_id" VARCHAR(80) NOT NULL,
  "name" VARCHAR(120) NOT NULL,
  "persona_snapshot" JSONB NOT NULL,
  "tile_x" INTEGER NOT NULL,
  "tile_y" INTEGER NOT NULL,
  "goal_x" INTEGER,
  "goal_y" INTEGER,
  "destination_path" TEXT,
  "route" JSONB NOT NULL,
  "current_action" TEXT NOT NULL,
  "plan" TEXT NOT NULL,
  "current_plan_context" JSONB NOT NULL,
  "reflection_accumulated_importance" INTEGER NOT NULL DEFAULT 0,
  "last_replan_reason" TEXT,
  CONSTRAINT "session_characters_session_agent_key" UNIQUE ("session_id", "agent_id"),
  CONSTRAINT "session_characters_reflection_check" CHECK ("reflection_accumulated_importance" >= 0)
);

CREATE TABLE "session_memories" (
  "id" UUID PRIMARY KEY,
  "character_id" UUID NOT NULL REFERENCES "session_characters"("id") ON DELETE CASCADE,
  "runtime_local_id" INTEGER NOT NULL,
  "node_type" "MemoryNodeType" NOT NULL,
  "content" TEXT NOT NULL,
  "importance" INTEGER NOT NULL,
  "embedding" vector(1024) NOT NULL,
  "game_created_at" TIMESTAMP(6) NOT NULL,
  "last_accessed_at" TIMESTAMP(6) NOT NULL,
  "inserted_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "session_memories_character_local_key" UNIQUE ("character_id", "runtime_local_id"),
  CONSTRAINT "session_memories_importance_check" CHECK ("importance" BETWEEN 1 AND 10)
);

CREATE TABLE "session_memory_citations" (
  "memory_id" UUID NOT NULL REFERENCES "session_memories"("id") ON DELETE CASCADE,
  "cited_memory_id" UUID NOT NULL REFERENCES "session_memories"("id") ON DELETE CASCADE,
  "position" INTEGER NOT NULL,
  PRIMARY KEY ("memory_id", "cited_memory_id"),
  CONSTRAINT "session_memory_citations_no_self_check" CHECK ("memory_id" <> "cited_memory_id"),
  CONSTRAINT "session_memory_citations_position_check" CHECK ("position" >= 0)
);

CREATE TABLE "session_plan_items" (
  "id" UUID PRIMARY KEY,
  "character_id" UUID NOT NULL REFERENCES "session_characters"("id") ON DELETE CASCADE,
  "parent_id" UUID REFERENCES "session_plan_items"("id") ON DELETE CASCADE,
  "level" "PlanLevel" NOT NULL,
  "ordinal" INTEGER NOT NULL,
  "start_time" TIMESTAMP(6) NOT NULL,
  "end_time" TIMESTAMP(6) NOT NULL,
  "location" TEXT NOT NULL,
  "action_content" TEXT NOT NULL,
  "is_active" BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT "session_plan_items_character_level_ordinal_key" UNIQUE ("character_id", "level", "ordinal"),
  CONSTRAINT "session_plan_items_time_check" CHECK ("end_time" > "start_time"),
  CONSTRAINT "session_plan_items_ordinal_check" CHECK ("ordinal" >= 0)
);

CREATE TABLE "session_dialogue_states" (
  "session_id" UUID PRIMARY KEY REFERENCES "game_sessions"("id") ON DELETE CASCADE,
  "is_active" BOOLEAN NOT NULL,
  "turn_index" INTEGER NOT NULL,
  "dialogue_turn_window" INTEGER,
  "dialogue_target_turns" INTEGER NOT NULL,
  "dialogue_turns_taken" INTEGER NOT NULL,
  "dialogue_goal" TEXT,
  "history" JSONB NOT NULL,
  "history_by_agent" JSONB NOT NULL,
  "incoming_queues_by_agent" JSONB NOT NULL,
  CONSTRAINT "session_dialogue_state_counts_check" CHECK (
    "turn_index" >= 0 AND "dialogue_target_turns" >= 2 AND "dialogue_turns_taken" >= 0
  )
);

CREATE TABLE "session_cognitive_logs" (
  "id" BIGSERIAL PRIMARY KEY,
  "session_id" UUID NOT NULL REFERENCES "game_sessions"("id") ON DELETE CASCADE,
  "character_id" UUID REFERENCES "session_characters"("id") ON DELETE SET NULL,
  "sequence" BIGINT NOT NULL,
  "turn" BIGINT NOT NULL,
  "occurred_at" TIMESTAMP(6) NOT NULL,
  "agent_id" VARCHAR(80) NOT NULL,
  "agent_name" VARCHAR(120) NOT NULL,
  "reply" TEXT NOT NULL,
  "silent_reason" TEXT NOT NULL,
  "parse_failure" BOOLEAN NOT NULL,
  "thought" TEXT NOT NULL,
  "model_thought" TEXT NOT NULL,
  "self_critique" TEXT NOT NULL,
  "decision_reason" TEXT NOT NULL,
  "action_summary" TEXT NOT NULL,
  "decision_process" JSONB NOT NULL,
  "governance_trace" JSONB NOT NULL,
  CONSTRAINT "session_cognitive_logs_session_sequence_key" UNIQUE ("session_id", "sequence")
);

CREATE INDEX "game_sessions_status_saved_at_idx" ON "game_sessions"("status", "saved_at" DESC);
CREATE INDEX "session_memories_character_created_idx" ON "session_memories"("character_id", "game_created_at" DESC);
CREATE INDEX "session_memories_character_accessed_idx" ON "session_memories"("character_id", "last_accessed_at");
CREATE INDEX "session_plan_items_active_idx" ON "session_plan_items"("character_id", "level", "start_time", "end_time");
CREATE INDEX "session_cognitive_logs_session_sequence_idx" ON "session_cognitive_logs"("session_id", "sequence" DESC);
CREATE INDEX "session_cognitive_logs_character_sequence_idx" ON "session_cognitive_logs"("character_id", "sequence" DESC);

CREATE UNIQUE INDEX "game_sessions_single_active_idx" ON "game_sessions" ((status)) WHERE status = 'ACTIVE';
