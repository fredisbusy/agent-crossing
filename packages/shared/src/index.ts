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
}

export interface SpatialWorldSnapshot {
  revision: number;
  map_id: string;
  agents: SpatialAgentState[];
}
