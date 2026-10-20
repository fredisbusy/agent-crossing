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

export * from "./world";
