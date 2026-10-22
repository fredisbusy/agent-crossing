import datetime
from typing import Literal, cast

import numpy as np
from agents.agent import AgentIdentity, AgentProfile, ExtendedPersona, FixedPersona
from agents.brain import ActionLoopInput, ActionLoopResult, AgentBrainGraphRunner
from agents.memory.memory_object import MemoryObject, NodeType
from agents.planning.models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)
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

    def create_plan(
        self,
        *,
        content: str,
        now: datetime.datetime,
        context: object,
        importance: int | None = None,
    ) -> MemoryObject:
        _ = content, context, importance
        self.calls.append("create_plan")
        return MemoryObject(
            id=2,
            node_type=NodeType.PLAN,
            citations=None,
            content="plan",
            created_at=now,
            last_accessed_at=now,
            importance=6,
            embedding=np.zeros(2, dtype=np.float32),
        )


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
                start_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                end_time=datetime.datetime(2026, 3, 3, 14, 0, 0),
                location="Town > Home > Desk",
                action_content="Work through a composition block.",
            )
        ]

    def generate_hourly_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        day_plan_item: DayPlanItem,
    ) -> list[HourlyPlanItem]:
        _ = current_time, day_plan_item
        self.calls.append(f"generate_hourly_plan:{agent_name}")
        return [
            HourlyPlanItem(
                start_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                end_time=datetime.datetime(2026, 3, 3, 13, 0, 0),
                location="Town > Home > Desk",
                action_content="Draft composition exercises.",
            )
        ]

    def generate_minute_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        hourly_plan_item: HourlyPlanItem,
    ) -> list[MinutePlanItem]:
        _ = current_time, hourly_plan_item
        self.calls.append(f"generate_minute_plan:{agent_name}")
        return [
            MinutePlanItem(
                start_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
                end_time=datetime.datetime(2026, 3, 3, 12, 10, 0),
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

    result = graph.run(_input())

    assert result.silent_reason == "llm_declined_reaction"
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

    result = graph.run(_input())

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


def test_brain_graph_updates_plan_context_after_retrieval() -> None:
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
    assert calls == [
        "encode_observation",
        "create_observation",
        "record_observation_importance",
        "should_reflect",
        "get_retrieval_memories",
        "generate_day_plan:Jiho",
        "generate_hourly_plan:Jiho",
        "generate_minute_plan:Jiho",
        "decide_reaction",
    ]


def test_brain_graph_updates_plan_memory_after_partner_utterance() -> None:
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
        reflection_graph=StubReflectionGraph(calls, should_reflect=False),
        llm_gateway=StubLlmGateway(calls),
        observation_writer=_ignore_observation,
        planner=StubPlanner(calls),
    )

    result = graph.run(
        ActionLoopInput(
            current_time=datetime.datetime(2026, 3, 3, 12, 1, 0),
            dialogue_history=[("새 디카프 블렌드 반응이 좋아요.", "")],
            profile=_profile(),
            language=cast(Literal["ko", "en"], "ko"),
            observed_entities=["Sujin"],
        )
    )

    assert result.plan_updated is True
    assert result.replan_reason == "dialogue_partner_utterance"
    assert "Continue the open conversation with Sujin" in result.current_plan_item
    assert calls.index("get_retrieval_memories") < calls.index("create_plan")
    assert calls.index("create_plan") < calls.index("decide_reaction")


class CapturingEncoder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def encode(self, context: object) -> np.ndarray:
        self.texts.append(cast(str, getattr(context, "text")))
        return np.zeros(2, dtype=np.float32)


def _perceive_text(now: datetime.datetime) -> str:
    calls: list[str] = []
    memory = StubMemoryManager(calls)
    encoder = CapturingEncoder()
    graph = AgentBrainGraphRunner(
        agent_identity=AgentIdentity(id="jiho", name="Jiho", age=29, traits=["kind"]),
        memory_manager=memory,
        embedding_encoder=encoder,
        reflection_graph=StubReflectionGraph(calls, should_reflect=False),
        llm_gateway=StubLlmGateway(calls),
        observation_writer=_ignore_observation,
        planner=StubPlanner(calls),
    )
    _ = graph.run(
        ActionLoopInput(
            current_time=now,
            dialogue_history=[],
            profile=_profile(),
            language=cast(Literal["ko", "en"], "ko"),
            observed_entities=["Sujin", "Minho"],
            observed_events=["Sujin이 인사했다"],
            world_context={"location": "Town > Cafe"},
        )
    )
    return encoder.texts[0]


def test_perceive_text_is_natural_language_without_metadata() -> None:
    text = _perceive_text(datetime.datetime(2026, 3, 3, 12, 0, 0))

    assert (
        text == "Jiho이(가) Town > Cafe에 있다. 주변: Sujin, Minho. 사건: Sujin이 인사했다."
    )
    for meta in ("time=", "agent=", "traits=", "current_plan=", "2026"):
        assert meta not in text


def test_perceive_text_is_deterministic_across_times() -> None:
    first = _perceive_text(datetime.datetime(2026, 3, 3, 12, 0, 0))
    second = _perceive_text(datetime.datetime(2026, 3, 3, 12, 7, 0))

    assert first == second
