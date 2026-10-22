"""시나리오를 마을 루프로 돌려 지표를 출력한다 (SPEC §16).

기본은 전원 규칙 마음(LLM 호출 0). `--agents`나 `--agent-count`로 LLM 마음을 섞는다.
예: uv run python src/run_town_scenario.py --scenario valentine --agents isabella_rodriguez
"""

import argparse
import asyncio
import json
from collections.abc import Sequence

from llm.clients.provider_factory import build_provider_client
from settings import (
    EMBEDDING_MODEL,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)
from world.contracts import Space
from world.residents import (
    LLMMindFactory,
    ResidentConfig,
    ResidentMindFactory,
    apply_mind_selection,
    load_resident_configs,
)
from world.scenarios import apply_scenario, load_scenario, run_scenario
from world.space import load_town_space
from world.town import TownSimulation


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="valentine")
    parser.add_argument(
        "--agents", default=None, help="LLM 마음으로 올릴 주민 id(쉼표 구분)"
    )
    parser.add_argument("--agent-count", type=int, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--hourly", action="store_true", help="매 시간 마을 상태를 출력"
    )
    return parser.parse_args(argv)


def _llm_factory(
    configs: Sequence[ResidentConfig], space: Space
) -> LLMMindFactory | None:
    if all(config.mind != "llm" for config in configs):
        return None
    client = build_provider_client(
        timeout_seconds=LLM_TIMEOUT_SECONDS,
        generation_model=LLM_MODEL,
        embedding_model=EMBEDDING_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY or None,
    )
    return LLMMindFactory(
        client=client,
        embedding_model=EMBEDDING_MODEL,
        known_places=space.location_paths(),
    )


def _print_hour(sim: TownSimulation) -> None:
    print(sim.text_state())


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse(argv)
    scenario = load_scenario(args.scenario)
    agent_ids = args.agents.split(",") if args.agents else None
    agent_count = (
        args.agent_count if agent_ids is None and args.agent_count is not None else None
    )
    if agent_ids is None and agent_count is None:
        agent_count = 0
    configs = apply_mind_selection(
        load_resident_configs(), agent_ids=agent_ids, agent_count=agent_count
    )
    configs = apply_scenario(configs, scenario)
    space = load_town_space()
    factory = ResidentMindFactory(
        start_time=scenario.start_time,
        seed=args.seed,
        llm_factory=_llm_factory(configs, space),
    )
    report = asyncio.run(
        run_scenario(
            scenario,
            configs=configs,
            space=space,
            mind_factory=factory,
            seed=args.seed,
            on_hour=_print_hour if args.hourly else None,
        )
    )
    summary = report.model_dump(mode="json")
    summary["diffusion_rate"] = round(report.diffusion_rate, 3)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
