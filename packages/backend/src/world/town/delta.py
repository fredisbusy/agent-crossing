"""연결별 변경분(delta) 계산 (SPEC §9). 순수 함수만 둔다."""

from world.contracts import ResidentSnapshot, WorldDelta, WorldSnapshot


def diff_snapshots(previous: WorldSnapshot, current: WorldSnapshot) -> WorldDelta:
    """`previous`와 달라진 주민(전체 `ResidentSnapshot`)만 담은 delta. 주민 구성은 같다고 본다."""
    before: dict[str, ResidentSnapshot] = {r.resident_id: r for r in previous.residents}
    changed = tuple(r for r in current.residents if before.get(r.resident_id) != r)
    return WorldDelta(tick=current.tick, sim_time=current.sim_time, residents=changed)
