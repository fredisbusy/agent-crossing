import datetime

from agents.agent import AgentIdentity, AgentProfile
from agents.planning import Planner
from agents.reaction import ReactionDecision
from llm.llm_gateway import LlmGateway

from .brain import ActionLoopInput, ActionLoopResult, AgentBrainGraphRunner
from .memory.memory_manager import MemoryManager, ObservationContext
from .reflection import ReflectionGraphRunner


class AgentBrain:
    """Agent의 인지, 상황판단, 행동결정 등을 담당하는 핵심 클래스."""

    def __init__(
        self,
        *,
        agent_identity: AgentIdentity,
        memory_manager: MemoryManager,
        reflection_graph: ReflectionGraphRunner,
        llm_gateway: LlmGateway,
        planner: Planner | None = None,
    ):
        self.planner: Planner | None = planner
        self.memory_manager: MemoryManager = memory_manager
        self.reflection_graph: ReflectionGraphRunner = reflection_graph
        self.llm_gateway: LlmGateway = llm_gateway
        self.agent_identity: AgentIdentity = agent_identity
        self.brain_graph: AgentBrainGraphRunner = AgentBrainGraphRunner(
            agent_identity=agent_identity,
            memory_manager=memory_manager,
            embedding_encoder=memory_manager.embedding_encoder,
            reflection_graph=reflection_graph,
            llm_gateway=llm_gateway,
            observation_writer=self.queue_observation,
            planner=planner,
        )

    def queue_observation(
        self,
        *,
        content: str,
        now: datetime.datetime,
        profile: AgentProfile,
        current_plan: str | None = None,
        importance: int | None = None,
    ) -> None:
        if current_plan is not None:
            final_current_plan = current_plan
        elif profile.extended.current_plan_context:
            final_current_plan = profile.extended.current_plan_context[0]
        else:
            final_current_plan = None
        memory = self.memory_manager.create_observation_from_text(
            content=content,
            now=now,
            context=ObservationContext(
                agent_name=self.agent_identity.name,
                identity_stable_set=profile.fixed.identity_stable_set,
                current_plan=final_current_plan,
            ),
            importance=importance,
        )
        self.reflection_graph.record_observation_importance(
            importance=memory.importance
        )

    def ingest_seed_memory(
        self,
        *,
        content: str,
        now: datetime.datetime,
        importance: int,
        identity_stable_set: list[str],
        current_plan: str | None,
    ) -> None:
        memory = self.memory_manager.create_observation_from_text(
            content=content,
            now=now,
            context=ObservationContext(
                agent_name=self.agent_identity.name,
                identity_stable_set=identity_stable_set,
                current_plan=current_plan,
            ),
            importance=importance,
        )
        self.reflection_graph.record_observation_importance(
            importance=memory.importance
        )

    def action_loop(
        self, input: ActionLoopInput
    ) -> tuple[ActionLoopResult, ReactionDecision | None]:
        # 1. 현재 상황을 인지한다. 인지할때 월드에서 현재 상황을 조회해서 주입한다.
        # 2. 인지된 정보들을 observation으로 메모리에 저장 (reflection 조건 충족 시 reflection도 함께 저장)
        # 3. 상황판단을 한다.
        # 4. 상황판단에 따라 반응을 결정한다.
        # 5. 반응에 때라 구체적인 행동 및 출력을 한다.
        #
        # 반환되는 두 번째 값(ReactionDecision)은 governance/diagnostics 원천
        # 데이터다. Brain 결과 객체(ActionLoopResult)에는 병합하지 않는다.
        return self.brain_graph.run(input)
