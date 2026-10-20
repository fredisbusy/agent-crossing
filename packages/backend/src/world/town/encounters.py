"""조우 판정: 새로 가까워진 쌍, 대화 가능 조건, 쌍별 쿨다운 (SPEC §14)."""

import datetime

from world.residents import Resident

ENCOUNTER_COOLDOWN = datetime.timedelta(minutes=60)


class EncounterTracker:
    """이미 다룬 가까운 쌍과 쌍별 쿨다운을 기억한다."""

    def __init__(self, cooldown: datetime.timedelta = ENCOUNTER_COOLDOWN) -> None:
        self._cooldown = cooldown
        self._settled: set[tuple[str, str]] = set()
        self._last_asked: dict[tuple[str, str], datetime.datetime] = {}

    def forget_apart(self, near: set[tuple[str, str]]) -> None:
        """멀어진 쌍은 다시 새로 가까워질 수 있게 잊는다."""
        self._settled &= near

    def candidates(self, near: set[tuple[str, str]]) -> list[tuple[str, str]]:
        return sorted(near - self._settled)

    def settle(self, pair: tuple[str, str]) -> None:
        self._settled.add(pair)

    def on_cooldown(self, pair: tuple[str, str], now: datetime.datetime) -> bool:
        last = self._last_asked.get(pair)
        return last is not None and now - last < self._cooldown

    def mark_asked(self, pair: tuple[str, str], now: datetime.datetime) -> None:
        self._last_asked[pair] = now


def can_talk(a: Resident, b: Resident) -> bool:
    """둘 다 대화 중이 아니고, 둘 다 서 있거나 같은 방이어야 한다."""
    if a.body.conversation_id or b.body.conversation_id:
        return False
    same_room = a.body.state.location_path == b.body.state.location_path
    return same_room or (not a.body.is_moving and not b.body.is_moving)
