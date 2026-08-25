"""§4.3.1 Reacting and Updating Plans — tick-level continue-vs-react gate.

This module answers a distinct question from `agents/reaction/graph.py`'s
`should_react`: that gate decides whether an *already-active dialogue*
should continue. This gate decides, for *any* tick observation, whether the
agent's existing day/hourly/minute plan should keep running unchanged or be
disrupted and partially replanned (§4.3.1, the Klaus/easel vs. father/son
walk example). The prompt shape follows the paper: `[Agent's Summary
Description]` + current time + agent status + observation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .react_gate_contracts import (
    PlanDisruptionDecision,
    PlanDisruptionInput,
    PlanDisruptionTrace,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from llm.clients.types import LlmGenerateOptions

__all__ = [
    "PlanDisruptionDecision",
    "PlanDisruptionInput",
    "PlanDisruptionTrace",
    "GenerateClient",
    "PlanDisruptionGate",
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


class PlanDisruptionGate:
    """Runs the §4.3.1 continue-vs-react judgment once per tick observation."""

    def __init__(self, *, generation_client: GenerateClient):
        self.generation_client: GenerateClient = generation_client

    def evaluate(self, input: PlanDisruptionInput) -> PlanDisruptionDecision:
        from llm import prompt_builders
        from llm.clients.types import LlmGenerateOptions
        from llm.governance.parsing import parse_plan_disruption
        from llm.language_policy import korean_text_or_fallback
        from llm.structured_outputs import PlanDisruptionOutput

        if not input.observation_content.strip():
            return PlanDisruptionDecision(
                should_react=False,
                reason="관찰 내용이 없어 기존 계획을 유지함",
                trace=PlanDisruptionTrace(
                    raw_response="", parse_success=True, parse_error=""
                ),
            )

        prompt = prompt_builders.build_plan_disruption_prompt(
            agent_identity=input.agent_identity,
            profile=input.profile,
            current_time=input.current_time,
            agent_status=input.agent_status,
            observation_content=input.observation_content,
        )
        response = self.generation_client.generate(
            prompt=prompt,
            system=prompt_builders.language_system_prompt("ko"),
            options=LlmGenerateOptions(temperature=0.0, top_p=1.0, num_predict=384),
            response_model=PlanDisruptionOutput,
        )
        decision = parse_plan_disruption(response)
        return PlanDisruptionDecision(
            should_react=decision.should_react,
            reason=korean_text_or_fallback(
                decision.reason, fallback="관찰이 계획에 미치는 영향을 한국어로 판단함"
            ),
            trace=decision.trace,
        )
