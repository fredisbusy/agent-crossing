"""마을 루프 테스트용 가짜 공간·가짜 마음. 외부 의존 없음."""

import datetime
import random
from collections import Counter, deque
from collections.abc import Callable, Sequence

from world.contracts import (
    ActionIntent,
    ConversationView,
    EncounterChoice,
    MindContext,
    MindKind,
    Observation,
    ResidentPublicView,
    TilePosition,
    Utterance,
)
from world.residents import Resident, ResidentConfig
from world.town import SimClock, TownSimulation

START = datetime.datetime(2025, 2, 13, 8, 0)
CAFE = "Smallville > Hobbs Cafe > Seating"
SQUARE = "Smallville > Town Square"
GARDEN = "Smallville > Johnson Park > Garden"
ISLAND = "Smallville > Oak Hill College > Library"

Rect = tuple[int, int, int, int]
ROOMS: dict[str, Rect] = {
    CAFE: (0, 0, 4, 4),
    GARDEN: (5, 0, 7, 4),
    SQUARE: (10, 0, 19, 4),
    ISLAND: (18, 8, 19, 9),
}
WALLS = {TilePosition(x=17, y=y) for y in range(7, 10)} | {
    TilePosition(x=x, y=7) for x in range(17, 20)
}


class GridSpace:
    """20x10 격자. 방은 직사각형이고 섬(ISLAND)은 벽으로 막혀 갈 수 없다."""

    def tile_of(self, location_path: str) -> TilePosition | None:
        rect = ROOMS.get(location_path)
        if rect is None:
            return None
        return TilePosition(x=(rect[0] + rect[2]) // 2, y=(rect[1] + rect[3]) // 2)

    def location_at(self, tile: TilePosition) -> str:
        for path, (x0, y0, x1, y1) in ROOMS.items():
            if x0 <= tile.x <= x1 and y0 <= tile.y <= y1:
                return path
        return "Smallville"

    def find_path(
        self, start: TilePosition, goal: TilePosition
    ) -> tuple[TilePosition, ...] | None:
        if goal in WALLS:
            return None
        previous: dict[TilePosition, TilePosition | None] = {start: None}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            if cur == goal:
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = TilePosition(x=cur.x + dx, y=cur.y + dy)
                if not (0 <= nxt.x < 20 and 0 <= nxt.y < 10):
                    continue
                if nxt in WALLS or nxt in previous:
                    continue
                previous[nxt] = cur
                queue.append(nxt)
        if goal not in previous:
            return None
        path: list[TilePosition] = []
        node: TilePosition | None = goal
        while node is not None and node != start:
            path.append(node)
            node = previous[node]
        return tuple(reversed(path))

    def location_paths(self) -> tuple[str, ...]:
        return tuple(ROOMS)


PlanFn = Callable[[MindContext], ActionIntent]


def stay(minutes: int = 30, where: str = CAFE, description: str = "책을 읽는다") -> PlanFn:
    def plan(ctx: MindContext) -> ActionIntent:
        return ActionIntent(
            kind="idle",
            description=description,
            location_path=where,
            until=ctx.now + datetime.timedelta(minutes=minutes),
        )

    return plan


class ScriptedMind:
    """호출을 기록하고 정해진 대로 답하는 가짜 마음."""

    def __init__(
        self,
        kind: MindKind = "schedule",
        *,
        plan: PlanFn | None = None,
        encounter: EncounterChoice = "pass_by",
        replies: Sequence[str | None] = (),
    ) -> None:
        self.kind: MindKind = kind
        self._plan = plan or stay()
        self._encounter = encounter
        self._replies = deque(replies)
        self.next_action_calls = 0
        self.encounter_with: list[str] = []
        self.respond_calls = 0
        self.observed: list[Observation] = []

    async def next_action(self, ctx: MindContext) -> ActionIntent:
        self.next_action_calls += 1
        return self._plan(ctx)

    async def on_encounter(
        self, ctx: MindContext, other: ResidentPublicView
    ) -> EncounterChoice:
        self.encounter_with.append(other.resident_id)
        return self._encounter

    async def respond(
        self, ctx: MindContext, conversation: ConversationView
    ) -> Utterance | None:
        self.respond_calls += 1
        text = self._replies.popleft() if self._replies else None
        if text is None:
            return None
        me = ctx.self_state.resident_id
        return Utterance(
            speaker_id=me,
            listener_ids=tuple(i for i in conversation.participant_ids if i != me),
            text=text,
            spoken_at=ctx.now,
        )

    async def observe(self, observations: tuple[Observation, ...]) -> None:
        self.observed.extend(observations)


class _Factory:
    def __init__(self, minds: dict[str, ScriptedMind]) -> None:
        self._minds = minds

    def build(self, config: ResidentConfig) -> ScriptedMind:
        return self._minds[config.resident_id]


def make_config(resident_id: str, start: str, mind: MindKind = "schedule") -> ResidentConfig:
    return ResidentConfig(
        resident_id=resident_id,
        display_name=resident_id.capitalize(),
        age=30,
        description=[f"{resident_id}는 마을 주민이다."],
        mind=mind,
        agent_priority=1,
        home_location=start,
        start_location=start,
        archetype="student",
    )


def make_sim(
    spec: dict[str, tuple[str, ScriptedMind]],
    *,
    seed: int = 0,
    max_turns: int = 8,
) -> TownSimulation:
    """spec: 주민 id → (시작 위치, 마음)."""
    space = GridSpace()
    minds = {rid: mind for rid, (_, mind) in spec.items()}
    factory = _Factory(minds)
    residents = [
        Resident(make_config(rid, start, mind.kind), space, factory)
        for rid, (start, mind) in spec.items()
    ]
    return TownSimulation(
        space=space,
        residents=residents,
        clock=SimClock(START),
        rng=random.Random(seed),
        max_turns=max_turns,
    )


def calls_total(counter: Counter[MindKind]) -> int:
    return sum(counter.values())
