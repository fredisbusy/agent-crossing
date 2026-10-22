import datetime

from minds.social import Agenda, Slot
from world.contracts import SocialEvent

MONDAY = datetime.datetime(2026, 10, 19)
CAFE = "Smallville > Hobbs Cafe > Counter"
SQUARE = "Smallville > Town Square"


class FixedRoutine:
    """하루 종일 카페에서 일하는 일과."""

    def slot_at(self, now: datetime.datetime) -> Slot:
        start = now.replace(hour=0, minute=0)
        return Slot(
            CAFE, "일한다", None, "idle", start, start + datetime.timedelta(days=1)
        )


def at(hour: int, minute: int = 0) -> datetime.datetime:
    return MONDAY.replace(hour=hour, minute=minute)


def party(start: datetime.datetime = at(15), hours: int = 1) -> SocialEvent:
    return SocialEvent(
        name="파티",
        start_time=start,
        end_time=start + datetime.timedelta(hours=hours),
        location_path=SQUARE,
    )


def test_guest_commitment_wins_from_thirty_minutes_before() -> None:
    agenda = Agenda(FixedRoutine())
    agenda.commit(party(), "guest")
    assert agenda.slot_at(at(14, 29)).location_path == CAFE
    assert agenda.slot_at(at(14, 29)).end == at(14, 30)
    slot = agenda.slot_at(at(14, 30))
    assert slot.is_commitment and slot.location_path == SQUARE
    assert slot.end == at(16)
    assert agenda.slot_at(at(16)).location_path == CAFE


def test_host_arrives_an_hour_early_to_prepare_then_hosts() -> None:
    agenda = Agenda(FixedRoutine())
    agenda.commit(party(hours=2), "host")
    assert agenda.slot_at(at(13, 59)).location_path == CAFE
    prep = agenda.slot_at(at(14))
    assert prep.location_path == SQUARE and "준비" in prep.description
    assert prep.end == at(15) and prep.action == "use_object"
    during = agenda.slot_at(at(15, 30))
    assert during.location_path == SQUARE and during.end == at(17)


def test_conflicts_detects_overlap_but_not_the_same_event() -> None:
    agenda = Agenda(FixedRoutine())
    agenda.commit(party(), "guest")
    other = party(at(15, 30)).model_copy(update={"name": "저녁"})
    later = party(at(16)).model_copy(update={"name": "저녁"})
    assert agenda.conflicts(other)
    assert not agenda.conflicts(later)
    assert not agenda.conflicts(party())


def test_commit_is_idempotent_and_host_role_wins() -> None:
    agenda = Agenda(FixedRoutine())
    agenda.commit(party(), "guest")
    agenda.commit(party(), "guest")
    assert len(agenda.commitments) == 1
    agenda.commit(party(), "host")
    assert [c.role for c in agenda.commitments] == ["host"]
