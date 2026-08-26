from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from agents.agent import AgentIdentity, AgentProfile
from agents.memory.memory_object import MemoryObject

if TYPE_CHECKING:
    from pydantic import BaseModel

    from llm.clients.types import LlmGenerateOptions


@dataclass(frozen=True)
class DialogueArc:
    goal: str
    turns_taken: int
    target_turns: int
    remaining_turns: int
    phase: Literal["opening", "middle", "closing"]
    should_wrap_up: bool = False


@dataclass(frozen=True)
class ReactionDecisionInput:
    agent_identity: AgentIdentity
    current_time: datetime.datetime
    observation_content: str
    dialogue_history: list[tuple[str, str]]
    profile: AgentProfile
    retrieved_memories: list[MemoryObject]
    dialogue_arc: DialogueArc | None = None
    language: Literal["ko", "en"] = "ko"
    recent_self_utterances: list[str] | None = None


@dataclass(frozen=True)
class ReactionDecisionTrace:
    raw_response: str
    parse_success: bool
    parse_error: str = ""
    fallback_reason: str = ""
    suppress_reason: str = ""
    overlap_retry_count: int = 0
    partner_retry_count: int = 0
    semantic_retry_count: int = 0
    max_semantic_similarity: float = 0.0
    semantic_hard_threshold: float = 0.92
    semantic_soft_threshold: float = 0.82
    semantic_retry_trigger: str = "none"


@dataclass(frozen=True)
class ReactionDecision:
    should_react: bool
    reaction: str
    reason: str
    end_dialogue: bool = False
    thought: str = ""
    critique: str = ""
    trace: ReactionDecisionTrace = ReactionDecisionTrace(
        raw_response="",
        parse_success=False,
        parse_error="uninitialized",
    )


@dataclass(frozen=True)
class ReactionIntent:
    should_react: bool
    reason: str
    end_dialogue: bool = False
    thought: str = ""
    critique: str = ""
    trace: ReactionDecisionTrace = ReactionDecisionTrace(
        raw_response="",
        parse_success=False,
        parse_error="uninitialized",
    )


@dataclass(frozen=True)
class ReactionUtterance:
    utterance: str
    reason: str
    end_dialogue: bool = False
    thought: str = ""
    critique: str = ""
    trace: ReactionDecisionTrace = ReactionDecisionTrace(
        raw_response="",
        parse_success=False,
        parse_error="uninitialized",
    )


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
