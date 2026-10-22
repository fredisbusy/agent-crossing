import datetime
from importlib import import_module
from typing import Literal, Protocol, cast

import numpy as np
from typing_extensions import TypedDict

from agents.agent import AgentIdentity, AgentProfile
from agents.memory.memory_object import MemoryObject
from agents.planning.models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)
from agents.planning.state import (
    AgentPlanState,
    PlanTickContext,
    ensure_tick_plan_context,
    format_plan_item,
    update_current_plan_for_dialogue,
)
from agents.reaction import ReactionDecision, ReactionDecisionInput, ReactionDecisionTrace
from llm.embedding_encoder import EmbeddingEncodingContext

from ..decision_diagnostics import build_action_diagnostics
from ..graph_support import (
    GRAPH_END,
    GRAPH_START,
    GRAPH_STATE_FACTORY,
    require_state_value,
)
from ..memory.memory_manager import ObservationContext, PlanContext
from .observation_text import build_observation_text
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

    def create_plan(
        self,
        *,
        content: str,
        now: datetime.datetime,
        context: PlanContext,
        importance: int | None = None,
    ) -> MemoryObject: ...


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

    def generate_hourly_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        day_plan_item: DayPlanItem,
    ) -> list[HourlyPlanItem]: ...

    def generate_minute_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        hourly_plan_item: HourlyPlanItem,
    ) -> list[MinutePlanItem]: ...


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
    plan_context: PlanTickContext | None
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
        self.plan_state: AgentPlanState = AgentPlanState()
        self._last_plan_memory_key: tuple[datetime.datetime, datetime.datetime, str] | None = (
            None
        )
        self.graph: AgentBrainGraphInvoker = self._build_graph()

    def run(self, input: ActionLoopInput) -> ActionLoopResult:
        final_state = self.graph.invoke(
            AgentBrainGraphState(
                input=input,
                plan_context=None,
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
        # 1. 현재 상황을 인지한다. 인지할때 월드에서 현재 상황을 조회해서 주입한다.
        builder.add_node("perceive", self._perceive)
        # 2. 인지된 정보들을 observation으로 메모리에 저장 (reflection 조건 충족 시 reflection도 함께 저장)
        builder.add_node("persist_observation", self._persist_observation)
        # 2-1. reflection 조건 충족 시 reflection graph를 실행한다.
        builder.add_node("run_reflection", self._run_reflection)
        # 3. 상황판단을 한다.
        builder.add_node("determine_context", self._determine_context)
        # 4. retrieval 결과 이후 현재 시점의 day/hour/minute plan을 갱신한다.
        builder.add_node("update_plan_context", self._update_plan_context)
        # 5. 상황판단에 따라 반응을 결정한다.
        builder.add_node("decide_reaction", self._decide_reaction)
        # 6. 반응에 따라 구체적인 행동 및 출력을 한다.
        builder.add_node("finalize_action", self._finalize_action)

        builder.add_edge(GRAPH_START, "perceive")
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
        builder.add_edge("determine_context", "update_plan_context")
        builder.add_edge("update_plan_context", "decide_reaction")
        builder.add_edge("decide_reaction", "finalize_action")
        builder.add_edge("finalize_action", GRAPH_END)
        return builder.compile()

    def _update_plan_context(
        self, state: AgentBrainGraphState
    ) -> dict[str, object]:
        input = state["input"]
        determine_context = require_state_value(
            state["determine_context"],
            key="determine_context",
        )
        partner_name = (
            input.observed_entities[0]
            if input.observed_entities and input.observed_entities[0].strip()
            else None
        )
        plan_context = ensure_tick_plan_context(
            state=self.plan_state,
            planner=self.planner,
            agent_identity=self.agent_identity,
            profile=input.profile,
            current_time=input.current_time,
        )
        latest_partner_utterance = _latest_partner_utterance(input.dialogue_history)
        if latest_partner_utterance is not None:
            plan_context = update_current_plan_for_dialogue(
                state=self.plan_state,
                profile=input.profile,
                current_time=input.current_time,
                partner_name=partner_name,
                latest_partner_utterance=latest_partner_utterance,
            )
        if plan_context.plan_updated:
            self._create_plan_memory_if_changed(
                input=input,
                plan_context=plan_context,
            )
        return {
            "plan_context": plan_context,
            "determine_context": DetermineContext(
                observation=determine_context.observation,
                retrieved_memories=determine_context.retrieved_memories,
                dialogue_history=determine_context.dialogue_history,
                dialogue_arc=determine_context.dialogue_arc,
                profile=determine_context.profile,
                language=determine_context.language,
                current_plan_item=plan_context.current_plan_item,
                next_plan_item=plan_context.next_plan_item,
                plan_updated=plan_context.plan_updated,
                replan_reason=plan_context.replan_reason,
            ),
        }

    def _create_plan_memory_if_changed(
        self,
        *,
        input: ActionLoopInput,
        plan_context: PlanTickContext,
    ) -> None:
        plan_memory_item = plan_context.current_plan_item
        if plan_memory_item is None:
            return
        memory_key = (
            plan_memory_item.start_time,
            plan_memory_item.end_time,
            plan_memory_item.action_content,
        )
        if memory_key == self._last_plan_memory_key:
            return

        content = (
            "Plan updated after dialogue. "
            f"agent={self.agent_identity.name}; "
            f"time={input.current_time.isoformat()}; "
            f"reason={plan_context.replan_reason}; "
            f"current_plan={format_plan_item(plan_context.current_plan_item)}"
        )
        _ = self.memory_manager.create_plan(
            content=content,
            now=input.current_time,
            context=PlanContext(
                agent_name=self.agent_identity.name,
                identity_stable_set=input.profile.fixed.identity_stable_set,
                current_plan=input.profile.extended.current_plan_context[0]
                if input.profile.extended.current_plan_context
                else None,
            ),
            importance=None,
        )
        self._last_plan_memory_key = memory_key

    def _perceive(self, state: AgentBrainGraphState) -> dict[str, Observation]:
        input = state["input"]
        current_plan = (
            input.profile.extended.current_plan_context[0]
            if input.profile.extended.current_plan_context
            else None
        )
        context = input.world_context or {}

        content = build_observation_text(
            agent_name=self.agent_identity.name,
            location=context.get("location"),
            observed_entities=input.observed_entities,
            observed_events=input.observed_events,
        )
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
        try:
            self.reflection_graph.reflect(now=input.current_time)
        except Exception:
            pass
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
        reaction_input = ReactionDecisionInput(
            agent_identity=self.agent_identity,
            current_time=determine_context.observation.now,
            observation_content=determine_context.observation.content,
            dialogue_history=determine_context.dialogue_history,
            profile=determine_context.profile,
            retrieved_memories=determine_context.retrieved_memories,
            dialogue_arc=determine_context.dialogue_arc,
            language=determine_context.language,
        )
        try:
            reaction_decision = self.llm_gateway.decide_reaction(reaction_input)
        except Exception as exc:
            reaction_decision = ReactionDecision(
                should_react=False,
                reaction="",
                reason="llm_gateway_error",
                trace=ReactionDecisionTrace(
                    raw_response="",
                    parse_success=False,
                    parse_error=f"llm_gateway_error:{type(exc).__name__}",
                ),
            )
        return {
            "reaction_decision": reaction_decision
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
                content=f"I decided to react: {talk}",
                now=input.current_time,
                profile=input.profile,
            )

        silent_reason = ""
        if not should_speak:
            if reaction_decision.reason == "llm_gateway_error":
                silent_reason = "llm_gateway_error"
            elif not reaction_decision.should_react:
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
                current_plan_item=format_plan_item(
                    state["plan_context"].current_plan_item
                    if state["plan_context"] is not None
                    else None
                ),
                plan_updated=(
                    state["plan_context"].plan_updated
                    if state["plan_context"] is not None
                    else False
                ),
                replan_reason=(
                    state["plan_context"].replan_reason
                    if state["plan_context"] is not None
                    else ""
                ),
            )
        }


def _latest_partner_utterance(dialogue_history: list[tuple[str, str]]) -> str | None:
    for partner_talk, _ in reversed(dialogue_history):
        if partner_talk.strip():
            return partner_talk
    return None
