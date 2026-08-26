"""§7.1.1 information diffusion experiment runner.

Wires the primitives in `agents/evaluation/` (interview grounding,
diffusion rate) into an actual multi-agent run: inject a seed fact into
one agent's memory, let the town's scheduler run for a while (so agents
can encounter each other, converse, and pass the fact along), then
interview every agent and report how many ended up "aware" of it.

This is the runner TODO.md's §5-A item 1 called out as missing — the
diffusion-rate primitives existed and were unit-tested, but nothing drove
them against a real running town.
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from agents.evaluation.diffusion import (
    DiffusionResult,
    RelationshipDensityResult,
    compute_diffusion_rate,
    compute_relationship_density,
)
from agents.evaluation.interview import InterviewAnswer, InterviewGate, InterviewQuestion
from agents.memory.memory_manager import ObservationContext
from agents.persona_loader import PersonaLoader
from agents.reaction.encounter import EncounterGate
from agents.sim_agent import SimAgent
from settings import (
    EMBEDDING_MODEL,
    GOOGLE_AI_STUDIO_API_KEY,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)
from world.runtime import WorldRuntime, WorldRuntimeConfig, build_world_runtime
from world.spatial import SpatialAgentSeed, SpatialWorldRuntime
from world.world_map import load_world_map


@dataclass(frozen=True)
class DiffusionExperimentConfig:
    agent_persona_names: list[str]
    """실험에 참여할 에이전트 persona id 목록 — 로스터 크기가 곧 §7.1의 |V|."""
    seed_holder_agent_id: str
    """seed fact를 초기 memory로 주입할 agent의 agent_id (persona의 agent_id, 소문자)."""
    seed_fact_content: str
    """seed_holder에게만 주입할 관찰 문장(한국어)."""
    interview_question: str
    """실험 종료 시 전 agent에게 물을 yes/no 질문(한국어, §7.1 "Did you know that...?" 형식)."""
    run_duration_seconds: float
    """스케줄러를 실제로 돌릴 wall-clock 시간(초) — 이 동안 조우/대화/plan이 진행된다."""
    base_url: str | None
    api_key: str | None
    llm_model: str
    embedding_model: str
    timeout_seconds: float | None
    persona_dir: str
    language: Literal["ko"] = "ko"
    tick_interval_seconds: float = 1.0
    cognitive_time_step_seconds: int = 60
    turn_time_step_seconds: int = 300


_DEFAULT_PERSONA_DIR = Path(__file__).resolve().parents[1] / "persona"

DEFAULT_CONFIG = DiffusionExperimentConfig(
    agent_persona_names=["Jiho", "Sujin", "Minji", "Jungwoo", "Haeun", "Taeo"],
    seed_holder_agent_id="jungwoo",
    seed_fact_content=(
        "하은이 이번 주 토요일 저녁에 달맞이꽃 공원에서 작은 그림 전시를 연다는 소식을 들었다."
    ),
    interview_question=(
        "하은이 이번 주 토요일 저녁에 달맞이꽃 공원에서 그림 전시를 연다는 걸 아는가?"
    ),
    run_duration_seconds=120.0,
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY or GOOGLE_AI_STUDIO_API_KEY,
    llm_model=LLM_MODEL,
    embedding_model=EMBEDDING_MODEL,
    timeout_seconds=LLM_TIMEOUT_SECONDS,
    persona_dir=str(_DEFAULT_PERSONA_DIR),
)


@dataclass(frozen=True)
class DiffusionExperimentReport:
    seed_holder_name: str
    seed_fact_content: str
    interview_question: str
    run_duration_seconds: float
    turns_elapsed: int
    diffusion: DiffusionResult
    per_agent_aware: dict[str, bool]
    per_agent_reason: dict[str, str]
    relationship_density_before: RelationshipDensityResult
    relationship_density_after: RelationshipDensityResult

    def to_json(self) -> str:
        payload = asdict(self)
        payload["diffusion"] = {
            "aware_agent_names": self.diffusion.aware_agent_names,
            "aware_count": self.diffusion.aware_count,
            "total_agent_count": self.diffusion.total_agent_count,
            "rate": self.diffusion.rate,
        }
        for key in ("relationship_density_before", "relationship_density_after"):
            result: RelationshipDensityResult = getattr(self, key)
            payload[key] = {
                "edges": [asdict(edge) for edge in result.edges],
                "edge_count": result.edge_count,
                "agent_count": result.agent_count,
                "density": result.density,
            }
        return json.dumps(payload, ensure_ascii=False, indent=2)


async def run_diffusion_experiment(
    *, config: DiffusionExperimentConfig
) -> DiffusionExperimentReport:
    # `_start_dialogue_for_real_encounter` (and therefore every organic
    # conversation an agent could pass the seed fact through) is a no-op
    # without a real SpatialWorldRuntime, so this must be built and wired
    # in exactly like `api/main.py::_build_runtime_bundle` does — a diffusion
    # experiment with no spatial runtime would just be N agents planning in
    # isolation forever.
    world_map = load_world_map()
    persona_loader = PersonaLoader(config.persona_dir)
    personas = [
        persona_loader.load(name) for name in config.agent_persona_names
    ]
    spatial_runtime = SpatialWorldRuntime(
        world_map=world_map,
        seeds=[
            SpatialAgentSeed(
                agent_id=persona.agent.id, name=persona.agent.name, plan_context=()
            )
            for persona in personas
        ],
    )
    runtime = build_world_runtime(
        config=WorldRuntimeConfig(
            agent_persona_names=config.agent_persona_names,
            base_url=config.base_url,
            api_key=config.api_key,
            llm_model=config.llm_model,
            embedding_model=config.embedding_model,
            timeout_seconds=config.timeout_seconds,
            persona_dir=config.persona_dir,
            language=config.language,
            tick_interval_seconds=config.tick_interval_seconds,
            cognitive_time_step_seconds=config.cognitive_time_step_seconds,
            turn_time_step_seconds=config.turn_time_step_seconds,
        ),
        spatial_runtime=spatial_runtime,
    )

    seed_holder = _require_agent(runtime, config.seed_holder_agent_id)
    current_plan_context = seed_holder.profile.extended.current_plan_context
    seed_holder.memory_service.create_observation_from_text(
        content=config.seed_fact_content,
        now=runtime.current_time,
        context=ObservationContext(
            agent_name=seed_holder.name,
            identity_stable_set=list(seed_holder.profile.fixed.identity_stable_set),
            current_plan=current_plan_context[0] if current_plan_context else None,
        ),
    )

    # Reuse the same LLM client the town's own gates already use rather than
    # opening a second connection with duplicated config.
    encounter_gate = runtime.encounter_gate
    assert isinstance(encounter_gate, EncounterGate)
    interview_gate = InterviewGate(generation_client=encounter_gate.generation_client)

    # §7.1.1 start-of-run baseline: measured *after* the seed fact is
    # injected but *before* the scheduler runs, so the seed itself never
    # counts as an acquaintance edge — only pre-existing mutual awareness
    # does.
    relationship_density_before = compute_relationship_density(
        agent_names=[agent.name for agent in runtime.agents],
        mutual_acknowledgment_pairs=_mutual_acknowledgment_pairs(
            runtime=runtime, interview_gate=interview_gate
        ),
    )

    await runtime.start_scheduler()
    await asyncio.sleep(config.run_duration_seconds)
    await runtime.pause_scheduler()

    relationship_density_after = compute_relationship_density(
        agent_names=[agent.name for agent in runtime.agents],
        mutual_acknowledgment_pairs=_mutual_acknowledgment_pairs(
            runtime=runtime, interview_gate=interview_gate
        ),
    )

    per_agent_aware: dict[str, bool] = {}
    per_agent_reason: dict[str, str] = {}
    answers_by_agent_name: dict[str, InterviewAnswer] = {}
    for agent in runtime.agents:
        answer = interview_gate.ask(
            question=InterviewQuestion(
                agent_name=agent.name,
                question=config.interview_question,
                current_time=runtime.current_time,
            ),
            memory_service=agent.memory_service,
        )
        answers_by_agent_name[agent.name] = answer
        per_agent_aware[agent.name] = answer.aware
        per_agent_reason[agent.name] = answer.reason

    diffusion = compute_diffusion_rate(answers_by_agent_name)

    return DiffusionExperimentReport(
        seed_holder_name=seed_holder.name,
        seed_fact_content=config.seed_fact_content,
        interview_question=config.interview_question,
        run_duration_seconds=config.run_duration_seconds,
        turns_elapsed=runtime.turn,
        diffusion=diffusion,
        per_agent_aware=per_agent_aware,
        per_agent_reason=per_agent_reason,
        relationship_density_before=relationship_density_before,
        relationship_density_after=relationship_density_after,
    )


def _mutual_acknowledgment_pairs(
    *, runtime: WorldRuntime, interview_gate: InterviewGate
) -> list[tuple[str, str]]:
    """§7.1.1: interview every ordered agent pair with "Do you know of X?"

    and keep only pairs where *both* directions answer aware=True (grounded
    in that agent's own memory stream, per `InterviewGate.ask`).
    """
    agents = runtime.agents
    aware_directional: dict[tuple[str, str], bool] = {}
    for agent in agents:
        for other in agents:
            if agent.name == other.name:
                continue
            answer = interview_gate.ask(
                question=InterviewQuestion(
                    agent_name=agent.name,
                    question=f"{other.name}을(를) 아는가?",
                    current_time=runtime.current_time,
                ),
                memory_service=agent.memory_service,
            )
            aware_directional[(agent.name, other.name)] = answer.aware

    pairs: list[tuple[str, str]] = []
    seen: set[frozenset[str]] = set()
    for agent in agents:
        for other in agents:
            if agent.name == other.name:
                continue
            pair_key = frozenset((agent.name, other.name))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            if aware_directional.get((agent.name, other.name)) and aware_directional.get(
                (other.name, agent.name)
            ):
                pairs.append((agent.name, other.name))
    return pairs


def _require_agent(runtime: WorldRuntime, agent_id: str) -> SimAgent:
    for agent in runtime.agents:
        if str(agent.identity.id) == agent_id:
            return agent
    raise ValueError(
        f"seed_holder_agent_id={agent_id!r} not found among runtime agents "
        f"({[str(a.identity.id) for a in runtime.agents]})"
    )


async def _main() -> None:
    report = await run_diffusion_experiment(config=DEFAULT_CONFIG)
    print(report.to_json())


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
