export type AgentId = string;

export interface AgentPosition {
  x: number;
  y: number;
}

export interface SpatialAgentState {
  agent_id: AgentId;
  name: string;
  tile_position: AgentPosition;
  position: AgentPosition;
  destination: string | null;
  current_action: string;
  plan: string;
  route_remaining: number;
  active_day: PlanItemState | null;
  active_hourly: PlanItemState | null;
  active_minute: PlanItemState | null;
  day_plan: PlanItemState[];
  bubble_kind: "speech" | "thought" | "action";
  bubble_text: string;
}

export interface PlanItemState {
  start_time: string;
  end_time: string;
  location: string;
  action_content: string;
}

export interface SpatialWorldSnapshot {
  session_id: string | null;
  revision: number;
  map_id: string;
  agents: SpatialAgentState[];
  current_time: string | null;
  turn: number;
  scheduler_running: boolean;
  planning_error: string | null;
}

export interface GameSessionSummary {
  id: string;
  name: string;
  status: "ACTIVE" | "SAVED" | "ERROR";
  map_id: string;
  world_time: string;
  turn: number;
  revision: number;
  save_version: number;
  created_at: string;
  saved_at: string;
}

export interface GameSessionList {
  current_session_id: string | null;
  sessions: GameSessionSummary[];
}

export interface DashboardMemory {
  id: number;
  node_type: "OBSERVATION" | "REFLECTION" | "PLAN";
  citations: number[] | null;
  content: string;
  created_at: string;
  last_accessed_at: string;
  importance: number;
}

export interface DashboardMemoryPage {
  items: DashboardMemory[];
  total: number;
  filtered_total: number;
  has_more: boolean;
  next_cursor: number | null;
  snapshot_memory_max_id: number | null;
}

export interface DashboardReflectionStatus {
  accumulated_importance: number;
  threshold: number;
  reflection_total: number;
  last_reflection_at: string | null;
}

export interface DashboardRelationshipEvidence {
  source: "persona" | "memory";
  content: string;
  memory_id: number | null;
  node_type: DashboardMemory["node_type"] | null;
  importance: number | null;
  created_at: string | null;
}

export interface DashboardRelationship {
  target_agent_id: AgentId;
  target_name: string;
  measurement: "modeled_v1";
  metrics: DashboardRelationshipMetrics;
  status_label: DashboardRelationshipStatusLabel;
  revision: number;
  updated_at: string | null;
  last_interaction_at: string | null;
  summary: string | null;
  summary_status: "available" | "no_explicit_evidence";
  evidence_total: number;
  has_more_evidence: boolean;
  recent_events: DashboardRelationshipEvent[];
  evidence: DashboardRelationshipEvidence[];
}

export type DashboardRelationshipStatusLabel =
  | "긴장된 관계"
  | "불신하는 관계"
  | "거리감 있는 관계"
  | "아직 낯선 사이"
  | "가깝고 신뢰하는 관계"
  | "인간적으로 호감 있는 관계"
  | "신뢰하는 관계"
  | "알아가는 관계";

export interface DashboardRelationshipMetrics {
  familiarity: number;
  trust: number;
  affinity: number;
  tension: number;
  romantic_interest: number;
}

export type DashboardRelationshipEventType =
  | "DIALOGUE_COMPLETED"
  | "HELP_GIVEN"
  | "HELP_RECEIVED"
  | "PERSONAL_DISCLOSURE_RECEIVED"
  | "COMPLIMENT_RECEIVED"
  | "PROMISE_MADE"
  | "PROMISE_KEPT"
  | "PROMISE_BROKEN"
  | "CONFLICT"
  | "INSULT_RECEIVED"
  | "APOLOGY_ACCEPTED"
  | "ROMANTIC_INTEREST_RECOGNIZED"
  | "ROMANTIC_GESTURE_WELCOMED"
  | "ROMANTIC_BOUNDARY_SET";

export interface DashboardRelationshipEvent {
  id: string;
  event_type: DashboardRelationshipEventType;
  occurred_at: string;
  familiarity_delta: number;
  trust_delta: number;
  affinity_delta: number;
  tension_delta: number;
  romantic_interest_delta: number;
  rule_version: string;
}

export interface DashboardAgent {
  agent_id: AgentId;
  name: string;
  age: number;
  gender: string;
  traits: string[];
  persona: string[];
  current_action: string;
  destination: string | null;
  current_location_path: string | null;
  current_location_source: "map" | "arrival" | "interior" | "unknown";
  tile_position: AgentPosition;
  route_remaining: number;
  bubble_kind: "speech" | "thought" | "action";
  bubble_text: string;
  current_plan_context: string[];
  active_day: PlanItemState | null;
  active_hourly: PlanItemState | null;
  active_minute: PlanItemState | null;
  day_plan: PlanItemState[];
  last_replan_reason: string | null;
  memory_total: number;
  memory_has_more: boolean;
  reflection_status: DashboardReflectionStatus;
  relationships: DashboardRelationship[];
  memories: DashboardMemory[];
}

export interface DashboardEvent {
  sequence: number;
  turn: number;
  occurred_at: string;
  agent_id: AgentId;
  agent_name: string;
  reply: string;
  silent_reason: string;
  parse_failure: boolean;
  decision_reason: string;
  action_summary: string;
}

export interface DashboardWorld {
  available: boolean;
  revision: number;
  turn: number;
  current_time: string | null;
  scheduler_running: boolean;
  cognitive_active: boolean;
  effective_time_step_seconds: number;
  cognitive_runtime_error: string | null;
  planning_error: string | null;
  snapshot_generated_at: string;
}

export interface DashboardState {
  world: DashboardWorld;
  agents: DashboardAgent[];
  events: DashboardEvent[];
  oldest_sequence: number;
  latest_sequence: number;
}
