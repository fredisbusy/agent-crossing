from dataclasses import replace
from typing import Literal, Protocol, cast

import numpy as np
from typing_extensions import TypedDict

from llm import prompt_builders
from llm.clients.types import (
    LlmGenerateOptions,
    LlmOutputTruncatedError,
    LlmStructuredOutputError,
)
from llm.guardrails.similarity import (
    EmbeddingEncoder,
    SEMANTIC_HARD_BLOCK_THRESHOLD,
    SEMANTIC_SOFT_PENALTY_THRESHOLD,
    SemanticOverlapCheck,
    embed_sentences,
    exceeds_ngram_overlap_threshold,
    latest_partner_utterance,
    recent_dialogue_sentences,
    recent_self_utterances,
    semantic_overlap_check,
)
from llm.governance.parsing import parse_reaction_intent, parse_reaction_utterance
from llm.language_policy import korean_text_or_fallback
from llm.structured_outputs import ReactionIntentOutput, ReactionUtteranceOutput

from ..graph_support import GRAPH_END, GRAPH_START, GRAPH_STATE_FACTORY
from .contracts import (
    GenerateClient,
    ReactionDecision,
    ReactionDecisionInput,
    ReactionDecisionTrace,
    ReactionIntent,
    ReactionUtterance,
)

REACTION_INTENT_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.35,
    top_p=0.92,
    num_predict=512,
    repeat_penalty=1.1,
    presence_penalty=0.2,
    frequency_penalty=0.4,
)

REACTION_UTTERANCE_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.35,
    top_p=0.92,
    num_predict=512,
    repeat_penalty=1.1,
    presence_penalty=0.2,
    frequency_penalty=0.4,
)


class ReactionGraphBuilder(Protocol):
    def add_node(self, node: str, action: object) -> None: ...

    def add_edge(self, start_key: object, end_key: object) -> None: ...

    def add_conditional_edges(
        self,
        source: str,
        path: object,
        path_map: dict[str, object],
    ) -> None: ...

    def compile(self) -> "ReactionGraphInvoker": ...


class ReactionGraphState(TypedDict):
    input: ReactionDecisionInput
    system_prompt: str
    intent_prompt: str
    intent: ReactionIntent
    utterance_prompt: str
    working_prompt: str
    recent_sentences: list[str]
    partner_utterance: str
    partner_retry_count: int
    semantic_history: list[str]
    semantic_history_embeddings: list[tuple[str, np.ndarray]]
    semantic_retry_count: int
    overlap_retry_count: int
    semantic_check: SemanticOverlapCheck
    semantic_status: Literal["retry", "continue", "final"]
    overlap_status: Literal["retry", "final"]
    utterance_result: ReactionUtterance
    decision: ReactionDecision


class ReactionGraphInvoker(Protocol):
    def invoke(self, input: ReactionGraphState) -> ReactionGraphState: ...


class StateGraphFactory(Protocol):
    def __call__(
        self, state_schema: type["ReactionGraphState"]
    ) -> ReactionGraphBuilder: ...


STATE_GRAPH = cast(StateGraphFactory, GRAPH_STATE_FACTORY)


class ReactionGraphRunner:
    def __init__(
        self,
        *,
        generation_client: GenerateClient,
        embedding_encoder: EmbeddingEncoder | None,
    ):
        self.generation_client: GenerateClient = generation_client
        self.embedding_encoder: EmbeddingEncoder | None = embedding_encoder
        self.graph: ReactionGraphInvoker = self._build_graph()

    def decide_reaction(self, input: ReactionDecisionInput) -> ReactionDecision:
        final_state = self.graph.invoke(self._initial_state(input))
        return final_state["decision"]

    def _build_graph(self) -> ReactionGraphInvoker:
        builder = STATE_GRAPH(ReactionGraphState)
        builder.add_node("initialize_context", self._initialize_context)
        builder.add_node("generate_intent", self._generate_intent)
        builder.add_node("finalize_no_reaction", self._finalize_no_reaction)
        builder.add_node("prepare_utterance_context", self._prepare_utterance_context)
        builder.add_node("generate_utterance", self._generate_utterance)
        builder.add_node("apply_partner_nudge", self._apply_partner_nudge)
        builder.add_node("evaluate_semantic", self._evaluate_semantic)
        builder.add_node("apply_semantic_retry", self._apply_semantic_retry)
        builder.add_node("evaluate_overlap", self._evaluate_overlap)
        builder.add_node("apply_overlap_retry", self._apply_overlap_retry)

        builder.add_edge(GRAPH_START, "initialize_context")
        builder.add_edge("initialize_context", "generate_intent")
        builder.add_conditional_edges(
            "generate_intent",
            self._route_after_intent,
            {
                "finalize_no_reaction": "finalize_no_reaction",
                "prepare_utterance_context": "prepare_utterance_context",
            },
        )
        builder.add_edge("finalize_no_reaction", GRAPH_END)
        builder.add_edge("prepare_utterance_context", "generate_utterance")
        builder.add_conditional_edges(
            "generate_utterance",
            self._route_after_utterance,
            {
                "apply_partner_nudge": "apply_partner_nudge",
                "evaluate_semantic": "evaluate_semantic",
            },
        )
        builder.add_edge("apply_partner_nudge", "generate_utterance")
        builder.add_conditional_edges(
            "evaluate_semantic",
            self._route_after_semantic,
            {
                "apply_semantic_retry": "apply_semantic_retry",
                "evaluate_overlap": "evaluate_overlap",
                "__end__": GRAPH_END,
            },
        )
        builder.add_edge("apply_semantic_retry", "generate_utterance")
        builder.add_conditional_edges(
            "evaluate_overlap",
            self._route_after_overlap,
            {
                "apply_overlap_retry": "apply_overlap_retry",
                "__end__": GRAPH_END,
            },
        )
        builder.add_edge("apply_overlap_retry", "generate_utterance")

        return builder.compile()

    def _initial_state(self, input: ReactionDecisionInput) -> ReactionGraphState:
        return ReactionGraphState(
            input=input,
            system_prompt="",
            intent_prompt="",
            intent=ReactionIntent(should_react=False, reason="uninitialized"),
            utterance_prompt="",
            working_prompt="",
            recent_sentences=[],
            partner_utterance="",
            partner_retry_count=0,
            semantic_history=[],
            semantic_history_embeddings=[],
            semantic_retry_count=0,
            overlap_retry_count=0,
            semantic_check=SemanticOverlapCheck(max_similarity=0.0, trigger="none"),
            semantic_status="continue",
            overlap_status="final",
            utterance_result=ReactionUtterance(utterance="", reason="uninitialized"),
            decision=ReactionDecision(
                should_react=False,
                reaction="",
                reason="uninitialized",
            ),
        )

    def _initialize_context(self, state: ReactionGraphState) -> dict[str, str]:
        input = state["input"]
        return {
            "system_prompt": prompt_builders.language_system_prompt(input.language),
            "intent_prompt": prompt_builders.build_reaction_intent_prompt(
                agent_identity=input.agent_identity,
                current_time=input.current_time,
                observation_content=input.observation_content,
                dialogue_history=input.dialogue_history,
                profile=input.profile,
                retrieved_memories=input.retrieved_memories,
                dialogue_arc=input.dialogue_arc,
            ),
        }

    def _generate_intent(
        self,
        state: ReactionGraphState,
    ) -> dict[str, ReactionIntent]:
        try:
            response = self.generation_client.generate(
                prompt=state["intent_prompt"],
                system=state["system_prompt"],
                options=REACTION_INTENT_GENERATE_OPTIONS,
                response_model=ReactionIntentOutput,
            )
        except (LlmOutputTruncatedError, LlmStructuredOutputError) as error:
            return {"intent": self._generation_failure_intent(error=error)}
        intent = parse_reaction_intent(response)
        if state["input"].language == "ko":
            intent = replace(
                intent,
                reason=korean_text_or_fallback(
                    intent.reason,
                    fallback="반응 여부를 한국어로 판단함",
                ),
                thought=korean_text_or_fallback(
                    intent.thought,
                    fallback="상황과 대화 맥락을 한국어로 판단함",
                ),
                critique=korean_text_or_fallback(
                    intent.critique,
                    fallback="응답의 자연스러움을 한국어로 점검함",
                ),
            )
        return {"intent": intent}

    def _route_after_intent(
        self,
        state: ReactionGraphState,
    ) -> Literal["finalize_no_reaction", "prepare_utterance_context"]:
        if not state["intent"].should_react:
            return "finalize_no_reaction"
        return "prepare_utterance_context"

    def _finalize_no_reaction(
        self,
        state: ReactionGraphState,
    ) -> dict[str, ReactionDecision]:
        intent = state["intent"]
        return {
            "decision": ReactionDecision(
                should_react=False,
                reaction="",
                reason=intent.reason,
                end_dialogue=intent.end_dialogue,
                thought=intent.thought,
                critique=intent.critique,
                trace=replace(
                    intent.trace,
                    partner_retry_count=0,
                    semantic_hard_threshold=SEMANTIC_HARD_BLOCK_THRESHOLD,
                    semantic_soft_threshold=SEMANTIC_SOFT_PENALTY_THRESHOLD,
                ),
            )
        }

    def _prepare_utterance_context(
        self,
        state: ReactionGraphState,
    ) -> dict[str, object]:
        input = state["input"]
        intent = state["intent"]
        utterance_prompt = prompt_builders.build_reaction_utterance_prompt(
            agent_identity=input.agent_identity,
            current_time=input.current_time,
            observation_content=input.observation_content,
            dialogue_history=input.dialogue_history,
            profile=input.profile,
            retrieved_memories=input.retrieved_memories,
            intent_reason=intent.reason,
            intent_thought=intent.thought,
            intent_critique=intent.critique,
            dialogue_arc=input.dialogue_arc,
        )
        semantic_history = recent_self_utterances(input.dialogue_history, window=5)
        return {
            "utterance_prompt": utterance_prompt,
            "working_prompt": utterance_prompt,
            "recent_sentences": recent_dialogue_sentences(
                input.dialogue_history,
                window=3,
            ),
            "partner_utterance": latest_partner_utterance(input.dialogue_history),
            "partner_retry_count": 0,
            "semantic_history": semantic_history,
            "semantic_history_embeddings": embed_sentences(
                sentences=semantic_history,
                embedding_encoder=self.embedding_encoder,
            ),
            "semantic_retry_count": 0,
            "overlap_retry_count": 0,
        }

    def _generate_utterance(
        self,
        state: ReactionGraphState,
    ) -> dict[str, object]:
        try:
            response = self.generation_client.generate(
                prompt=state["working_prompt"],
                system=state["system_prompt"],
                options=REACTION_UTTERANCE_GENERATE_OPTIONS,
                response_model=ReactionUtteranceOutput,
            )
        except (LlmOutputTruncatedError, LlmStructuredOutputError) as error:
            utterance_result = self._generation_failure_utterance(error=error)
            return {
                "utterance_result": utterance_result,
                "decision": self._build_reaction_decision(
                    intent=state["intent"],
                    utterance_result=utterance_result,
                ),
            }
        utterance_result = parse_reaction_utterance(response)
        if state["input"].language == "ko":
            utterance_result = replace(
                utterance_result,
                utterance=korean_text_or_fallback(
                    utterance_result.utterance,
                    fallback="",
                ),
                reason=korean_text_or_fallback(
                    utterance_result.reason,
                    fallback="한국어 발화를 생성함",
                ),
                thought=korean_text_or_fallback(
                    utterance_result.thought,
                    fallback="상대의 말과 현재 계획을 한국어로 고려함",
                ),
                critique=korean_text_or_fallback(
                    utterance_result.critique,
                    fallback="발화가 자연스러운지 한국어로 점검함",
                ),
            )
        return {
            "utterance_result": utterance_result,
            "decision": self._build_reaction_decision(
                intent=state["intent"],
                utterance_result=utterance_result,
            ),
        }

    def _route_after_utterance(
        self,
        state: ReactionGraphState,
    ) -> Literal["apply_partner_nudge", "evaluate_semantic"]:
        if (
            state["partner_utterance"]
            and not state["decision"].reaction
            and state["partner_retry_count"] < 1
        ):
            return "apply_partner_nudge"
        return "evaluate_semantic"

    def _apply_partner_nudge(
        self,
        state: ReactionGraphState,
    ) -> dict[str, object]:
        partner_retry_count = state["partner_retry_count"] + 1
        return {
            "partner_retry_count": partner_retry_count,
            "working_prompt": (
                f"{state['utterance_prompt']}\n\n"
                + prompt_builders.build_partner_response_nudge_block(
                    latest_partner_utterance=state["partner_utterance"],
                )
            ),
        }

    def _evaluate_semantic(
        self,
        state: ReactionGraphState,
    ) -> dict[str, object]:
        semantic_check = semantic_overlap_check(
            candidate_sentence=state["decision"].reaction,
            reference_sentences=state["semantic_history"],
            reference_embeddings=state["semantic_history_embeddings"],
            embedding_encoder=self.embedding_encoder,
        )
        base_decision = self._decorate_decision_trace(
            decision=state["decision"],
            partner_retry_count=state["partner_retry_count"],
            semantic_retry_count=state["semantic_retry_count"],
            semantic_check=semantic_check,
        )

        if semantic_check.max_similarity >= SEMANTIC_SOFT_PENALTY_THRESHOLD:
            next_retry_count = state["semantic_retry_count"] + 1
            # Capped at one retry: a local model call is expensive enough that a
            # second consecutive semantic-overlap retry rarely pays for itself, and
            # this can already stack with a partner nudge and an overlap retry.
            if next_retry_count > 1:
                return {
                    "decision": replace(
                        base_decision,
                        trace=replace(
                            base_decision.trace,
                            semantic_retry_count=next_retry_count,
                            fallback_reason="semantic_retry_exhausted",
                        ),
                    ),
                    "semantic_check": semantic_check,
                    "semantic_retry_count": next_retry_count,
                    "semantic_status": "final",
                }
            return {
                "semantic_check": semantic_check,
                "semantic_retry_count": next_retry_count,
                "semantic_status": "retry",
            }

        return {
            "decision": base_decision,
            "semantic_check": semantic_check,
            "semantic_status": "continue",
        }

    def _route_after_semantic(
        self,
        state: ReactionGraphState,
    ) -> Literal["apply_semantic_retry", "evaluate_overlap", "__end__"]:
        semantic_status = state["semantic_status"]
        if semantic_status == "retry":
            return "apply_semantic_retry"
        if semantic_status == "continue":
            return "evaluate_overlap"
        return "__end__"

    def _apply_semantic_retry(
        self,
        state: ReactionGraphState,
    ) -> dict[str, str]:
        semantic_check = state["semantic_check"]
        return {
            "working_prompt": (
                f"{state['utterance_prompt']}\n\n"
                + prompt_builders.build_semantic_guard_block(
                    semantic_history=state["semantic_history"],
                    previous_candidate=state["decision"].reaction,
                    max_similarity=semantic_check.max_similarity,
                    trigger=semantic_check.trigger,
                    soft_threshold=SEMANTIC_SOFT_PENALTY_THRESHOLD,
                    hard_threshold=SEMANTIC_HARD_BLOCK_THRESHOLD,
                )
            )
        }

    def _evaluate_overlap(
        self,
        state: ReactionGraphState,
    ) -> dict[str, object]:
        decision = state["decision"]
        recent_sentences = state["recent_sentences"]
        if not decision.reaction or not recent_sentences:
            return {"overlap_status": "final"}

        has_overlap = exceeds_ngram_overlap_threshold(
            candidate_sentence=decision.reaction,
            recent_sentences=recent_sentences,
            n=2,
            threshold=0.5,
        )
        if not has_overlap:
            return {"overlap_status": "final"}

        next_retry_count = state["overlap_retry_count"] + 1
        # Capped at one retry for the same reason as the semantic-overlap check above.
        if next_retry_count > 1:
            return {
                "decision": replace(
                    decision,
                    trace=replace(
                        decision.trace,
                        overlap_retry_count=next_retry_count,
                        fallback_reason="overlap_retry_exhausted",
                    ),
                ),
                "overlap_retry_count": next_retry_count,
                "overlap_status": "final",
            }

        return {
            "overlap_retry_count": next_retry_count,
            "overlap_status": "retry",
        }

    def _route_after_overlap(
        self,
        state: ReactionGraphState,
    ) -> Literal["apply_overlap_retry", "__end__"]:
        if state["overlap_status"] == "retry":
            return "apply_overlap_retry"
        return "__end__"

    def _apply_overlap_retry(
        self,
        state: ReactionGraphState,
    ) -> dict[str, str]:
        return {
            "working_prompt": (
                f"{state['utterance_prompt']}\n\n"
                + prompt_builders.build_overlap_guard_block(
                    recent_sentences=state["recent_sentences"],
                    previous_candidate=state["decision"].reaction,
                )
            )
        }

    @staticmethod
    def _generation_failure_trace(
        *, error: LlmOutputTruncatedError | LlmStructuredOutputError
    ) -> ReactionDecisionTrace:
        failure = (
            "provider_output_truncated"
            if isinstance(error, LlmOutputTruncatedError)
            else "provider_structured_output_invalid"
        )
        return ReactionDecisionTrace(
            raw_response="",
            parse_success=False,
            parse_error=failure,
            fallback_reason=failure,
        )

    @classmethod
    def _generation_failure_intent(
        cls,
        *,
        error: LlmOutputTruncatedError | LlmStructuredOutputError,
    ) -> ReactionIntent:
        return ReactionIntent(
            should_react=False,
            reason="fallback",
            trace=cls._generation_failure_trace(error=error),
        )

    @classmethod
    def _generation_failure_utterance(
        cls,
        *,
        error: LlmOutputTruncatedError | LlmStructuredOutputError,
    ) -> ReactionUtterance:
        return ReactionUtterance(
            utterance="",
            reason="fallback",
            trace=cls._generation_failure_trace(error=error),
        )

    @staticmethod
    def _build_reaction_decision(
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

    @staticmethod
    def _decorate_decision_trace(
        *,
        decision: ReactionDecision,
        partner_retry_count: int,
        semantic_retry_count: int,
        semantic_check: SemanticOverlapCheck,
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
            ),
        )
