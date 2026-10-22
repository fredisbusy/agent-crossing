"""상대별 우호도(0~100), 마지막 대화 시각, 대화 쿨다운."""

import datetime

from world.contracts import ResidentId

MAX_FRIENDSHIP = 100
CONVERSATION_GAIN = 2
INVITE_ACCEPT_GAIN = 1
GIFT_GAIN = 5
"""선물을 받거나 건넸을 때 오르는 우호도."""
CONVERSATION_COOLDOWN = datetime.timedelta(hours=3)
"""같은 상대와 다시 대화를 시작하기까지의 게임 시간."""
LONG_TIME = datetime.timedelta(days=3)
"""이만큼 못 봤으면 오랜만에 만난 것으로 본다."""


class Friendship:
    def __init__(self) -> None:
        self._scores: dict[ResidentId, int] = {}
        self._last_talk: dict[ResidentId, datetime.datetime] = {}

    def score(self, other: ResidentId) -> int:
        return self._scores.get(other, 0)

    def add(self, other: ResidentId, amount: int) -> int:
        value = max(0, min(MAX_FRIENDSHIP, self.score(other) + amount))
        self._scores[other] = value
        return value

    def record_conversation(self, other: ResidentId, now: datetime.datetime) -> None:
        self.add(other, CONVERSATION_GAIN)
        self._last_talk[other] = now

    def last_talk(self, other: ResidentId) -> datetime.datetime | None:
        return self._last_talk.get(other)

    def in_cooldown(self, other: ResidentId, now: datetime.datetime) -> bool:
        last = self._last_talk.get(other)
        return last is not None and now - last < CONVERSATION_COOLDOWN

    def is_long_time(self, other: ResidentId, now: datetime.datetime) -> bool:
        """전에 이야기한 적이 있고 `LONG_TIME` 넘게 못 봤으면 True."""
        last = self._last_talk.get(other)
        return last is not None and now - last >= LONG_TIME
