"""사회 상태: 할 일·우호도·사실을 묶고 화행의 효과를 한곳에서 반영한다 (SPEC §13).

두 마음은 "무엇을 말할지"만 따로 정하고, 말한 것·들은 것의 효과(약속, 소문, 우호도)는
이 클래스가 같은 규칙으로 처리한다. 같은 발화를 여러 번 받아도 한 번만 반영한다.
"""

import datetime
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from world.contracts import (
    Holiday,
    ResidentId,
    SocialEvent,
    SpeechAct,
    Utterance,
)

from .agenda import Agenda, Routine
from .events import describe_event, event_act, event_from_act
from .facts import Fact, FactStore
from .friendship import GIFT_GAIN, INVITE_ACCEPT_GAIN, Friendship

INVITE_COMPANION_MIN = 20
"""손님으로 가는 행사에 다른 주민을 같이 가자고 부를 최소 우호도."""
GIFT_MIN_FRIENDSHIP = 10
"""기념일 선물을 건넬 최소 우호도."""


@dataclass(frozen=True)
class SocialSeed:
    """시작할 때 아는 것: 여는 행사, 아는 사실, 이미 친한 정도."""

    hosting: tuple[SocialEvent, ...] = ()
    facts: tuple[tuple[str, str], ...] = ()
    """(주제, 내용)."""
    friendships: Mapping[ResidentId, int] = field(default_factory=dict[ResidentId, int])


class SocialState:
    def __init__(self, resident_id: ResidentId, routine: Routine) -> None:
        self.resident_id = resident_id
        self.agenda = Agenda(routine)
        self.friendship = Friendship()
        self.facts = FactStore()
        self._heard: set[tuple[ResidentId, datetime.datetime, str]] = set()
        self._conversations: set[str] = set()
        self._invited: set[tuple[str, ResidentId]] = set()
        self._gifted: set[tuple[str, datetime.date, ResidentId]] = set()

    # --- 시작 상태 -----------------------------------------------------------

    def apply_seed(self, seed: SocialSeed, now: datetime.datetime) -> None:
        for event in seed.hosting:
            self.host(event, now)
        for topic, fact in seed.facts:
            self.facts.learn(topic, fact, self.resident_id, now)
        for other, score in sorted(seed.friendships.items()):
            self.friendship.add(other, score)

    def host(self, event: SocialEvent, now: datetime.datetime) -> None:
        """행사를 연다: 주최 약속을 잡고 소문낼 사실로 담는다."""
        hosted = event.model_copy(update={"host_id": self.resident_id})
        self.agenda.commit(hosted, "host")
        self.facts.learn(
            hosted.name, describe_event(hosted, now), self.resident_id, now, hosted
        )

    # --- 대화 효과 -----------------------------------------------------------

    def join_conversation(
        self, conversation_id: str, other: ResidentId, now: datetime.datetime
    ) -> None:
        """대화 하나당 한 번 우호도와 마지막 대화 시각을 갱신한다."""
        if conversation_id in self._conversations:
            return
        self._conversations.add(conversation_id)
        self.friendship.record_conversation(other, now)

    def hear(self, utterance: Utterance, now: datetime.datetime) -> None:
        """남의 발화를 반영한다. 엿들은 말은 소문만 배우고 초대·선물은 받지 않는다."""
        key = (utterance.speaker_id, utterance.spoken_at, utterance.text)
        if utterance.speaker_id == self.resident_id or key in self._heard:
            return
        self._heard.add(key)
        speaker = utterance.speaker_id
        addressed = self.resident_id in utterance.listener_ids
        for act in utterance.acts:
            if act.kind == "share_fact":
                self._learn_from(act, speaker, now)
            elif not addressed:
                continue
            elif act.kind == "invite":
                self._learn_from(act, speaker, now)
            elif act.kind == "accept" and self._hosts(act.event):
                self.friendship.add(speaker, INVITE_ACCEPT_GAIN)
            elif act.kind == "gift":
                self.friendship.add(speaker, GIFT_GAIN)

    def said(self, utterance: Utterance, now: datetime.datetime) -> None:
        """내 발화의 효과: 수락이면 약속, 초대·소문이면 전달 기록, 선물이면 우호도."""
        key = (utterance.speaker_id, utterance.spoken_at, utterance.text)
        if key in self._heard:
            return
        self._heard.add(key)
        for act in utterance.acts:
            for other in utterance.listener_ids:
                self._apply_own(act, other, now)

    def _apply_own(
        self, act: SpeechAct, other: ResidentId, now: datetime.datetime
    ) -> None:
        if act.kind == "accept":
            event = self.known_event(act)
            if event is not None and (
                self.agenda.is_committed(event) or self.can_attend(event, now)
            ):
                self.agenda.commit(event, "guest")
                if event.host_id == other:
                    self.friendship.add(other, INVITE_ACCEPT_GAIN)
        elif act.kind == "invite" and act.event:
            if self.event_named(act.event) is None:
                event = event_from_act(act, self.resident_id)
                if event is not None:
                    self.host(event, now)
            self._invited.add((act.event, other))
            self.facts.mark_topic_told(other, act.event)
        elif act.kind == "share_fact" and (act.topic or act.event):
            self.facts.mark_topic_told(other, act.topic or act.event or "")
        elif act.kind == "gift":
            self._gifted.add((act.item or "", now.date(), other))
            self.friendship.add(other, GIFT_GAIN)

    def _learn_from(
        self, act: SpeechAct, speaker: ResidentId, now: datetime.datetime
    ) -> None:
        event = event_from_act(act, speaker)
        if event is not None:
            known = self.event_named(event.name)
            if known is not None and known.host_id is not None:
                event = event.model_copy(update={"host_id": known.host_id})
            self.facts.learn(
                act.topic or event.name, describe_event(event, now), speaker, now, event
            )
        elif act.topic and act.fact:
            self.facts.learn(act.topic, act.fact, speaker, now)

    def _hosts(self, event_name: str | None) -> bool:
        return any(
            c.role == "host" and c.event.name == event_name
            for c in self.agenda.commitments
        )

    # --- 질의 ----------------------------------------------------------------

    def event_named(self, name: str) -> SocialEvent | None:
        """이름으로 아는 행사: 약속 → 사실 저장소 순."""
        for commitment in self.agenda.commitments:
            if commitment.event.name == name:
                return commitment.event
        known = self.facts.get(name)
        return known.event if known is not None else None

    def known_event(self, act: SpeechAct) -> SocialEvent | None:
        """화행이 가리키는 행사. 아는 행사면 그 정보(주최자 포함)를 쓴다."""
        if act.event:
            known = self.event_named(act.event)
            if known is not None:
                return known
        return event_from_act(act, None)

    def fact_act(self, fact: Fact, now: datetime.datetime) -> SpeechAct:
        """사실을 전하는 화행. 행사 문장은 말하는 시점 기준으로 다시 쓴다."""
        if fact.event is None:
            return SpeechAct(kind="share_fact", topic=fact.topic, fact=fact.fact)
        text = describe_event(fact.event, now)
        return event_act("share_fact", fact.event, topic=fact.topic, fact=text)

    def can_attend(self, event: SocialEvent, now: datetime.datetime) -> bool:
        return event.end_time > now and not self.agenda.conflicts(event)

    def gifted(self, item: str, day: datetime.date, other: ResidentId) -> bool:
        return (item, day, other) in self._gifted

    def talking_points(
        self,
        other: ResidentId,
        now: datetime.datetime,
        holidays: Sequence[Holiday] = (),
    ) -> tuple[SpeechAct, ...]:
        """`other`에게 꺼낼 만한 화행 후보. 초대 → 선물 → 소문 순."""
        points: list[SpeechAct] = []
        for commitment in self.agenda.upcoming(now):
            event = commitment.event
            if (
                event.start_time <= now
                or other == event.host_id
                or (event.name, other) in self._invited
            ):
                continue
            if commitment.role == "host" or (
                event.is_open and self.friendship.score(other) >= INVITE_COMPANION_MIN
            ):
                points.append(event_act("invite", event))
        for holiday in holidays:
            item = holiday.gift_item
            if (
                item
                and not self.gifted(item, now.date(), other)
                and self.friendship.score(other) >= GIFT_MIN_FRIENDSHIP
            ):
                points.append(SpeechAct(kind="gift", item=item))
        inviting = {p.event for p in points if p.kind == "invite"}
        for fact in self.facts.unshared_for(other):
            if fact.event is None:
                points.append(self.fact_act(fact, now))
            elif (
                fact.event.end_time > now
                and other != fact.event.host_id
                and fact.topic not in inviting
                and (fact.topic, other) not in self._invited
            ):
                points.append(self.fact_act(fact, now))
        return tuple(points)


@runtime_checkable
class HasSocialState(Protocol):
    """사회 상태를 가진 마음. 두 마음 구현이 모두 해당한다."""

    social: SocialState
