import type { SpatialAgentState } from "@agent-crossing/shared";

const MAX_BUBBLE_LENGTH = 46;

function truncateBubble(text: string): string {
  const normalized = text.trim();
  return normalized.length > MAX_BUBBLE_LENGTH
    ? `${normalized.slice(0, MAX_BUBBLE_LENGTH - 3)}...`
    : normalized;
}

function stripOuterParentheses(text: string): string {
  const normalized = text.trim();
  return normalized.startsWith("(") && normalized.endsWith(")")
    ? normalized.slice(1, -1).trim()
    : normalized;
}

export function agentBubbleLabel(agent: SpatialAgentState): string {
  const fallback =
    agent.active_minute?.action_content || agent.plan || "잠시 생각을 정리한다";
  const text = truncateBubble(agent.bubble_text || fallback);
  return agent.bubble_kind === "speech"
    ? text
    : `(${stripOuterParentheses(text)})`;
}
