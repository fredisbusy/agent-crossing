"""실제 LLM으로 마을을 돌리며 호출 수·지연·형식 실패를 잰다 (TODO 실측 항목).

기본은 LLM 주민 2명·게임 24시간. 결과는 `--out` 폴더에 남긴다:
`calls.jsonl`(호출별 프롬프트·응답), `hourly.txt`(매시간 마을 상태), `summary.json`.
예: EMBEDDING_MODEL=local/BAAI/bge-m3 uv run python src/run_live_day.py --out /tmp/live-day
"""

import argparse
import asyncio
import json
import statistics
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import IO

from llm.clients import CallRecord, RecordingProviderClient
from world.scenarios import build_llm_client, build_town, load_scenario

MINUTES_PER_HOUR = 60
DEFAULT_MINUTES = 24 * MINUTES_PER_HOUR
DEFAULT_AGENTS = "isabella_rodriguez,klaus_mueller"

_PROMPT_KINDS: tuple[tuple[str, str], ...] = (
    ("Score the importance of each numbered memory", "importance:batch"),
    ("Score memory importance", "importance"),
    ("Active Hourly Plan", "plan:minute"),
    ("Active Day Plan", "plan:hour"),
    ("## Persona Context", "plan:day"),
    ("상위 수준 통찰", "reflect:insight"),
    ("가장 중요한", "reflect:question"),
)
"""프롬프트에 이 문구가 있으면 그 종류다(`llm/templates/`의 머리말). `plan:day`는 재계획 포함."""

_RESPONSE_KINDS: tuple[tuple[str, str], ...] = (
    ('"react"', "react"),
    ('"converse"', "encounter"),
    ('"utterance"', "speech"),
    ('"summary"', "summary"),
)
"""`## 인물`로 시작하는 마을 프롬프트는 응답의 키로 나눈다."""


def call_kind(record: CallRecord) -> str:
    if record.op == "embed":
        return "embed"
    for marker, kind in _PROMPT_KINDS:
        if marker in record.prompt:
            return kind
    for marker, kind in _RESPONSE_KINDS:
        if marker in record.response:
            return kind
    return "other"


def _is_bad(record: CallRecord) -> bool:
    if record.error is not None:
        return True
    if not record.format_json:
        return False
    try:
        json.loads(record.response)
    except ValueError:
        return True
    return False


def summarize(records: Sequence[CallRecord]) -> dict[str, dict[str, float | int]]:
    """종류별 호출 수, 지연 중앙값·최댓값(초), 오류·JSON 형식 실패 수."""
    grouped: dict[str, list[CallRecord]] = defaultdict(list)
    for record in records:
        grouped[call_kind(record)].append(record)
    return {
        kind: {
            "count": len(items),
            "median_seconds": round(statistics.median(r.seconds for r in items), 2),
            "max_seconds": round(max(r.seconds for r in items), 2),
            "total_seconds": round(sum(r.seconds for r in items), 1),
            "bad": sum(_is_bad(r) for r in items),
        }
        for kind, items in sorted(grouped.items(), key=lambda kv: -len(kv[1]))
    }


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="valentine")
    parser.add_argument("--agents", default=DEFAULT_AGENTS, help="LLM 주민 id(쉼표 구분)")
    parser.add_argument("--minutes", type=int, default=DEFAULT_MINUTES)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace, calls: IO[str], hourly: IO[str]) -> dict[str, object]:
    records: list[CallRecord] = []

    def sink(record: CallRecord) -> None:
        records.append(record)
        calls.write(record.model_dump_json() + "\n")
        calls.flush()

    client = RecordingProviderClient(build_llm_client(), sink)
    scenario = load_scenario(args.scenario).model_copy(update={"minutes": args.minutes})
    town = build_town(
        scenario, agent_ids=args.agents.split(","), seed=args.seed, llm_client=client
    )
    sim = town.simulation
    tracker = town.new_tracker()
    started = time.perf_counter()
    for minute in range(scenario.minutes):
        client.label = sim.clock.now.isoformat()
        await sim.tick()
        tracker.sample(town.residents, sim.clock.now)
        if (minute + 1) % MINUTES_PER_HOUR == 0:
            elapsed = time.perf_counter() - started
            hourly.write(f"=== {sim.clock.now.isoformat()} (실제 {elapsed:.0f}초)\n")
            hourly.write(sim.text_state() + "\n\n")
            hourly.flush()
            print(f"{sim.clock.now.isoformat()} 실제 {elapsed:.0f}초", flush=True)
    report = tracker.report(
        scenario=scenario.name, residents=town.residents, mind_calls=sim.mind_calls
    )
    return {
        "report": report.model_dump(mode="json"),
        "diffusion_rate": round(report.diffusion_rate, 3),
        "wall_seconds": round(time.perf_counter() - started, 1),
        "max_concurrent": max((r.concurrent for r in records), default=0),
        "calls": summarize(records),
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    with (
        open(args.out / "calls.jsonl", "w", encoding="utf-8") as calls,
        open(args.out / "hourly.txt", "w", encoding="utf-8") as hourly,
    ):
        summary = asyncio.run(_run(args, calls, hourly))
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    (args.out / "summary.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
