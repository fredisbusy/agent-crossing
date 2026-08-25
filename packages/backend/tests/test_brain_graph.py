import datetime
from typing import Literal, cast

import numpy as np
from agents.agent import AgentIdentity, AgentProfile, ExtendedPersona, FixedPersona
from agents.brain import ActionLoopInput, ActionLoopResult, AgentBrainGraphRunner
from agents.planning.models import DayPlanBroadStrokesRequest, DayPlanItem
from agents.memory.memory_object import MemoryObject, NodeType
from agents.reaction import ReactionDecision, ReactionDecisionTrace


class StubEmbeddingEncoder:
    def __init__(self, calls: list[str]):
        self.calls: list[str] = calls

    def encode(self, context: object) -> np.ndarray:
        _ = context
        self.calls.append("encode_observation")
        return np.zeros(2, dtype=np.float32)


class StubMemoryManager:
    def __init__(self, calls: list[str]):
        self.calls: list[str] = calls
        self.embedding_encoder: StubEmbeddingEncoder = StubEmbeddingEncoder(calls)

    def create_observation(
        self,
        *,
        content: str,
        now: datetime.datetime,
        embedding: np.ndarray,
        context: object,
        importance: int | None,
    ) -> MemoryObject:
        _ = content, now, embedding, context, importance
        self.calls.append("create_observation")
        return MemoryObject(
            id=1,
            node_type=NodeType.OBSERVATION,
            citations=None,
            content="observation",
            created_at=now,
            last_accessed_at=now,
            importance=7,
            embedding=np.zeros(2, dtype=np.float32),
        )

    def get_retrieval_memories(
        self,
        *,
        query: str,
        current_time: datetime.datetime,
        top_k: int = 3,
    ) -> list[MemoryObject]:
        _ = query, current_time, top_k
        self.calls.append("get_retrieval_memories")
        return []


class StubReflectionGraph:
    def __init__(self, calls: list[str], *, should_reflect: bool):
        self.calls: list[str] = calls
        self.should_reflect_value: bool = should_reflect

    def record_observation_importance(self, importance: int) -> None:
        _ = importance
        self.calls.append("record_observation_importance")

    def should_reflect(self) -> bool:
        self.calls.append("should_reflect")
        return self.should_reflect_value

    def reflect(self, *, now: datetime.datetime) -> None:
        _ = now
        self.calls.append("reflect")


class StubLlmGateway:
    def __init__(self, calls: list[str]):
        self.calls: list[str] = calls

    def decide_reaction(self, input: object) -> ReactionDecision:
        _ = input
        self.calls.append("decide_reaction")
        return ReactionDecision(
            should_react=False,
            reaction="",
            reason="skip",
            trace=ReactionDecisionTrace(raw_response="", parse_success=True),
        )


class StubPlanner:
    def __init__(self, calls: list[str]):
        self.calls: list[str] = calls

    def generate_day_plan(
        self,
        request: DayPlanBroadStrokesRequest,
    ) -> list[DayPlanItem]:
        self.calls.append(f"generate_day_plan:{request.agent_name}")
        return [
            DayPlanItem(
                start_time=datetime.datetime(2026, 3, 3, 9, 0, 0),
                end_time=datetime.datetime(2026, 3, 3, 10, 0, 0),
                location="Town > Home > Desk",
                action_content="Draft a composition exercise.",
            )
        ]


def _profile() -> AgentProfile:
    return AgentProfile(
        fixed=FixedPersona(identity_stable_set=["kind"]),
        extended=ExtendedPersona(
            lifestyle_and_routine=[],
            current_plan_context=[],
        ),
    )


def _input() -> ActionLoopInput:
    return ActionLoopInput(
        current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
        dialogue_history=[],
        profile=_profile(),
        language=cast(Literal["ko", "en"], "ko"),
    )


def _append_observation(
    queued: list[str],
    *,
    content: str,
    now: datetime.datetime,
    profile: AgentProfile,
    current_plan: str | None = None,
    importance: int | None = None,
) -> None:
    _ = now, profile, current_plan, importance
    queued.append(content)


def _ignore_observation(
    *,
    content: str,
    now: datetime.datetime,
    profile: AgentProfile,
    current_plan: str | None = None,
    importance: int | None = None,
) -> None:
    _ = content, now, profile, current_plan, importance


def _observation_writer(queued: list[str]):
    def write_observation(
        *,
        content: str,
        now: datetime.datetime,
        profile: AgentProfile,
        current_plan: str | None = None,
        importance: int | None = None,
    ) -> None:
        _append_observation(
            queued,
            content=content,
            now=now,
            profile=profile,
            current_plan=current_plan,
            importance=importance,
        )

    return write_observation


def test_brain_graph_skips_reflection_when_not_needed() -> None:
    calls: list[str] = []
    queued: list[str] = []
    memory = StubMemoryManager(calls)
    graph = AgentBrainGraphRunner(
        agent_identity=AgentIdentity(
            id="jiho",
            name="Jiho",
            age=29,
            traits=["kind"],
        ),
        memory_manager=memory,
        embedding_encoder=memory.embedding_encoder,
        reflection_graph=StubReflectionGraph(calls, should_reflect=False),
        llm_gateway=StubLlmGateway(calls),
        observation_writer=_observation_writer(queued),
    )

    result, reaction_decision = graph.run(_input())

    assert result.silent_reason == "llm_declined_reaction"
    assert reaction_decision is not None
    assert queued == []
    assert calls == [
        "encode_observation",
        "create_observation",
        "record_observation_importance",
        "should_reflect",
        "get_retrieval_memories",
        "decide_reaction",
    ]


def test_brain_graph_runs_reflection_before_retrieval_when_needed() -> None:
    calls: list[str] = []
    memory = StubMemoryManager(calls)
    graph = AgentBrainGraphRunner(
        agent_identity=AgentIdentity(
            id="jiho",
            name="Jiho",
            age=29,
            traits=["kind"],
        ),
        memory_manager=memory,
        embedding_encoder=memory.embedding_encoder,
        reflection_graph=StubReflectionGraph(calls, should_reflect=True),
        llm_gateway=StubLlmGateway(calls),
        observation_writer=_ignore_observation,
    )

    result, _reaction_decision = graph.run(_input())

    assert isinstance(result, ActionLoopResult)
    assert calls == [
        "encode_observation",
        "create_observation",
        "record_observation_importance",
        "should_reflect",
        "reflect",
        "get_retrieval_memories",
        "decide_reaction",
    ]


def test_brain_graph_seeds_plan_context_with_planner_when_missing() -> None:
    calls: list[str] = []
    memory = StubMemoryManager(calls)
    profile = _profile()
    graph = AgentBrainGraphRunner(
        agent_identity=AgentIdentity(
            id="jiho",
            name="Jiho",
            age=29,
            traits=["kind"],
        ),
        memory_manager=memory,
        embedding_encoder=memory.embedding_encoder,
        reflection_graph=StubReflectionGraph(calls, should_reflect=False),
        llm_gateway=StubLlmGateway(calls),
        observation_writer=_ignore_observation,
        planner=StubPlanner(calls),
    )

    _ = graph.run(
        ActionLoopInput(
            current_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
            dialogue_history=[],
            profile=profile,
            language=cast(Literal["ko", "en"], "ko"),
        )
    )

    assert profile.extended.current_plan_context == ["Draft a composition exercise."]
    assert calls[0] == "generate_day_plan:Jiho"
