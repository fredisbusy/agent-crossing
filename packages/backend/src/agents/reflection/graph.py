import datetime
from typing import Literal, Protocol, cast

from typing_extensions import TypedDict

from llm.llm_gateway import InsightWithCitation, LlmGateway

from ..graph_support import GRAPH_END, GRAPH_START, GRAPH_STATE_FACTORY
from ..memory.memory_manager import MemoryManager, ReflectionContext
from ..memory.memory_object import MemoryObject
from .state import Reflection


class ReflectionGraphBuilder(Protocol):
    def add_node(self, node: str, action: object) -> None: ...

    def add_edge(self, start_key: object, end_key: object) -> None: ...

    def add_conditional_edges(
        self,
        source: str,
        path: object,
        path_map: dict[str, object],
    ) -> None: ...

    def compile(self) -> "ReflectionGraphInvoker": ...


class ReflectionGraphInvoker(Protocol):
    def invoke(self, input: "ReflectionGraphState") -> "ReflectionGraphState": ...


class StateGraphFactory(Protocol):
    def __call__(
        self, state_schema: type["ReflectionGraphState"]
    ) -> ReflectionGraphBuilder: ...


STATE_GRAPH = cast(StateGraphFactory, GRAPH_STATE_FACTORY)


class ReflectionGraphState(TypedDict):
    now: datetime.datetime
    recent_memories: list[MemoryObject]
    questions: list[str]
    question_index: int
    active_question: str
    retrieved_memories: list[MemoryObject]
    generated_insights: list[InsightWithCitation]
    persisted_reflection_count: int


class ReflectionGraphRunner:
    def __init__(
        self,
        *,
        reflection: Reflection,
        memory_manager: MemoryManager,
        llm_gateway: LlmGateway,
        agent_name: str,
        identity_stable_set: list[str],
    ):
        self.reflection: Reflection = reflection
        self.memory_manager: MemoryManager = memory_manager
        self.llm_gateway: LlmGateway = llm_gateway
        self.agent_name: str = agent_name
        self.identity_stable_set: list[str] = list(identity_stable_set)
        self.graph: ReflectionGraphInvoker = self._build_graph()

    def record_observation_importance(self, importance: int) -> None:
        self.reflection.record_observation_importance(importance=importance)

    def should_reflect(self) -> bool:
        return self.reflection.should_reflect()

    def reflect(self, *, now: datetime.datetime) -> None:
        _ = self.graph.invoke(self._initial_state(now=now))
        self.reflection.clear_importance()

    def _build_graph(self) -> ReflectionGraphInvoker:
        builder = STATE_GRAPH(ReflectionGraphState)
        builder.add_node("load_recent_memories", self._load_recent_memories)
        builder.add_node("generate_questions", self._generate_questions)
        builder.add_node("prepare_question", self._prepare_question)
        builder.add_node("retrieve_memories", self._retrieve_memories)
        builder.add_node("generate_insights", self._generate_insights)
        builder.add_node("persist_insights", self._persist_insights)
        builder.add_node("advance_question", self._advance_question)

        builder.add_edge(GRAPH_START, "load_recent_memories")
        builder.add_edge("load_recent_memories", "generate_questions")
        builder.add_conditional_edges(
            "generate_questions",
            self._route_after_generate_questions,
            {
                "prepare_question": "prepare_question",
                "__end__": GRAPH_END,
            },
        )
        builder.add_edge("prepare_question", "retrieve_memories")
        builder.add_edge("retrieve_memories", "generate_insights")
        builder.add_edge("generate_insights", "persist_insights")
        builder.add_conditional_edges(
            "persist_insights",
            self._route_after_persist_insights,
            {
                "advance_question": "advance_question",
                "__end__": GRAPH_END,
            },
        )
        builder.add_conditional_edges(
            "advance_question",
            self._route_after_advance_question,
            {
                "prepare_question": "prepare_question",
                "__end__": GRAPH_END,
            },
        )

        return builder.compile()

    @staticmethod
    def _initial_state(*, now: datetime.datetime) -> ReflectionGraphState:
        return ReflectionGraphState(
            now=now,
            recent_memories=[],
            questions=[],
            question_index=0,
            active_question="",
            retrieved_memories=[],
            generated_insights=[],
            persisted_reflection_count=0,
        )

    def _load_recent_memories(
        self,
        state: ReflectionGraphState,
    ) -> dict[str, list[MemoryObject]]:
        _ = state
        return {
            "recent_memories": self.memory_manager.get_recent_memories(limit=100),
        }

    def _generate_questions(
        self,
        state: ReflectionGraphState,
    ) -> dict[str, object]:
        questions = self.llm_gateway.generate_salient_high_level_questions(
            agent_name=self.agent_name,
            memories=state["recent_memories"],
        )
        return {
            "questions": questions,
            "question_index": 0,
        }

    def _route_after_generate_questions(
        self,
        state: ReflectionGraphState,
    ) -> Literal["prepare_question", "__end__"]:
        if not state["questions"]:
            return "__end__"
        return "prepare_question"

    def _prepare_question(
        self,
        state: ReflectionGraphState,
    ) -> dict[str, str]:
        return {"active_question": state["questions"][state["question_index"]]}

    def _retrieve_memories(
        self,
        state: ReflectionGraphState,
    ) -> dict[str, list[MemoryObject]]:
        return {
            "retrieved_memories": self.memory_manager.get_retrieval_memories(
                query=state["active_question"],
                current_time=state["now"],
            )
        }

    def _generate_insights(
        self,
        state: ReflectionGraphState,
    ) -> dict[str, list[InsightWithCitation]]:
        return {
            "generated_insights": self.llm_gateway.generate_insights_with_citation_key(
                agent_name=self.agent_name,
                memories=state["retrieved_memories"],
            )
        }

    def _persist_insights(
        self,
        state: ReflectionGraphState,
    ) -> dict[str, int]:
        persisted_count = 0
        for insight in state["generated_insights"]:
            persisted = self.memory_manager.create_reflection(
                insight,
                now=state["now"],
                context=ReflectionContext(
                    agent_name=self.agent_name,
                    identity_stable_set=self.identity_stable_set,
                ),
            )
            if persisted is not None:
                persisted_count += 1

        return {
            "persisted_reflection_count": (
                state["persisted_reflection_count"] + persisted_count
            )
        }

    def _route_after_persist_insights(
        self,
        state: ReflectionGraphState,
    ) -> Literal["advance_question", "__end__"]:
        if state["question_index"] + 1 >= len(state["questions"]):
            return "__end__"
        return "advance_question"

    def _advance_question(self, state: ReflectionGraphState) -> dict[str, int]:
        return {"question_index": state["question_index"] + 1}

    def _route_after_advance_question(
        self,
        state: ReflectionGraphState,
    ) -> Literal["prepare_question", "__end__"]:
        if state["question_index"] >= len(state["questions"]):
            return "__end__"
        return "prepare_question"
