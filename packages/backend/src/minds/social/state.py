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
        self._going: set[tuple[str, ResidentId]] = set()
        """(행사 이름, 주민): 나에게 가겠다고 말한 주민."""
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
            elif act.kind == "accept" and act.event:
                self._going.add((act.event, speaker))
                if self._hosts(act.event):
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
                or (event.name, other) in self._going
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
                and (fact.topic, other) not in self._going
            ):
                points.append(self.fact_act(fact, now))
        return tuple(points)

    # --- 같은 말 되풀이 막기 ----------------------------------------------------

    def is_redundant(
        self, act: SpeechAct, other: ResidentId, now: datetime.datetime
    ) -> bool:
        """이미 한 초대·수락·소문·선물을 같은 상대에게 되풀이하는 화행이면 True.

        두 마음 모두 말하기 직전에 이 검사로 걸러 낸다.
        """
        event = self.event_named(act.event) if act.event else None
        name = act.event or ""
        if act.kind == "invite":
            return (
                (name, other) in self._invited
                or (name, other) in self._going
                or (event is not None and other == event.host_id)
            )
        if act.kind == "accept":
            return event is not None and self.agenda.is_committed(event)
        if act.kind == "share_fact":
            topic = act.topic or name
            if event is not None and other == event.host_id:
                return True
            return (
                (topic, other) in self._invited
                or (topic, other) in self._going
                or self.facts.was_told(other, topic)
            )
        if act.kind == "gift":
            return self.gifted(act.item or "", now.date(), other)
        return False

    def partner_notes(
        self, other: ResidentId, now: datetime.datetime
    ) -> tuple[str, ...]:
        """`other`와 행사 사이에 이미 오간 일 (`{partner}` 자리에 상대 이름이 들어간다)."""
        notes: list[str] = []
        for event in self._events_in_mind(now):
            if other == event.host_id:
                notes.append(f"{event.name}은(는) {{partner}}가 여는 행사다.")
            if (event.name, other) in self._going:
                notes.append(f"{{partner}}는 {event.name}에 가겠다고 이미 말했다.")
            elif (event.name, other) in self._invited:
                notes.append(f"{{partner}}를 {event.name}에 이미 초대했다.")
            elif self.facts.was_told(other, event.name):
                notes.append(f"{{partner}}에게 {event.name} 소식을 이미 전했다.")
        return tuple(notes)

    def _events_in_mind(self, now: datetime.datetime) -> tuple[SocialEvent, ...]:
        seen: dict[str, SocialEvent] = {}
        for commitment in self.agenda.upcoming(now):
            seen.setdefault(commitment.event.name, commitment.event)
        for event in self.facts.events(now):
            seen.setdefault(event.name, event)
        return tuple(seen.values())


@runtime_checkable
class HasSocialState(Protocol):
    """사회 상태를 가진 마음. 두 마음 구현이 모두 해당한다."""

    social: SocialState
