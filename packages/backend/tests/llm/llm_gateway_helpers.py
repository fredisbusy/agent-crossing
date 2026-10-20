import datetime
import json

import numpy as np
from agents.agent import AgentIdentity, AgentProfile, ExtendedPersona, FixedPersona
from agents.memory.memory_object import MemoryObject
from agents.reaction import ReactionDecisionInput
from llm.embedding_encoder import EmbeddingEncodingContext


class StubGenerationClient:
    def __init__(self, responses: list[str]):
        self.responses: list[str] = list(responses)
        self.calls: int = 0
        self.call_kwargs: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> str:
        self.call_kwargs.append(kwargs)
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]


class StubEmbeddingEncoder:
    def __init__(self, vectors: dict[str, list[float]]):
        self.vectors: dict[str, list[float]] = vectors

    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray:
        if context.text not in self.vectors:
            return np.asarray([0.0, 1.0], dtype=np.float32)
        return np.asarray(self.vectors[context.text], dtype=np.float32)


def reaction_json(
    *,
    should_react: bool,
    reaction: str,
    reason: str,
    end_dialogue: bool = False,
    thought: str = "",
    critique: str = "",
    use_utterance_field: bool = False,
) -> str:
    payload: dict[str, object] = {
        "should_react": should_react,
        "reason": reason,
        "end_dialogue": end_dialogue,
    }
    if use_utterance_field:
        payload["utterance"] = reaction
    else:
        payload["reaction"] = reaction

    if thought:
        payload["thought"] = thought
    if critique:
        payload["critique"] = critique

    return json.dumps(payload)


def intent_json(
    *,
    should_react: bool,
    reason: str,
    end_dialogue: bool = False,
    thought: str = "",
    critique: str = "",
) -> str:
    payload: dict[str, object] = {
        "should_react": should_react,
        "reason": reason,
        "end_dialogue": end_dialogue,
    }
    if thought:
        payload["thought"] = thought
    if critique:
        payload["critique"] = critique

    return json.dumps(payload)


def build_reaction_input(
    dialogue_history: list[tuple[str, str]],
    *,
    retrieved_memories: list[MemoryObject] | None = None,
) -> ReactionDecisionInput:
    return ReactionDecisionInput(
        agent_identity=AgentIdentity(
            id="jiho",
            name="Jiho Park",
            age=29,
            traits=["kind"],
        ),
        current_time=datetime.datetime(2026, 2, 27, 14, 0, 0),
        observation_content="Jiho encountered Sujin near the cafe.",
        dialogue_history=dialogue_history,
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=["Jiho helps neighbors."]),
            extended=ExtendedPersona(
                lifestyle_and_routine=["Morning library routine."],
                current_plan_context=["Finish workbook."],
            ),
        ),
        retrieved_memories=retrieved_memories or [],
        language="ko",
    )
