"""하이브리드 마을의 공유 계약 (SPEC §12~§15).

몸·마음·공간·마을 루프가 서로 만나는 경계 타입만 둔다. 구현은 각 기능 폴더에 있고,
이 파일의 이름은 `packages/shared/src/world.ts`의 TS 타입 이름과 같게 유지한다.
"""

import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

ResidentId = str
"""주민 식별자. 주민 설정 파일의 `resident_id`."""

LocationPath = str
"""`Town > Building > Room > Object` 형식의 위치 경로 (SPEC §8, §15)."""

LOCATION_SEPARATOR = " > "

MindKind = Literal["llm", "schedule"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class TilePosition(_Frozen):
    x: int
    y: int


# --- 화행 (SPEC §13) -------------------------------------------------------

SpeechActKind = Literal[
    "greet",
    "smalltalk",
    "share_fact",
    "ask",
    "invite",
    "accept",
    "decline",
    "farewell",
    "gift",
]


def _naive(value: datetime.datetime | None) -> datetime.datetime | None:
    """시뮬레이션 시계는 시간대 없는(naive) 시각이다. 시간대가 붙어 오면 떼어 맞춘다."""
    if value is None or value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


class SocialEvent(_Frozen):
    """주민이 열거나 초대받는 행사. 두 마음이 같은 형식으로 약속·사실에 담는다 (SPEC §13)."""

    name: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    location_path: LocationPath
    host_id: ResidentId | None = None
    is_open: bool = True
    """소문으로 들은 주민도 와도 되는 행사인지."""

    @field_validator("start_time", "end_time")
    @classmethod
    def _naive_sim_time(cls, value: datetime.datetime) -> datetime.datetime:
        return value.replace(tzinfo=None)


class Holiday(_Frozen):
    """마을 달력의 기념일. 모든 마음에 같은 형식으로 전달된다 (SPEC §14)."""

    name: str
    customs: tuple[str, ...] = ()
    """이날의 풍습 문장. 관찰 문장과 대화 맥락에 쓴다."""
    greetings: tuple[str, ...] = ()
    """이날 인사말."""
    gift_item: str | None = None
    """이날 주고받는 선물. 없으면 선물 풍습이 없다."""


class SpeechAct(_Frozen):
    kind: SpeechActKind
    topic: str | None = None
    """`share_fact`·`ask`의 주제."""
    fact: str | None = None
    """`share_fact`의 내용."""
    event: str | None = None
    """`invite`·`accept`·`decline`이 가리키는 행사 이름. `share_fact`에 붙으면 행사 소문이다."""
    start_time: datetime.datetime | None = None
    """행사 시작 시각."""
    end_time: datetime.datetime | None = None
    """행사 종료 시각. 없으면 기본 길이(SPEC §13)를 쓴다."""
    location_path: LocationPath | None = None
    """`invite`의 장소."""
    item: str | None = None
    """`gift`로 건네는 물건."""
    host_id: ResidentId | None = None
    """행사 주최자. 전해 듣는 동안 주최자 정보가 사라지지 않게 싣는다."""

    @field_validator("start_time", "end_time")
    @classmethod
    def _naive_sim_time(cls, value: datetime.datetime | None) -> datetime.datetime | None:
        return _naive(value)


class Utterance(_Frozen):
    speaker_id: ResidentId
    listener_ids: tuple[ResidentId, ...]
    text: str
    acts: tuple[SpeechAct, ...] = ()
    spoken_at: datetime.datetime


# --- 관찰과 행동 -------------------------------------------------------------

ObservationKind = Literal["sight", "object_state", "utterance", "event"]


class Observation(_Frozen):
    """마음에 전달되는 관찰. 문장 형식은 상대 마음 종류와 무관하다(불가지 원칙)."""

    kind: ObservationKind
    text: str
    observed_at: datetime.datetime
    location_path: LocationPath
    subject_id: ResidentId | None = None
    utterance: Utterance | None = None


ActionKind = Literal["move", "use_object", "idle", "sleep", "converse"]


class ActionIntent(_Frozen):
    """마음이 몸에 내리는 다음 행동. 몸은 도착·지속을 스스로 처리한다."""

    kind: ActionKind
    description: str
    """사람이 읽는 행동 서술. 예: "카페에서 커피를 내린다"."""
    location_path: LocationPath
    """행동 장소. `move`면 목적지."""
    until: datetime.datetime
    """이 행동을 이어 갈 시각. 그 전에는 새 관찰·조우가 없으면 마음을 깨우지 않는다."""
    emoji: str | None = None


class BodyState(_Frozen):
    resident_id: ResidentId
    display_name: str
    tile: TilePosition
    location_path: LocationPath
    action: ActionIntent | None = None
    path: tuple[TilePosition, ...] = ()
    """남은 이동 경로(현재 타일 제외)."""
    conversation_id: str | None = None


# --- 마음 프로토콜 (SPEC §12) ------------------------------------------------


class ResidentPublicView(_Frozen):
    """다른 주민이 볼 수 있는 정보. 마음 종류는 포함하지 않는다."""

    resident_id: ResidentId
    display_name: str
    location_path: LocationPath
    action_description: str | None = None


class MindContext(_Frozen):
    now: datetime.datetime
    self_state: BodyState
    nearby: tuple[ResidentPublicView, ...] = ()
    observations: tuple[Observation, ...] = ()
    """마지막으로 마음을 깨운 뒤 쌓인 새 관찰."""
    holidays: tuple[Holiday, ...] = ()
    """오늘의 기념일."""


EncounterChoice = Literal["pass_by", "converse"]


class ConversationView(_Frozen):
    conversation_id: str
    participant_ids: tuple[ResidentId, ...]
    history: tuple[Utterance, ...] = ()


class Mind(Protocol):
    """주민의 마음. LLMMind와 ScheduleMind가 같은 계약을 따른다."""

    @property
    def kind(self) -> MindKind:
        """디버그 인스펙터 전용 마음 종류. 다른 마음에는 전달하지 않는다."""
        ...

    async def next_action(self, ctx: MindContext) -> ActionIntent:
        """현재 행동이 끝났거나 새 관찰이 생겼을 때 다음 행동을 정한다."""
        ...

    async def on_encounter(
        self, ctx: MindContext, other: ResidentPublicView
    ) -> EncounterChoice:
        """가까이 온 주민과 대화할지 정한다."""
        ...

    async def respond(
        self, ctx: MindContext, conversation: ConversationView
    ) -> Utterance | None:
        """대화 차례에 말한다. None이면 대화를 끝낸다."""
        ...

    async def observe(self, observations: tuple[Observation, ...]) -> None:
        """관찰을 기억·사실 저장소에 반영한다."""
        ...


# --- 공간 (SPEC §15) --------------------------------------------------------


class Space(Protocol):
    """마을 루프가 쓰는 공간 질의. 구현은 `world.space`."""

    def tile_of(self, location_path: LocationPath) -> TilePosition | None:
        """위치 경로가 가리키는 대표 타일(서는 자리). 모르는 경로면 None."""
        ...

    def location_at(self, tile: TilePosition) -> LocationPath:
        """타일이 속한 가장 구체적인 위치 경로. 장소 밖이면 마을 이름."""
        ...

    def find_path(
        self, start: TilePosition, goal: TilePosition
    ) -> tuple[TilePosition, ...] | None:
        """4방향 A* 경로(start 제외, goal 포함). 갈 수 없으면 None."""
        ...

    def location_paths(self) -> tuple[LocationPath, ...]:
        """맵에 정의된 모든 위치 경로."""
        ...


# --- 월드 스냅샷 (WebSocket, SPEC §9) ----------------------------------------


class ResidentSnapshot(_Frozen):
    resident_id: ResidentId
    display_name: str
    tile: TilePosition
    location_path: LocationPath
    action_description: str | None = None
    emoji: str | None = None
    utterance_text: str | None = None
    mind_kind: MindKind | None = None
    """디버그 인스펙터 전용. 마음에는 절대 전달하지 않는다."""


class WorldSnapshot(_Frozen):
    tick: int
    sim_time: datetime.datetime
    residents: tuple[ResidentSnapshot, ...] = Field(default_factory=tuple)
