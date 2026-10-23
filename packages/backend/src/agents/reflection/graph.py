import datetime
from concurrent.futures import ThreadPoolExecutor
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


# 성찰 질문 1개당 검색 개수. 원 구현(reverie run_reflect)의 new_retrieve(n_count=30)를 따른다.
# SPEC §6 참조. get_retrieval_memories의 기본값(3)은 다른 호출자가 쓰므로 바꾸지 않는다.
REFLECTION_RETRIEVAL_TOP_K = 30

# 성찰 초점 질문 개수 상한. SPEC §6.
REFLECTION_QUESTION_COUNT = 3

# reflect() 밖으로 내보내지 않는 오류. ValueError는 코드 결함을 가릴 수 있어 LLM 호출 지점에서만 잡는다.
_REFLECT_ERRORS = (RuntimeError, TimeoutError)
_LLM_CALL_ERRORS = (RuntimeError, TimeoutError, ValueError)

STATE_GRAPH = cast(StateGraphFactory, GRAPH_STATE_FACTORY)


class ReflectionGraphState(TypedDict):
    now: datetime.datetime
    recent_memories: list[MemoryObject]
    questions: list[str]
    retrieved_by_question: list[list[MemoryObject]]
    insights_by_question: list[list[InsightWithCitation]]
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
        """성찰을 실행한다. LLM 오류는 밖으로 내지 않고, 성공 여부와 무관하게 누적 중요도를 리셋한다."""
        try:
            _ = self.graph.invoke(self._initial_state(now=now))
        except _REFLECT_ERRORS:
            pass
        finally:
            self.reflection.clear_importance()

    def _build_graph(self) -> ReflectionGraphInvoker:
        builder = STATE_GRAPH(ReflectionGraphState)
        builder.add_node("load_recent_memories", self._load_recent_memories)
        builder.add_node("generate_questions", self._generate_questions)
        builder.add_node("retrieve_all", self._retrieve_all)
        builder.add_node("generate_insights_all", self._generate_insights_all)
        builder.add_node("persist_all", self._persist_all)

        builder.add_edge(GRAPH_START, "load_recent_memories")
        builder.add_edge("load_recent_memories", "generate_questions")
        builder.add_conditional_edges(
            "generate_questions",
            self._route_after_generate_questions,
            {"retrieve_all": "retrieve_all", "__end__": GRAPH_END},
        )
        builder.add_edge("retrieve_all", "generate_insights_all")
        builder.add_edge("generate_insights_all", "persist_all")
        builder.add_edge("persist_all", GRAPH_END)
        return builder.compile()

    @staticmethod
    def _initial_state(*, now: datetime.datetime) -> ReflectionGraphState:
        return ReflectionGraphState(
            now=now,
            recent_memories=[],
            questions=[],
            retrieved_by_question=[],
            insights_by_question=[],
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
    ) -> dict[str, list[str]]:
        try:
            questions = self.llm_gateway.generate_salient_high_level_questions(
                agent_name=self.agent_name,
                memories=state["recent_memories"],
            )
        except ValueError:
            questions = []
        return {"questions": questions[:REFLECTION_QUESTION_COUNT]}

    def _route_after_generate_questions(
        self,
        state: ReflectionGraphState,
    ) -> Literal["retrieve_all", "__end__"]:
        if not state["questions"]:
            return "__end__"
        return "retrieve_all"

    def _retrieve_all(
        self,
        state: ReflectionGraphState,
    ) -> dict[str, list[list[MemoryObject]]]:
        # 이번 회차 통찰을 저장하기 전에 모든 질문의 검색을 끝낸다(원 구현 순서).
        return {
            "retrieved_by_question": self.memory_manager.get_retrieval_memories_many(
                state["questions"],
                current_time=state["now"],
                top_k=REFLECTION_RETRIEVAL_TOP_K,
            )
        }

    def _generate_insights_for(
        self, memories: list[MemoryObject]
    ) -> list[InsightWithCitation]:
        try:
            return self.llm_gateway.generate_insights_with_citation_key(
                agent_name=self.agent_name,
                memories=memories,
            )
        except _LLM_CALL_ERRORS:
            return []

    def _generate_insights_all(
        self,
        state: ReflectionGraphState,
    ) -> dict[str, list[list[InsightWithCitation]]]:
        retrieved = state["retrieved_by_question"]
        with ThreadPoolExecutor(max_workers=len(retrieved)) as pool:
            # map은 입력(질문) 순서대로 결과를 돌려준다.
            results = list(pool.map(self._generate_insights_for, retrieved))
        return {"insights_by_question": results}

    def _persist_all(
        self,
        state: ReflectionGraphState,
    ) -> dict[str, int]:
        insights = [i for group in state["insights_by_question"] for i in group]
        created = self.memory_manager.create_reflections(
            insights,
            now=state["now"],
            context=ReflectionContext(
                agent_name=self.agent_name,
                identity_stable_set=self.identity_stable_set,
            ),
        )
        return {"persisted_reflection_count": len(created)}
