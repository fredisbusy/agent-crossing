"""시나리오를 마을 루프로 돌려 지표를 출력한다 (SPEC §16).

기본은 전원 규칙 마음(LLM 호출 0). `--agents`나 `--agent-count`로 LLM 마음을 섞는다.
예: uv run python src/run_town_scenario.py --scenario valentine --agents isabella_rodriguez
"""

import argparse
import asyncio
import json
from collections.abc import Sequence

from world.scenarios import build_town, load_scenario, simulate
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


def _print_hour(sim: TownSimulation) -> None:
    print(sim.text_state())


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse(argv)
    scenario = load_scenario(args.scenario)
    agent_ids = args.agents.split(",") if args.agents else None
    town = build_town(
        scenario,
        agent_ids=agent_ids,
        agent_count=args.agent_count if agent_ids is None else None,
        seed=args.seed,
    )
    report = asyncio.run(simulate(town, on_hour=_print_hour if args.hourly else None))
    summary = report.model_dump(mode="json")
    summary["diffusion_rate"] = round(report.diffusion_rate, 3)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
