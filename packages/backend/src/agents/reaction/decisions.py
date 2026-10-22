from dataclasses import replace

from llm.guardrails.similarity import (
    SEMANTIC_HARD_BLOCK_THRESHOLD,
    SEMANTIC_SOFT_PENALTY_THRESHOLD,
    SemanticOverlapCheck,
)

from .contracts import (
    ReactionDecision,
    ReactionIntent,
    ReactionUtterance,
)


def build_reaction_decision(
    *,
    intent: ReactionIntent,
    utterance_result: ReactionUtterance,
) -> ReactionDecision:
    return ReactionDecision(
        should_react=True,
        reaction=utterance_result.utterance,
        reason=(utterance_result.reason or intent.reason).strip() or "n/a",
        end_dialogue=utterance_result.end_dialogue or intent.end_dialogue,
        thought=(utterance_result.thought or intent.thought).strip(),
        critique=(utterance_result.critique or intent.critique).strip(),
        trace=utterance_result.trace,
    )


def decorate_decision_trace(
    *,
    decision: ReactionDecision,
    partner_retry_count: int,
    semantic_retry_count: int,
    semantic_check: SemanticOverlapCheck,
    combined_fallback_reason: str = "",
) -> ReactionDecision:
    return replace(
        decision,
        trace=replace(
            decision.trace,
            partner_retry_count=partner_retry_count,
            semantic_retry_count=semantic_retry_count,
            max_semantic_similarity=semantic_check.max_similarity,
            semantic_retry_trigger=semantic_check.trigger,
            semantic_hard_threshold=SEMANTIC_HARD_BLOCK_THRESHOLD,
            semantic_soft_threshold=SEMANTIC_SOFT_PENALTY_THRESHOLD,
            combined_fallback_reason=combined_fallback_reason,
        ),
    )
