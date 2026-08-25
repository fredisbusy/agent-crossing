export type AgentId = string;

export interface AgentPosition {
  x: number;
  y: number;
}

export interface WorldAgentState {
  agentId: AgentId;
  position: AgentPosition;
  currentAction: string;
  currentPlanItem: string | null;
  dialogue: string | null;
  emoji: string | null;
  timestamp: string;
}

export interface WorldMapPoint {
  x: number;
  y: number;
}

export interface WorldMapBounds extends WorldMapPoint {
  width: number;
  height: number;
}

export interface WorldLocation extends WorldMapBounds {
  id: string;
  name: string;
  kind: string;
  locationPath: string;
  color: string;
}

export interface WorldInteractable extends WorldMapPoint {
  id: string;
  name: string;
  kind: string;
  locationPath: string;
  affordances: string[];
}

export interface WorldSpawn extends WorldMapPoint {
  id: string;
  agentId: AgentId;
  color: string;
}

export interface WorldMapDefinition {
  id: string;
  name: string;
  width: number;
  height: number;
  tileWidth: number;
  tileHeight: number;
  locations: WorldLocation[];
  interactables: WorldInteractable[];
  spawns: WorldSpawn[];
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

export interface DashboardReflectionStatus {
  accumulated_importance: number;
  threshold: number;
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
  affinity_score: number | null;
  measurement: "not_modeled";
  summary: string | null;
  evidence: DashboardRelationshipEvidence[];
}

export interface DashboardAgent {
  agent_id: AgentId;
  name: string;
  current_action: string;
  destination: string | null;
  tile_position: AgentPosition;
  route_remaining: number;
  bubble_kind: "speech" | "thought" | "action";
  bubble_text: string;
  current_plan_context: string[];
  active_day: PlanItemState | null;
  active_hourly: PlanItemState | null;
  active_minute: PlanItemState | null;
  day_plan: PlanItemState[];
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
  thought: string;
  model_thought: string;
  self_critique: string;
  decision_reason: string;
  action_summary: string;
  decision_process: Record<string, unknown>;
  governance_trace: Record<string, unknown>;
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
}

export interface DashboardState {
  world: DashboardWorld;
  agents: DashboardAgent[];
  events: DashboardEvent[];
  latest_sequence: number;
}
