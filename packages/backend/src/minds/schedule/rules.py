"""화행 규칙: 상대 마지막 발화의 화행을 읽어 응답 화행을 정한다 (SPEC §13)."""

import datetime
import random

from world.contracts import (
    ConversationView,
    ResidentId,
    SpeechAct,
    Utterance,
)

from .config import ScheduleConfig
from .facts import Fact, FactStore
from .friendship import INVITE_ACCEPT_GAIN, Friendship
from .lines import render
from .timetable import Timetable


class ReplyRules:
    """대화 한 차례의 응답을 만든다. 우호도·일정표·사실 저장소를 갱신하는 부작용이 있다."""

    def __init__(
        self,
        *,
        resident_id: ResidentId,
        config: ScheduleConfig,
        timetable: Timetable,
        friendship: Friendship,
        facts: FactStore,
        rng: random.Random,
    ) -> None:
        self._me = resident_id
        self._config = config
        self._timetable = timetable
        self._friendship = friendship
        self._facts = facts
        self._rng = rng
        self._counted: set[str] = set()

    def reply(
        self, now: datetime.datetime, conversation: ConversationView
    ) -> Utterance | None:
        others = tuple(p for p in conversation.participant_ids if p != self._me)
        if not others:
            return None
        other = others[0]
        history = conversation.history
        mine = [u for u in history if u.speaker_id == self._me]
        if mine and _has_kind(mine[-1], "farewell"):
            return None
        if history and history[-1].speaker_id == self._me:
            return None
        if conversation.conversation_id not in self._counted:
            self._counted.add(conversation.conversation_id)
            self._friendship.record_conversation(other, now)
        last = history[-1] if history else None
        act = self._choose(
            now,
            other,
            last,
            greeted=any(_has_kind(u, "greet") for u in mine),
            turns=len(mine),
        )
        text = self._text(act)
        return Utterance(
            speaker_id=self._me,
            listener_ids=others,
            text=text,
            acts=(act,),
            spoken_at=now,
        )

    def _choose(
        self,
        now: datetime.datetime,
        other: ResidentId,
        last: Utterance | None,
        *,
        greeted: bool,
        turns: int,
    ) -> SpeechAct:
        if last is None:
            return SpeechAct(kind="greet")
        for act in last.acts:
            if act.kind == "share_fact" and act.topic and act.fact:
                self._facts.learn(act.topic, act.fact, other, now)
        kinds = {a.kind: a for a in last.acts}
        if "farewell" in kinds:
            return SpeechAct(kind="farewell")
        if "invite" in kinds:
            return self._answer_invite(other, kinds["invite"])
        if turns + 1 >= self._config.max_turns:
            return SpeechAct(kind="farewell")
        if "ask" in kinds:
            return self._answer_ask(other, kinds["ask"])
        if "share_fact" in kinds:
            return SpeechAct(kind="smalltalk")
        if "greet" in kinds and not greeted:
            return SpeechAct(kind="greet")
        return self._maybe_share(other) or SpeechAct(kind="smalltalk")

    def _answer_invite(self, other: ResidentId, invite: SpeechAct) -> SpeechAct:
        start, place = invite.start_time, invite.location_path
        event = invite.event or ""
        accepted = (
            start is not None
            and place is not None
            and not self._timetable.conflicts(start)
            and self._friendship.score(other)
            >= self._config.min_friendship_to_accept_invite
        )
        if not accepted or start is None or place is None:
            return SpeechAct(kind="decline", event=event)
        self._timetable.add_override(event, start, place)
        self._friendship.add(other, INVITE_ACCEPT_GAIN)
        return SpeechAct(
            kind="accept", event=event, start_time=start, location_path=place
        )

    def _answer_ask(self, other: ResidentId, ask: SpeechAct) -> SpeechAct:
        known = self._facts.get(ask.topic) if ask.topic else None
        if known is None:
            return SpeechAct(kind="smalltalk", topic=ask.topic)
        self._facts.mark_told(other, known)
        return SpeechAct(kind="share_fact", topic=known.topic, fact=known.fact)

    def _maybe_share(self, other: ResidentId) -> SpeechAct | None:
        pending: tuple[Fact, ...] = self._facts.unshared_for(other)
        if not pending or self._rng.random() >= self._config.share_probability:
            return None
        fact = pending[0]
        self._facts.mark_told(other, fact)
        return SpeechAct(kind="share_fact", topic=fact.topic, fact=fact.fact)

    def _text(self, act: SpeechAct) -> str:
        key: str = act.kind
        if act.kind == "smalltalk" and act.topic:
            key = "unknown"
        return render(
            key,
            self._config.tone,
            self._rng,
            topic=act.topic or "",
            fact=act.fact or "",
            event=act.event or "",
            when=act.start_time,
            location_path=act.location_path,
        )


def _has_kind(utterance: Utterance, kind: str) -> bool:
    return any(a.kind == kind for a in utterance.acts)
