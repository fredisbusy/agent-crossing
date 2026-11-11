"""마을 틱 수준에서 대화 정리(TODO 3-C)가 대화마다 한 번씩만 도는지 확인한다.

LLM 마음을 실제 `TownSimulation`에 올리고, 가짜 클라이언트가 받은 대화 정리 프롬프트를 센다.
"""

import asyncio
import datetime
import json
import random
from collections import deque
from collections.abc import Sequence

from agents.memory.memory_object import MemoryObject
from agents.planning.models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)
from llm.clients.types import LlmGenerateOptions
from town_fakes import CAFE, SQUARE, START, GridSpace, ScriptedMind, make_config, stay
from world.contracts import ActionIntent, Mind, MindContext
from world.residents import Resident, ResidentConfig, llm_persona
from world.town import SimClock, TownSimulation

from minds.llm import LLMMind

NOTES_KEY = '"plan_note"'
"""대화 정리 프롬프트(`town_talk_notes.md`)에만 있는 출력 키."""


class TalkClient:
    """만나면 대화하고, 정해 둔 말을 차례로 한 뒤 작별한다. 대화 정리 프롬프트를 모은다."""

    def __init__(
        self,
        lines: Sequence[str],
        *,
        converse: bool = True,
        farewell: str = "또 봐요!",
    ) -> None:
        self._lines = deque(lines)
        self._converse = converse
        self._farewell = farewell
        self.notes_prompts: list[str] = []

    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
    ) -> str:
        del system, options, format_json
        if NOTES_KEY in prompt:
            self.notes_prompts.append(prompt)
            return json.dumps({"memo": "이야기를 나눴다.", "plan_note": ""})
        if '"converse"' in prompt:
            return json.dumps({"converse": self._converse, "reason": "판정"})
        if '"react"' in prompt:
            return json.dumps({"react": False, "reason": "하던 일을 한다"})
        if '"summary"' in prompt:
            return json.dumps({"summary": "카페 단골이다."})
        if self._lines:
            acts = [{"kind": "smalltalk"}]
            return json.dumps({"utterance": self._lines.popleft(), "acts": acts})
        acts = [{"kind": "farewell"}]
        return json.dumps(
            {"utterance": self._farewell, "acts": acts, "end_conversation": True}
        )


class CafeAllDay:
    """6~22시 카페에 있다. `step_minutes`마다 구간을 나눠 그때마다 마음이 깨어나게 한다.

    대화가 끝난 뒤에도 여러 번 깨어나야 정리가 한 번만 도는지 확인할 수 있다.
    """

    def __init__(self, step_minutes: int = 15) -> None:
        self._step = datetime.timedelta(minutes=step_minutes)

    def generate_hourly_plan(self, **_: object) -> list[HourlyPlanItem]:
        raise ValueError("하루 계획 구간 그대로")

    def generate_minute_plan(self, **_: object) -> list[MinutePlanItem]:
        raise ValueError("하루 계획 구간 그대로")

    def generate_day_plan(
        self, request: DayPlanBroadStrokesRequest
    ) -> list[DayPlanItem]:
        day = request.today_date.replace(hour=0, minute=0, second=0, microsecond=0)
        start, end = day.replace(hour=6), day.replace(hour=22)
        items: list[DayPlanItem] = []
        while start < end:
            items.append(
                DayPlanItem(
                    start_time=start,
                    end_time=min(start + self._step, end),
                    location="Hobbs Cafe Seating",
                    action_content="커피를 마신다",
                )
            )
            start += self._step
        return items


class NoMemory:
    def __init__(self) -> None:
        self.stored: list[str] = []

    def remember(
        self, content: str, now: datetime.datetime, *, kind: str = "observation"
    ) -> int:
        del now, kind
        self.stored.append(content)
        return 1

    def remember_many(self, items: list[tuple[str, datetime.datetime]]) -> list[int]:
        return [self.remember(text, now) for text, now in items]

    def retrieve(
        self, query: str, now: datetime.datetime, top_k: int
    ) -> list[MemoryObject]:
        del query, now, top_k
        return []


class NoReflection:
    def record_observation_importance(self, importance: int) -> None:
        del importance

    def should_reflect(self) -> bool:
        return False

    def reflect(self, *, now: datetime.datetime) -> None:
        del now


class _Factory:
    def __init__(self, minds: dict[str, Mind]) -> None:
        self._minds = minds

    def build(self, config: ResidentConfig) -> Mind:
        return self._minds[config.resident_id]


def llm_mind(
    resident_id: str,
    client: TalkClient,
    memory: NoMemory | None = None,
    planner: CafeAllDay | None = None,
) -> LLMMind:
    config = make_config(resident_id, CAFE, "llm")
    return LLMMind(
        persona=llm_persona(config, GridSpace().location_paths()),
        client=client,
        planner=planner or CafeAllDay(),
        memory=memory or NoMemory(),
        reflection=NoReflection(),
    )


def arrive_at_cafe_after_ten_minutes(ctx: MindContext) -> ActionIntent:
    """처음 10분은 광장에 있다가 카페로 온다."""
    late = ctx.now >= START + datetime.timedelta(minutes=10)
    return stay(30 if late else 1, where=CAFE if late else SQUARE)(ctx)


def town(
    minds: dict[str, Mind],
    *,
    starts: dict[str, str] | None = None,
    start: datetime.datetime = START,
    max_turns: int = 8,
) -> TownSimulation:
    space = GridSpace()
    factory = _Factory(minds)
    residents = [
        Resident(
            make_config(rid, (starts or {}).get(rid, CAFE), mind.kind), space, factory
        )
        for rid, mind in minds.items()
    ]
    return TownSimulation(
        space=space,
        residents=residents,
        clock=SimClock(start),
        rng=random.Random(0),
        max_turns=max_turns,
    )


def transcript(notes_prompt: str) -> list[str]:
    """대화 정리 프롬프트의 대화 기록 줄들."""
    section = notes_prompt.split("나눈 대화", 1)[1].split("## 지시", 1)[0]
    return [line[2:] for line in section.splitlines() if line.startswith("- ")]


def test_two_llm_minds_each_digest_their_conversation_once() -> None:
    ann_client = TalkClient(["안녕, Bob!", "오늘 날씨 좋네."], farewell="잘 가, Bob.")
    bob_client = TalkClient(["안녕, Ann.", "그러게."], farewell="다음에 봐, Ann.")
    sim = town({"ann": llm_mind("ann", ann_client), "bob": llm_mind("bob", bob_client)})
    asyncio.run(sim.run_minutes(90))
    assert all(r.body.conversation_id is None for r in sim.residents)
    assert len(ann_client.notes_prompts) == 1
    assert len(bob_client.notes_prompts) == 1
    # 마지막 작별처럼 내 차례 뒤에 들은 말까지, 두 사람이 같은 대화 기록을 한 줄씩만 담는다.
    ann_lines = transcript(ann_client.notes_prompts[0])
    assert ann_lines == transcript(bob_client.notes_prompts[0])
    assert ann_lines[-2:] == ["Bob: 다음에 봐, Ann.", "Ann: 잘 가, Bob."]
    assert len(ann_lines) == len(set(ann_lines)) == 6


def test_conversation_cut_at_max_turns_keeps_the_line_heard_after_my_last_turn() -> None:
    """마을이 최대 턴에서 대화를 끊으면 마지막 말을 들은 쪽에는 다음 차례가 오지 않는다."""
    ann_client = TalkClient(["하나", "셋", "다섯"])
    bob_client = TalkClient(["둘", "넷", "여섯"])
    sim = town(
        {"ann": llm_mind("ann", ann_client), "bob": llm_mind("bob", bob_client)},
        max_turns=3,
    )
    asyncio.run(sim.run_minutes(90))
    assert len(ann_client.notes_prompts) == 1
    assert len(bob_client.notes_prompts) == 1
    ann_lines = transcript(ann_client.notes_prompts[0])
    assert ann_lines == transcript(bob_client.notes_prompts[0])
    assert len(ann_lines) == len(set(ann_lines)) == 3


def test_partner_ending_first_is_digested_once_with_its_last_line() -> None:
    ann_client = TalkClient(["안녕, Bob!", "요즘 어때?", "그렇구나.", "또 이야기하자."])
    bob = ScriptedMind(encounter="converse", replies=["응, 반가워.", "나는 이만 갈게.", None])
    sim = town({"ann": llm_mind("ann", ann_client), "bob": bob})
    asyncio.run(sim.run_minutes(90))
    assert bob.respond_calls >= 2
    assert len(ann_client.notes_prompts) == 1
    assert "나는 이만 갈게." in ann_client.notes_prompts[0]


def test_back_to_back_conversations_are_digested_once_each() -> None:
    ann_client = TalkClient(["안녕, Bob!", "안녕, Carl!"])
    bob = ScriptedMind(encounter="converse", replies=["반가워.", None])
    carl = ScriptedMind(
        encounter="converse",
        replies=["오랜만이야.", None],
        plan=arrive_at_cafe_after_ten_minutes,
    )
    sim = town(
        {"ann": llm_mind("ann", ann_client), "bob": bob, "carl": carl},
        starts={"carl": SQUARE},
    )
    asyncio.run(sim.run_minutes(90))
    partners = [
        "Bob" if "Bob: 반가워." in p else "Carl" if "Carl: 오랜만이야." in p else "?"
        for p in ann_client.notes_prompts
    ]
    assert partners == ["Bob", "Carl"]


def test_overheard_conversation_is_not_digested_by_the_bystander() -> None:
    ann = ScriptedMind(encounter="converse", replies=["비밀 이야기야.", "정말이야.", None])
    bob = ScriptedMind(encounter="converse", replies=["그래?", "알겠어.", None])
    eve_client = TalkClient([], converse=False)
    eve_memory = NoMemory()
    # 엿들은 발화는 다음에 깨어날 때 전달된다(CafeAllDay가 15분마다 깨운다).
    eve = llm_mind("eve", eve_client, eve_memory)
    sim = town({"ann": ann, "bob": bob, "eve": eve})
    asyncio.run(sim.run_minutes(90))
    assert ann.respond_calls >= 2 and bob.respond_calls >= 2
    assert any("비밀 이야기야." in text for text in eve_memory.stored)
    assert eve_client.notes_prompts == []
