import type {
  DashboardAgent,
  DashboardEvent,
  DashboardMemory,
  DashboardMemoryPage,
  DashboardRelationship,
  DashboardRelationshipEvent,
  DashboardRelationshipEvidence,
  DashboardState,
  PlanItemState,
} from "@agent-crossing/shared";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
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
    typeof value.importance !== "number" ||
    typeof value.content_redacted !== "boolean"
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
    content_redacted: value.content_redacted,
  };
}

export function parseDashboardMemoryPage(
  value: unknown,
): DashboardMemoryPage | null {
  if (!isRecord(value) || !Array.isArray(value.items)) return null;
  const items = value.items.map(parseMemory);
  if (
    items.some((item) => item === null) ||
    !isNonNegativeInteger(value.total) ||
    !isNonNegativeInteger(value.filtered_total) ||
    typeof value.has_more !== "boolean" ||
    (value.next_cursor !== null && !isNonNegativeInteger(value.next_cursor)) ||
    (value.snapshot_memory_max_id !== null &&
      !isNonNegativeInteger(value.snapshot_memory_max_id))
  ) {
    return null;
  }
  return {
    items: items.filter((item): item is DashboardMemory => item !== null),
    total: value.total,
    filtered_total: value.filtered_total,
    has_more: value.has_more,
    next_cursor: value.next_cursor as number | null,
    snapshot_memory_max_id: value.snapshot_memory_max_id as number | null,
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
  const metrics = value.metrics;
  const evidence = Array.isArray(value.evidence)
    ? value.evidence.map(parseRelationshipEvidence)
    : null;
  const recentEvents = Array.isArray(value.recent_events)
    ? value.recent_events.map(parseRelationshipEvent)
    : null;
  if (
    typeof value.target_agent_id !== "string" ||
    typeof value.target_name !== "string" ||
    value.measurement !== "modeled_v1" ||
    !isRelationshipMetrics(metrics) ||
    !relationshipStatusLabels.has(String(value.status_label)) ||
    !isNonNegativeInteger(value.revision) ||
    (value.updated_at !== null && !isDateTimeString(value.updated_at)) ||
    (value.last_interaction_at !== null &&
      !isDateTimeString(value.last_interaction_at)) ||
    (value.summary !== null && typeof value.summary !== "string") ||
    !["available", "no_explicit_evidence", "redacted"].includes(
      String(value.summary_status),
    ) ||
    !isNonNegativeInteger(value.evidence_total) ||
    typeof value.has_more_evidence !== "boolean" ||
    recentEvents === null ||
    recentEvents.some((item) => item === null) ||
    evidence === null ||
    evidence.some((item) => item === null)
  ) {
    return null;
  }
  return {
    target_agent_id: value.target_agent_id,
    target_name: value.target_name,
    measurement: "modeled_v1",
    metrics,
    status_label: value.status_label as DashboardRelationship["status_label"],
    revision: value.revision as number,
    updated_at: value.updated_at as string | null,
    last_interaction_at: value.last_interaction_at as string | null,
    summary: value.summary as string | null,
    summary_status:
      value.summary_status as DashboardRelationship["summary_status"],
    evidence_total: value.evidence_total as number,
    has_more_evidence: value.has_more_evidence,
    recent_events: recentEvents.filter(
      (item): item is DashboardRelationshipEvent => item !== null,
    ),
    evidence: evidence.filter(
      (item): item is DashboardRelationshipEvidence => item !== null,
    ),
  };
}

const relationshipStatusLabels = new Set([
  "긴장된 관계",
  "불신하는 관계",
  "거리감 있는 관계",
  "아직 낯선 사이",
  "가깝고 신뢰하는 관계",
  "인간적으로 호감 있는 관계",
  "신뢰하는 관계",
  "알아가는 관계",
]);

function inRange(value: unknown, low: number, high: number): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    value >= low &&
    value <= high
  );
}

function inIntegerRange(
  value: unknown,
  low: number,
  high: number,
): value is number {
  return Number.isInteger(value) && inRange(value, low, high);
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isDateTimeString(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isRelationshipMetrics(
  value: unknown,
): value is DashboardRelationship["metrics"] {
  return (
    isRecord(value) &&
    inIntegerRange(value.familiarity, 0, 100) &&
    inIntegerRange(value.trust, -100, 100) &&
    inIntegerRange(value.affinity, -100, 100) &&
    inIntegerRange(value.tension, 0, 100) &&
    inIntegerRange(value.romantic_interest, 0, 100)
  );
}

const relationshipEventTypes = new Set([
  "DIALOGUE_COMPLETED",
  "HELP_GIVEN",
  "HELP_RECEIVED",
  "PERSONAL_DISCLOSURE_RECEIVED",
  "COMPLIMENT_RECEIVED",
  "PROMISE_MADE",
  "PROMISE_KEPT",
  "PROMISE_BROKEN",
  "CONFLICT",
  "INSULT_RECEIVED",
  "APOLOGY_ACCEPTED",
  "ROMANTIC_INTEREST_RECOGNIZED",
  "ROMANTIC_GESTURE_WELCOMED",
  "ROMANTIC_BOUNDARY_SET",
]);

function parseRelationshipEvent(
  value: unknown,
): DashboardRelationshipEvent | null {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    !relationshipEventTypes.has(String(value.event_type)) ||
    !isDateTimeString(value.occurred_at) ||
    !inIntegerRange(value.familiarity_delta, -100, 100) ||
    !inIntegerRange(value.trust_delta, -100, 100) ||
    !inIntegerRange(value.affinity_delta, -100, 100) ||
    !inIntegerRange(value.tension_delta, -100, 100) ||
    !inIntegerRange(value.romantic_interest_delta, -100, 100) ||
    value.rule_version !== "relationship-v1"
  )
    return null;
  return value as unknown as DashboardRelationshipEvent;
}

function parseAgent(value: unknown): DashboardAgent | null {
  if (!isRecord(value) || !isRecord(value.tile_position)) return null;
  const activeDay =
    value.active_day === null ? null : parsePlan(value.active_day);
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
    (value.current_location_path !== null &&
      typeof value.current_location_path !== "string") ||
    !["map", "arrival", "unknown"].includes(
      String(value.current_location_source),
    ) ||
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
    (value.last_replan_reason !== null &&
      typeof value.last_replan_reason !== "string") ||
    !isNonNegativeInteger(value.memory_total) ||
    typeof value.memory_has_more !== "boolean" ||
    memories === null ||
    memories.some((item) => item === null) ||
    !isRecord(reflection) ||
    typeof reflection.accumulated_importance !== "number" ||
    typeof reflection.threshold !== "number" ||
    !isNonNegativeInteger(reflection.reflection_total) ||
    (reflection.last_reflection_at !== null &&
      !isDateTimeString(reflection.last_reflection_at)) ||
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
    current_location_path: value.current_location_path as string | null,
    current_location_source:
      value.current_location_source as DashboardAgent["current_location_source"],
    tile_position: { x: value.tile_position.x, y: value.tile_position.y },
    route_remaining: value.route_remaining,
    bubble_kind: value.bubble_kind as DashboardAgent["bubble_kind"],
    bubble_text: value.bubble_text,
    current_plan_context: value.current_plan_context,
    active_day: activeDay,
    active_hourly: activeHourly,
    active_minute: activeMinute,
    day_plan: dayPlan.filter((item): item is PlanItemState => item !== null),
    last_replan_reason: value.last_replan_reason as string | null,
    memory_total: value.memory_total,
    memory_has_more: value.memory_has_more,
    reflection_status: {
      accumulated_importance: reflection.accumulated_importance,
      threshold: reflection.threshold,
      reflection_total: reflection.reflection_total,
      last_reflection_at: reflection.last_reflection_at as string | null,
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
    "decision_reason",
    "action_summary",
  ] as const;
  if (
    typeof value.sequence !== "number" ||
    typeof value.turn !== "number" ||
    typeof value.parse_failure !== "boolean" ||
    stringFields.some((field) => typeof value[field] !== "string")
  ) {
    return null;
  }
  return value as unknown as DashboardEvent;
}

export function parseDashboardEvents(value: unknown): DashboardEvent[] | null {
  if (!Array.isArray(value)) return null;
  const events = value.map(parseEvent);
  return events.some((event) => event === null)
    ? null
    : events.filter((event): event is DashboardEvent => event !== null);
}

export function parseDashboardState(value: unknown): DashboardState | null {
  if (!isRecord(value) || !isRecord(value.world)) return null;
  const world = value.world;
  const agents = Array.isArray(value.agents)
    ? value.agents.map(parseAgent)
    : null;
  const events = Array.isArray(value.events)
    ? value.events.map(parseEvent)
    : null;
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
    (world.planning_error !== null &&
      typeof world.planning_error !== "string") ||
    !isDateTimeString(world.snapshot_generated_at) ||
    agents === null ||
    agents.some((agent) => agent === null) ||
    events === null ||
    events.some((event) => event === null) ||
    !isNonNegativeInteger(value.oldest_sequence) ||
    !isNonNegativeInteger(value.latest_sequence)
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
      planning_error: world.planning_error as string | null,
      snapshot_generated_at: world.snapshot_generated_at,
    },
    agents: agents.filter((agent): agent is DashboardAgent => agent !== null),
    events: events.filter((event): event is DashboardEvent => event !== null),
    oldest_sequence: value.oldest_sequence,
    latest_sequence: value.latest_sequence,
  };
}
