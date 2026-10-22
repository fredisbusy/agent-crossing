"""화행 규칙: 상대 마지막 발화의 화행을 읽어 응답 화행을 정한다 (SPEC §13).

화행의 효과(약속·소문·우호도)는 `minds.social.SocialState`가 반영한다.
여기서는 무엇을 말할지만 고른다.
"""

import datetime
import random
from collections import deque

from minds.social import (
    SocialState,
    event_act,
    must_end,
    my_turns,
    partner_of,
    should_stop,
)
from world.contracts import (
    ConversationView,
    MindContext,
    ResidentId,
    SocialEvent,
    SpeechAct,
    Utterance,
)

from .config import ScheduleConfig
from .lines import render

HOST_FRIEND_BONUS = 0.3
"""주최자와 친하면(우호도 `HOST_FRIEND_MIN` 이상) 소문 행사에 갈 확률에 더한다."""
HOST_FRIEND_MIN = 10
RECENT_LINES = 8
"""되풀이를 피할 최근 대사 수."""


class ReplyRules:
    """대화 한 차례의 응답을 만든다."""

    def __init__(
        self,
        *,
        social: SocialState,
        config: ScheduleConfig,
        rng: random.Random,
    ) -> None:
        self._social = social
        self._me = social.resident_id
        self._config = config
        self._rng = rng
        self._considered: set[tuple[str, datetime.datetime]] = set()
        self._long_time: dict[str, bool] = {}
        self._recent: deque[str] = deque(maxlen=RECENT_LINES)
        """최근에 한 말. 같은 문장을 되풀이하지 않게 피한다."""

    def reply(
        self, ctx: MindContext, conversation: ConversationView
    ) -> Utterance | None:
        other = partner_of(self._me, conversation)
        if other is None or should_stop(self._me, conversation):
            return None
        now = ctx.now
        cid = conversation.conversation_id
        if cid not in self._long_time:
            self._long_time[cid] = self._social.friendship.is_long_time(other, now)
        self._social.join_conversation(cid, other, now)
        history = conversation.history
        last = history[-1] if history else None
        if last is not None:
            self._social.hear(last, now)
        mine = my_turns(self._me, conversation)
        act = self._choose(ctx, conversation, other, last)
        if self._social.is_redundant(act, other, now):
            act = SpeechAct(kind="smalltalk")
        avoid = {*self._recent, *(u.text for u in mine)}
        text = self._text(act, ctx, last, first=not mine, cid=cid, avoid=avoid)
        self._recent.append(text)
        utterance = Utterance(
            speaker_id=self._me,
            listener_ids=(other,),
            text=text,
            acts=(act,),
            spoken_at=now,
        )
        self._social.said(utterance, now)
        return utterance

    def _choose(
        self,
        ctx: MindContext,
        conversation: ConversationView,
        other: ResidentId,
        last: Utterance | None,
    ) -> SpeechAct:
        if last is None:
            return SpeechAct(kind="greet")
        kinds = {a.kind: a for a in last.acts}
        if "invite" in kinds:
            return self._answer_invite(ctx.now, other, kinds["invite"])
        if must_end(self._me, conversation, self._config.max_turns):
            return SpeechAct(kind="farewell")
        if "gift" in kinds:
            return SpeechAct(kind="smalltalk")
        if "ask" in kinds:
            return self._answer_ask(ctx.now, kinds["ask"])
        if "share_fact" in kinds:
            return self._answer_rumor(ctx.now, kinds["share_fact"])
        greeted = any(_has_kind(u, "greet") for u in my_turns(self._me, conversation))
        if "greet" in kinds and not greeted:
            return SpeechAct(kind="greet")
        return self._initiative(ctx, other)

    def _answer_invite(
        self, now: datetime.datetime, other: ResidentId, invite: SpeechAct
    ) -> SpeechAct:
        event = self._social.known_event(invite)
        accepted = (
            event is not None
            and self._social.can_attend(event, now)
            and self._social.friendship.score(other)
            >= self._config.min_friendship_to_accept_invite
        )
        if not accepted or event is None:
            return SpeechAct(kind="decline", event=invite.event or "")
        return event_act("accept", event)

    def _answer_ask(self, now: datetime.datetime, ask: SpeechAct) -> SpeechAct:
        known = self._social.facts.get(ask.topic) if ask.topic else None
        if known is None:
            return SpeechAct(kind="smalltalk", topic=ask.topic)
        return self._social.fact_act(known, now)

    def _answer_rumor(self, now: datetime.datetime, rumor: SpeechAct) -> SpeechAct:
        event = self._social.known_event(rumor) if rumor.event else None
        if event is not None and self._wants_to_join(event, now):
            return event_act("accept", event)
        return SpeechAct(kind="smalltalk")

    def _wants_to_join(self, event: SocialEvent, now: datetime.datetime) -> bool:
        """소문으로 들은 공개 행사에 갈지 한 번만 정한다."""
        key = (event.name, event.start_time)
        if (
            key in self._considered
            or not event.is_open
            or self._social.agenda.is_committed(event)
            or not self._social.can_attend(event, now)
        ):
            return False
        self._considered.add(key)
        chance = self._config.event_interest
        host = event.host_id
        if host and self._social.friendship.score(host) >= HOST_FRIEND_MIN:
            chance += HOST_FRIEND_BONUS
        return self._rng.random() < chance

    def _initiative(self, ctx: MindContext, other: ResidentId) -> SpeechAct:
        """먼저 꺼낼 화행: 초대 → 선물 → (확률로) 소문 → 잡담."""
        points = self._social.talking_points(other, ctx.now, ctx.holidays)
        for kind in ("invite", "gift"):
            for point in points:
                if point.kind == kind:
                    return point
        shares = [p for p in points if p.kind == "share_fact"]
        if shares and self._rng.random() < self._config.share_probability:
            return shares[0]
        return SpeechAct(kind="smalltalk")

    def _text(
        self,
        act: SpeechAct,
        ctx: MindContext,
        last: Utterance | None,
        *,
        first: bool,
        cid: str,
        avoid: set[str],
    ) -> str:
        key: str = act.kind
        if act.kind == "greet" and first:
            if self._long_time.get(cid):
                key = "greet_again"
            else:
                greetings = [g for h in ctx.holidays for g in h.greetings]
                if greetings:
                    return greetings[self._rng.randrange(len(greetings))]
        if act.kind == "smalltalk" and act.topic:
            key = "unknown"
        if act.kind == "smalltalk" and last is not None and _has_kind(last, "gift"):
            key = "thanks"
        return render(
            key,
            self._config.tone,
            self._rng,
            now=ctx.now,
            topic=act.topic or "",
            fact=act.fact or "",
            event=act.event or "",
            when=act.start_time,
            location_path=act.location_path,
            item=act.item or "",
            avoid=avoid,
        )


def _has_kind(utterance: Utterance, kind: str) -> bool:
    return any(a.kind == kind for a in utterance.acts)
