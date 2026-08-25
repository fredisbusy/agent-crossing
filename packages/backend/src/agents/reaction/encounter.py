"""§3.4/§4.3 encounter judgment: pass-by vs converse.

When two agents encounter each other, decide whether they should pass by
without interacting or start a conversation. The decision is grounded in a
relationship summary and a context summary (the paper's two-summary
pattern), and it hands off into the existing short-dialogue-arc session
mechanism (§2-D, `agents/reaction/graph.py`) on "converse".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .encounter_contracts import (
    EncounterDecision,
    EncounterDecisionInput,
    EncounterDecisionTrace,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from llm.clients.types import LlmGenerateOptions

__all__ = [
    "EncounterDecision",
    "EncounterDecisionInput",
    "EncounterDecisionTrace",
    "GenerateClient",
    "EncounterGate",
]


class GenerateClient(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
        response_model: type[BaseModel] | None = None,
    ) -> str: ...


class EncounterGate:
    """Runs the pass-by vs converse judgment for a single encounter."""

    def __init__(self, *, generation_client: GenerateClient):
        self.generation_client: GenerateClient = generation_client

    def evaluate(self, input: EncounterDecisionInput) -> EncounterDecision:
        from llm import prompt_builders
        from llm.clients.types import LlmGenerateOptions
        from llm.governance.parsing import parse_encounter_decision
        from llm.language_policy import korean_text_or_fallback
        from llm.structured_outputs import EncounterOutput

        prompt = prompt_builders.build_encounter_prompt(
            self_identity=input.self_identity,
            other_identity=input.other_identity,
            self_profile=input.self_profile,
            current_time=input.current_time,
            retrieved_memories=input.retrieved_memories,
        )
        response = self.generation_client.generate(
            prompt=prompt,
            system=prompt_builders.language_system_prompt("ko"),
            options=LlmGenerateOptions(temperature=0.2, top_p=0.95, num_predict=512),
            response_model=EncounterOutput,
        )
        decision = parse_encounter_decision(response)
        return EncounterDecision(
            should_converse=decision.should_converse,
            relationship_summary=korean_text_or_fallback(
                decision.relationship_summary, fallback="관계 요약 없음"
            ),
            context_summary=korean_text_or_fallback(
                decision.context_summary, fallback="상황 요약 없음"
            ),
            reason=korean_text_or_fallback(
                decision.reason, fallback="조우 판단을 한국어로 수행함"
            ),
            trace=decision.trace,
        )
