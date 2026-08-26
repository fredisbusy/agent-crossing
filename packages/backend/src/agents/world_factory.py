import datetime
from pathlib import Path

from agents.agent import AgentContext, AgentProfile, ExtendedPersona, FixedPersona
from agents.agent_brain import AgentBrain
from agents.planning import Planner
from agents.persona_loader import AgentPersona, PersonaLoader, apply_persona_to_brain
from agents.reflection import Reflection, ReflectionGraphRunner
from agents.sim_agent import SimAgent
from llm.clients.provider_factory import ProviderClient
from llm.embedding_encoder import LlmEmbeddingEncoder
from llm.importance_scorer import LlmImportanceScorer
from llm.llm_gateway import LlmGateway

from .memory.memory_manager import MemoryManager
from .memory.memory_stream import MemoryStream


def _profile_from_persona(persona: AgentPersona) -> AgentProfile:
    return AgentProfile(
        fixed=FixedPersona(
            identity_stable_set=list(persona.identity_stable_set),
            relationship_baselines=dict(persona.relationship_baselines),
        ),
        extended=ExtendedPersona(
            lifestyle_and_routine=list(persona.lifestyle_and_routine),
            current_plan_context=list(persona.current_plan_context),
        ),
    )


def _build_agent(
    persona: AgentPersona,
    llm_client: ProviderClient,
    embedding_model: str,
) -> SimAgent:
    memory_stream = MemoryStream()
    importance_scorer = LlmImportanceScorer(client=llm_client)
    embedding_encoder = LlmEmbeddingEncoder(client=llm_client, model=embedding_model)
    memory_manager = MemoryManager(
        memory_stream=memory_stream,
        importance_scorer=importance_scorer,
        embedding_encoder=embedding_encoder,
    )
    llm_gateway = LlmGateway(llm_client, embedding_encoder=embedding_encoder)
    planner = Planner(llm_gateway)
    reflection_graph = ReflectionGraphRunner(
        reflection=Reflection(),
        memory_manager=memory_manager,
        llm_gateway=llm_gateway,
        agent_name=persona.agent.name,
        identity_stable_set=list(persona.identity_stable_set),
    )
    brain = AgentBrain(
        agent_identity=persona.agent,
        memory_manager=memory_manager,
        reflection_graph=reflection_graph,
        llm_gateway=llm_gateway,
        planner=planner,
    )
    context = AgentContext(
        identity=persona.agent,
        profile=_profile_from_persona(persona),
        brain=brain,
        memory_service=memory_manager,
    )
    return SimAgent(context=context)


def init_agents(
    *,
    persona_dir: str | Path,
    agent_persona_names: list[str],
    llm_client: ProviderClient,
    embedding_model: str,
    now: datetime.datetime,
) -> list[SimAgent]:
    if not agent_persona_names:
        raise ValueError("agent_persona_names must not be empty")

    persona_loader = PersonaLoader(persona_dir)

    agents: list[SimAgent] = []
    for persona_name in agent_persona_names:
        persona = persona_loader.load(persona_name)
        agent = _build_agent(persona, llm_client, embedding_model)
        apply_persona_to_brain(brain=agent.brain, persona=persona, now=now)
        agents.append(agent)

    return agents
