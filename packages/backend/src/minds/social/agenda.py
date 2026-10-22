"""할 일 목록: 평소 일과(routine) 위에 행사 약속(commitment)을 덮어쓴다 (SPEC §12, §13).

일과는 마음마다 출처가 다르다(규칙 마음은 일정표, LLM 마음은 하루 계획).
약속과 덮어쓰기 규칙, 행동 의도 변환은 두 마음이 이 파일 하나를 함께 쓴다.
"""

import datetime
from dataclasses import dataclass, field
from typing import Literal, Protocol

from world.contracts import ActionIntent, LocationPath, SocialEvent

from .events import place_name

SlotAction = Literal["idle", "use_object", "sleep"]
CommitmentRole = Literal["host", "guest"]

GUEST_LEAD = datetime.timedelta(minutes=30)
"""손님이 행사 시작 전에 미리 이동을 시작하는 시간 (SPEC §13)."""
HOST_LEAD = datetime.timedelta(minutes=60)
"""주최자가 행사 시작 전에 가서 준비하는 시간 (SPEC §13)."""


@dataclass(frozen=True)
class Slot:
    """지금 따라야 할 한 구간."""

    location_path: LocationPath
    description: str
    emoji: str | None
    action: SlotAction
    start: datetime.datetime
    end: datetime.datetime
    is_commitment: bool = False


class Routine(Protocol):
    """평소 일과. 약속이 없을 때 지금 할 일을 알려 준다."""

    def slot_at(self, now: datetime.datetime) -> Slot: ...


@dataclass(frozen=True)
class Commitment:
    """참석하기로 한 행사와 내 역할."""

    event: SocialEvent
    role: CommitmentRole

    @property
    def arrive_at(self) -> datetime.datetime:
        lead = HOST_LEAD if self.role == "host" else GUEST_LEAD
        return self.event.start_time - lead

    def slot_at(self, now: datetime.datetime) -> Slot:
        event = self.event
        if self.role == "host" and now < event.start_time:
            return Slot(
                event.location_path,
                f"{event.name} 준비를 한다",
                "🎀",
                "use_object",
                self.arrive_at,
                event.start_time,
                True,
            )
        return Slot(
            event.location_path,
            f"{event.name}에 참석한다",
            "🎉",
            "idle",
            self.arrive_at if self.role == "guest" else event.start_time,
            event.end_time,
            True,
        )


@dataclass
class Agenda:
    routine: Routine
    commitments: list[Commitment] = field(default_factory=list)

    def commit(self, event: SocialEvent, role: CommitmentRole) -> Commitment:
        """같은 행사(이름·시작 시각)는 한 번만 담는다. 주최자 역할이 손님보다 우선한다."""
        for index, existing in enumerate(self.commitments):
            if _same_event(existing.event, event):
                if role == "host" and existing.role == "guest":
                    self.commitments[index] = Commitment(event, role)
                return self.commitments[index]
        commitment = Commitment(event, role)
        self.commitments.append(commitment)
        self.commitments.sort(key=lambda c: (c.arrive_at, c.event.name))
        return commitment

    def is_committed(self, event: SocialEvent) -> bool:
        return any(_same_event(c.event, event) for c in self.commitments)

    def conflicts(self, event: SocialEvent) -> bool:
        """다른 약속과 시간이 겹치면 True. 같은 행사는 겹침으로 보지 않는다."""
        return any(
            not _same_event(c.event, event)
            and c.event.start_time < event.end_time
            and event.start_time < c.event.end_time
            for c in self.commitments
        )

    def upcoming(self, now: datetime.datetime) -> tuple[Commitment, ...]:
        """아직 끝나지 않은 약속."""
        return tuple(c for c in self.commitments if c.event.end_time > now)

    def slot_at(self, now: datetime.datetime) -> Slot:
        """약속 구간이면 약속, 아니면 다음 약속 전까지로 자른 일과."""
        self.commitments = list(self.upcoming(now))
        for commitment in self.commitments:
            if commitment.arrive_at <= now < commitment.event.end_time:
                return commitment.slot_at(now)
        slot = self.routine.slot_at(now)
        later = [c.arrive_at for c in self.commitments if c.arrive_at > now]
        if later and min(later) < slot.end:
            slot = Slot(
                slot.location_path,
                slot.description,
                slot.emoji,
                slot.action,
                slot.start,
                min(later),
            )
        return slot


def intent_for_slot(slot: Slot, here: LocationPath) -> ActionIntent:
    """구간 장소 밖이면 그쪽으로 이동, 안이면 구간 행동."""
    at_place = here == slot.location_path or here.startswith(slot.location_path + " > ")
    if not at_place:
        return ActionIntent(
            kind="move",
            description=f"{place_name(slot.location_path)} 쪽으로 이동한다",
            location_path=slot.location_path,
            until=slot.end,
            emoji=slot.emoji,
        )
    return ActionIntent(
        kind=slot.action,
        description=slot.description,
        location_path=slot.location_path,
        until=slot.end,
        emoji=slot.emoji,
    )


def _same_event(a: SocialEvent, b: SocialEvent) -> bool:
    return a.name == b.name and a.start_time == b.start_time
