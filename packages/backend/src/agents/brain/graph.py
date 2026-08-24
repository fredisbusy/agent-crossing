import datetime
from importlib import import_module
from typing import Literal, Protocol, cast

import numpy as np
from typing_extensions import TypedDict

from agents.agent import AgentIdentity, AgentProfile
from agents.memory.memory_object import MemoryObject
from agents.planning.models import DayPlanBroadStrokesRequest, DayPlanItem
from agents.reaction import ReactionDecision, ReactionDecisionInput
from llm.embedding_encoder import EmbeddingEncodingContext

from ..decision_diagnostics import build_action_diagnostics
from ..graph_support import (
    GRAPH_END,
    GRAPH_START,
    GRAPH_STATE_FACTORY,
    require_state_value,
)
from ..memory.memory_manager import ObservationContext
from .types import ActionLoopInput, ActionLoopResult, DetermineContext, Observation


class PromptBuildersModule(Protocol):
    def build_retrieval_query(
        self,
        *,
        agent_identity: AgentIdentity,
        observation_content: str,
        dialogue_history: list[tuple[str, str]],
        profile: AgentProfile,
    ) -> str: ...


class ObservationWriter(Protocol):
    def __call__(
        self,
        *,
        content: str,
        now: datetime.datetime,
        profile: AgentProfile,
        current_plan: str | None = None,
        importance: int | None = None,
    ) -> None: ...


class EmbeddingEncoderLike(Protocol):
    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray: ...


class ObservationMemoryManager(Protocol):
    def create_observation(
        self,
        *,
        content: str,
        now: datetime.datetime,
        embedding: np.ndarray,
        context: ObservationContext,
        importance: int | None,
    ) -> MemoryObject: ...

    def get_retrieval_memories(
        self,
        *,
        query: str,
        current_time: datetime.datetime,
        top_k: int = 3,
    ) -> list[MemoryObject]: ...


class ReflectionRunner(Protocol):
    def record_observation_importance(self, importance: int) -> None: ...

    def should_reflect(self) -> bool: ...

    def reflect(self, *, now: datetime.datetime) -> None: ...


class ReactionGateway(Protocol):
    def decide_reaction(self, input: ReactionDecisionInput) -> ReactionDecision: ...


class PlanningRunner(Protocol):
    def generate_day_plan(
        self,
        request: DayPlanBroadStrokesRequest,
    ) -> list[DayPlanItem]: ...


class AgentBrainGraphBuilder(Protocol):
    def add_node(self, node: str, action: object) -> None: ...

    def add_edge(self, start_key: object, end_key: object) -> None: ...

    def add_conditional_edges(
        self,
        source: str,
        path: object,
        path_map: dict[str, object],
    ) -> None: ...

    def compile(self) -> "AgentBrainGraphInvoker": ...


class AgentBrainGraphInvoker(Protocol):
    def invoke(self, input: "AgentBrainGraphState") -> "AgentBrainGraphState": ...


class StateGraphFactory(Protocol):
    def __call__(
        self, state_schema: type["AgentBrainGraphState"]
    ) -> AgentBrainGraphBuilder: ...


STATE_GRAPH = cast(StateGraphFactory, GRAPH_STATE_FACTORY)


class AgentBrainGraphState(TypedDict):
    input: ActionLoopInput
    observation: Observation | None
    should_reflect: bool
    determine_context: DetermineContext | None
    reaction_decision: ReactionDecision | None
    result: ActionLoopResult | None


class AgentBrainGraphRunner:
    def __init__(
        self,
        *,
        agent_identity: AgentIdentity,
        memory_manager: ObservationMemoryManager,
        embedding_encoder: EmbeddingEncoderLike,
        reflection_graph: ReflectionRunner,
        llm_gateway: ReactionGateway,
        observation_writer: ObservationWriter,
        planner: PlanningRunner | None = None,
    ):
        self.agent_identity: AgentIdentity = agent_identity
        self.memory_manager: ObservationMemoryManager = memory_manager
        self.embedding_encoder: EmbeddingEncoderLike = embedding_encoder
        self.reflection_graph: ReflectionRunner = reflection_graph
        self.llm_gateway: ReactionGateway = llm_gateway
        self.observation_writer: ObservationWriter = observation_writer
        self.planner: PlanningRunner | None = planner
        self.graph: AgentBrainGraphInvoker = self._build_graph()

    def run(self, input: ActionLoopInput) -> ActionLoopResult:
        final_state = self.graph.invoke(
            AgentBrainGraphState(
                input=input,
                observation=None,
                should_reflect=False,
                determine_context=None,
                reaction_decision=None,
                result=None,
            )
        )
        return require_state_value(final_state["result"], key="result")

    def _build_graph(self) -> AgentBrainGraphInvoker:
        builder = STATE_GRAPH(AgentBrainGraphState)
        builder.add_node("ensure_plan_context", self._ensure_plan_context)
        # 1. 현재 상황을 인지한다. 인지할때 월드에서 현재 상황을 조회해서 주입한다.
        builder.add_node("perceive", self._perceive)
        # 2. 인지된 정보들을 observation으로 메모리에 저장 (reflection 조건 충족 시 reflection도 함께 저장)
        builder.add_node("persist_observation", self._persist_observation)
        # 2-1. reflection 조건 충족 시 reflection graph를 실행한다.
        builder.add_node("run_reflection", self._run_reflection)
        # 3. 상황판단을 한다.
        builder.add_node("determine_context", self._determine_context)
        # 4. 상황판단에 따라 반응을 결정한다.
        builder.add_node("decide_reaction", self._decide_reaction)
        # 5. 반응에 때라 구체적인 행동 및 출력을 한다.
        builder.add_node("finalize_action", self._finalize_action)

        builder.add_edge(GRAPH_START, "ensure_plan_context")
        builder.add_edge("ensure_plan_context", "perceive")
        builder.add_edge("perceive", "persist_observation")
        builder.add_conditional_edges(
            "persist_observation",
            self._route_after_persist_observation,
            {
                "run_reflection": "run_reflection",
                "determine_context": "determine_context",
            },
        )
        builder.add_edge("run_reflection", "determine_context")
        builder.add_edge("determine_context", "decide_reaction")
        builder.add_edge("decide_reaction", "finalize_action")
        builder.add_edge("finalize_action", GRAPH_END)
        return builder.compile()

    def _ensure_plan_context(self, state: AgentBrainGraphState) -> dict[str, object]:
        input = state["input"]
        if input.profile.extended.current_plan_context or self.planner is None:
            return {}

        persona_background = " | ".join(input.profile.extended.lifestyle_and_routine)
        if not persona_background.strip():
            persona_background = "사용 가능한 배경 요약이 없다."

        day_plan_items = self.planner.generate_day_plan(
            DayPlanBroadStrokesRequest(
                agent_name=self.agent_identity.name,
                age=self.agent_identity.age,
                innate_traits=list(self.agent_identity.traits),
                persona_background=persona_background,
                yesterday_date=input.current_time - datetime.timedelta(days=1),
                yesterday_summary="기록된 활동 요약이 없다.",
                today_date=input.current_time,
            )
        )
        if not day_plan_items:
            return {}

        input.profile.extended.current_plan_context = [
            item.action_content for item in day_plan_items[:2]
        ]
        return {}

    def _perceive(self, state: AgentBrainGraphState) -> dict[str, Observation]:
        input = state["input"]
        current_plan = (
            input.profile.extended.current_plan_context[0]
            if input.profile.extended.current_plan_context
            else None
        )
        context = input.world_context or {}

        lines: list[str] = []
        lines.append(f"시간={input.current_time.isoformat()}")
        lines.append(f"에이전트={self.agent_identity.name}")
        lines.append(f"현재 계획={current_plan or '없음'}")
        lines.append(f"성격={', '.join(self.agent_identity.traits)}")
        lines.append(f"위치={context.get('location', '알 수 없음')}")

        entity_text = (
            ", ".join(input.observed_entities) if input.observed_entities else "없음"
        )
        lines.append(f"주변 존재={entity_text}")

        if input.observed_events:
            lines.append("관찰 사건=" + "; ".join(input.observed_events))
        else:
            lines.append("관찰 사건=없음")

        content = "\n".join(lines)
        embedding = self.embedding_encoder.encode(
            EmbeddingEncodingContext(text=content)
        )
        return {
            "observation": Observation(
                content=content,
                now=input.current_time,
                embedding=embedding,
                agent_name=self.agent_identity.name,
                current_plan=current_plan,
                importance=None,
            )
        }

    def _persist_observation(self, state: AgentBrainGraphState) -> dict[str, bool]:
        observation = require_state_value(state["observation"], key="observation")
        input = state["input"]

        memory = self.memory_manager.create_observation(
            content=observation.content,
            now=observation.now,
            embedding=observation.embedding,
            context=ObservationContext(
                agent_name=observation.agent_name,
                identity_stable_set=input.profile.fixed.identity_stable_set,
                current_plan=observation.current_plan,
            ),
            importance=observation.importance,
        )
        self.reflection_graph.record_observation_importance(
            importance=memory.importance
        )
        return {"should_reflect": self.reflection_graph.should_reflect()}

    def _route_after_persist_observation(
        self, state: AgentBrainGraphState
    ) -> Literal["run_reflection", "determine_context"]:
        if state["should_reflect"]:
            return "run_reflection"
        return "determine_context"

    def _run_reflection(self, state: AgentBrainGraphState) -> dict[str, bool]:
        input = state["input"]
        self.reflection_graph.reflect(now=input.current_time)
        return {"should_reflect": False}

    def _determine_context(
        self, state: AgentBrainGraphState
    ) -> dict[str, DetermineContext]:
        observation = require_state_value(state["observation"], key="observation")
        input = state["input"]

        prompt_builders_module = cast(
            PromptBuildersModule,
            cast(object, import_module("agents.prompt_builders")),
        )
        retrieval_query = prompt_builders_module.build_retrieval_query(
            agent_identity=self.agent_identity,
            observation_content=observation.content,
            dialogue_history=input.dialogue_history,
            profile=input.profile,
        )
        retrieved_memories = self.memory_manager.get_retrieval_memories(
            query=retrieval_query,
            current_time=input.current_time,
        )
        return {
            "determine_context": DetermineContext(
                observation=observation,
                dialogue_history=input.dialogue_history,
                dialogue_arc=input.dialogue_arc,
                profile=input.profile,
                retrieved_memories=retrieved_memories,
                language=input.language,
            )
        }

    def _decide_reaction(
        self, state: AgentBrainGraphState
    ) -> dict[str, ReactionDecision]:
        determine_context = require_state_value(
            state["determine_context"],
            key="determine_context",
        )
        return {
            "reaction_decision": self.llm_gateway.decide_reaction(
                ReactionDecisionInput(
                    agent_identity=self.agent_identity,
                    current_time=determine_context.observation.now,
                    observation_content=determine_context.observation.content,
                    dialogue_history=determine_context.dialogue_history,
                    profile=determine_context.profile,
                    retrieved_memories=determine_context.retrieved_memories,
                    dialogue_arc=determine_context.dialogue_arc,
                    language=determine_context.language,
                )
            )
        }

    def _finalize_action(
        self, state: AgentBrainGraphState
    ) -> dict[str, ActionLoopResult]:
        input = state["input"]
        reaction_decision = require_state_value(
            state["reaction_decision"],
            key="reaction_decision",
        )

        candidate_talk = reaction_decision.reaction.strip()
        should_speak = reaction_decision.should_react and bool(candidate_talk)
        talk = candidate_talk if should_speak else None
        action_intent = (
            "react_to_partner"
            if reaction_decision.should_react
            else "continue_current_plan"
        )
        if reaction_decision.should_react and talk is None:
            action_intent = "react_without_utterance"

        if should_speak and talk is not None:
            self.observation_writer(
                content=f"나는 이렇게 반응하기로 결정했다: {talk}",
                now=input.current_time,
                profile=input.profile,
            )

        silent_reason = ""
        if not should_speak:
            if not reaction_decision.should_react:
                silent_reason = "llm_declined_reaction"
            elif not candidate_talk:
                silent_reason = "empty_reaction_text"
            else:
                silent_reason = "suppressed_unknown"

        return {
            "result": ActionLoopResult(
                current_time=input.current_time,
                talk=talk,
                utterance=talk,
                speak_decision=should_speak,
                action_intent=action_intent,
                end_dialogue=reaction_decision.end_dialogue,
                silent_reason=silent_reason,
                reaction_trace=reaction_decision.trace,
                diagnostics=build_action_diagnostics(
                    reaction_decision=reaction_decision,
                    speak_decision=should_speak,
                    action_intent=action_intent,
                    silent_reason=silent_reason,
                ),
            )
        }
