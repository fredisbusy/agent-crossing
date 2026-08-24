import type {
  DashboardAgent,
  DashboardEvent,
  DashboardMemory,
  DashboardRelationship,
  DashboardRelationshipEvidence,
  DashboardState,
  PlanItemState,
} from "@agent-crossing/shared";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function parsePlan(value: unknown): PlanItemState | null {
  if (!isRecord(value)) return null;
  return typeof value.start_time === "string" &&
    typeof value.end_time === "string" &&
    typeof value.location === "string" &&
    typeof value.action_content === "string"
    ? {
        start_time: value.start_time,
        end_time: value.end_time,
        location: value.location,
        action_content: value.action_content,
      }
    : null;
}

function parseMemory(value: unknown): DashboardMemory | null {
  if (!isRecord(value)) return null;
  const nodeType = value.node_type;
  const citations = value.citations;
  if (
    typeof value.id !== "number" ||
    !["OBSERVATION", "REFLECTION", "PLAN"].includes(String(nodeType)) ||
    (citations !== null &&
      (!Array.isArray(citations) ||
        !citations.every((item) => typeof item === "number"))) ||
    typeof value.content !== "string" ||
    typeof value.created_at !== "string" ||
    typeof value.last_accessed_at !== "string" ||
    typeof value.importance !== "number"
  ) {
    return null;
  }
  return {
    id: value.id,
    node_type: nodeType as DashboardMemory["node_type"],
    citations: citations as number[] | null,
    content: value.content,
    created_at: value.created_at,
    last_accessed_at: value.last_accessed_at,
    importance: value.importance,
  };
}

function parseRelationshipEvidence(
  value: unknown,
): DashboardRelationshipEvidence | null {
  if (!isRecord(value)) return null;
  if (
    !["persona", "memory"].includes(String(value.source)) ||
    typeof value.content !== "string" ||
    (value.memory_id !== null && typeof value.memory_id !== "number") ||
    (value.node_type !== null &&
      !["OBSERVATION", "REFLECTION", "PLAN"].includes(
        String(value.node_type),
      )) ||
    (value.importance !== null && typeof value.importance !== "number") ||
    (value.created_at !== null && typeof value.created_at !== "string")
  ) {
    return null;
  }
  return {
    source: value.source as DashboardRelationshipEvidence["source"],
    content: value.content,
    memory_id: value.memory_id as number | null,
    node_type: value.node_type as DashboardMemory["node_type"] | null,
    importance: value.importance as number | null,
    created_at: value.created_at as string | null,
  };
}

function parseRelationship(value: unknown): DashboardRelationship | null {
  if (!isRecord(value)) return null;
  const evidence = Array.isArray(value.evidence)
    ? value.evidence.map(parseRelationshipEvidence)
    : null;
  if (
    typeof value.target_agent_id !== "string" ||
    typeof value.target_name !== "string" ||
    (value.affinity_score !== null && typeof value.affinity_score !== "number") ||
    value.measurement !== "not_modeled" ||
    (value.summary !== null && typeof value.summary !== "string") ||
    evidence === null ||
    evidence.some((item) => item === null)
  ) {
    return null;
  }
  return {
    target_agent_id: value.target_agent_id,
    target_name: value.target_name,
    affinity_score: value.affinity_score as number | null,
    measurement: "not_modeled",
    summary: value.summary as string | null,
    evidence: evidence.filter(
      (item): item is DashboardRelationshipEvidence => item !== null,
    ),
  };
}

function parseAgent(value: unknown): DashboardAgent | null {
  if (!isRecord(value) || !isRecord(value.tile_position)) return null;
  const activeDay = value.active_day === null ? null : parsePlan(value.active_day);
  const activeHourly =
    value.active_hourly === null ? null : parsePlan(value.active_hourly);
  const activeMinute =
    value.active_minute === null ? null : parsePlan(value.active_minute);
  const dayPlan = Array.isArray(value.day_plan)
    ? value.day_plan.map(parsePlan)
    : null;
  const memories = Array.isArray(value.memories)
    ? value.memories.map(parseMemory)
    : null;
  const reflection = value.reflection_status;
  const relationships = Array.isArray(value.relationships)
    ? value.relationships.map(parseRelationship)
    : null;
  if (
    typeof value.agent_id !== "string" ||
    typeof value.name !== "string" ||
    typeof value.current_action !== "string" ||
    (value.destination !== null && typeof value.destination !== "string") ||
    typeof value.tile_position.x !== "number" ||
    typeof value.tile_position.y !== "number" ||
    typeof value.route_remaining !== "number" ||
    !["speech", "thought", "action"].includes(String(value.bubble_kind)) ||
    typeof value.bubble_text !== "string" ||
    !isStringArray(value.current_plan_context) ||
    (value.active_day !== null && activeDay === null) ||
    (value.active_hourly !== null && activeHourly === null) ||
    (value.active_minute !== null && activeMinute === null) ||
    dayPlan === null ||
    dayPlan.some((item) => item === null) ||
    memories === null ||
    memories.some((item) => item === null) ||
    !isRecord(reflection) ||
    typeof reflection.accumulated_importance !== "number" ||
    typeof reflection.threshold !== "number" ||
    relationships === null ||
    relationships.some((relationship) => relationship === null)
  ) {
    return null;
  }
  return {
    agent_id: value.agent_id,
    name: value.name,
    current_action: value.current_action,
    destination: value.destination as string | null,
    tile_position: { x: value.tile_position.x, y: value.tile_position.y },
    route_remaining: value.route_remaining,
    bubble_kind: value.bubble_kind as DashboardAgent["bubble_kind"],
    bubble_text: value.bubble_text,
    current_plan_context: value.current_plan_context,
    active_day: activeDay,
    active_hourly: activeHourly,
    active_minute: activeMinute,
    day_plan: dayPlan.filter((item): item is PlanItemState => item !== null),
    reflection_status: {
      accumulated_importance: reflection.accumulated_importance,
      threshold: reflection.threshold,
    },
    relationships: relationships.filter(
      (relationship): relationship is DashboardRelationship =>
        relationship !== null,
    ),
    memories: memories.filter((item): item is DashboardMemory => item !== null),
  };
}

function parseEvent(value: unknown): DashboardEvent | null {
  if (!isRecord(value)) return null;
  const stringFields = [
    "occurred_at",
    "agent_id",
    "agent_name",
    "reply",
    "silent_reason",
    "thought",
    "model_thought",
    "self_critique",
    "decision_reason",
    "action_summary",
  ] as const;
  if (
    typeof value.sequence !== "number" ||
    typeof value.turn !== "number" ||
    typeof value.parse_failure !== "boolean" ||
    stringFields.some((field) => typeof value[field] !== "string") ||
    !isRecord(value.decision_process) ||
    !isRecord(value.governance_trace)
  ) {
    return null;
  }
  return value as unknown as DashboardEvent;
}

export function parseDashboardState(value: unknown): DashboardState | null {
  if (!isRecord(value) || !isRecord(value.world)) return null;
  const world = value.world;
  const agents = Array.isArray(value.agents) ? value.agents.map(parseAgent) : null;
  const events = Array.isArray(value.events) ? value.events.map(parseEvent) : null;
  if (
    typeof world.available !== "boolean" ||
    typeof world.revision !== "number" ||
    typeof world.turn !== "number" ||
    (world.current_time !== null && typeof world.current_time !== "string") ||
    typeof world.scheduler_running !== "boolean" ||
    typeof world.cognitive_active !== "boolean" ||
    typeof world.effective_time_step_seconds !== "number" ||
    (world.cognitive_runtime_error !== null &&
      typeof world.cognitive_runtime_error !== "string") ||
    agents === null ||
    agents.some((agent) => agent === null) ||
    events === null ||
    events.some((event) => event === null) ||
    typeof value.latest_sequence !== "number"
  ) {
    return null;
  }
  return {
    world: {
      available: world.available,
      revision: world.revision,
      turn: world.turn,
      current_time: world.current_time as string | null,
      scheduler_running: world.scheduler_running,
      cognitive_active: world.cognitive_active,
      effective_time_step_seconds: world.effective_time_step_seconds,
      cognitive_runtime_error: world.cognitive_runtime_error as string | null,
    },
    agents: agents.filter((agent): agent is DashboardAgent => agent !== null),
    events: events.filter((event): event is DashboardEvent => event !== null),
    latest_sequence: value.latest_sequence,
  };
}
