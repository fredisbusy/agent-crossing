import datetime

from minds.social import (
    ENCOUNTER_LOG_SIZE,
    EncounterLog,
    Slot,
    SocialSeed,
    SocialState,
    rule_choice,
)
from world.contracts import SocialEvent

NOW = datetime.datetime(2023, 2, 13, 10, 0)
HOME = "Smallville > Lin Family House > Kitchen"
PARTY = SocialEvent(
    name="밸런타인데이 파티",
    start_time=datetime.datetime(2023, 2, 14, 17, 0),
    end_time=datetime.datetime(2023, 2, 14, 19, 0),
    location_path="Smallville > Hobbs Cafe > Seating",
)


class HomeRoutine:
    def slot_at(self, now: datetime.datetime) -> Slot:
        return Slot(HOME, "쉰다", None, "idle", now, now + datetime.timedelta(hours=1))


def _state() -> SocialState:
    return SocialState("isabella", HomeRoutine())


def test_rule_choice_leaves_ordinary_encounters_to_the_mind() -> None:
    assert rule_choice(_state(), "maria", NOW, ()) is None


def test_rule_choice_converses_when_there_is_something_to_say() -> None:
    social = _state()
    social.apply_seed(SocialSeed(hosting=(PARTY,)), NOW)

    assert rule_choice(social, "maria", NOW, ()) == (
        "converse",
        "talking_point",
        "꺼낼 이야깃거리: invite",
    )


def test_rule_choice_passes_by_during_cooldown_even_with_talking_points() -> None:
    social = _state()
    social.apply_seed(SocialSeed(hosting=(PARTY,)), NOW)
    social.join_conversation("c1", "maria", NOW)

    choice = rule_choice(social, "maria", NOW + datetime.timedelta(hours=1), ())

    assert choice is not None and choice[:2] == ("pass_by", "cooldown")


def test_log_records_relationship_and_keeps_only_recent_entries() -> None:
    social = _state()
    social.join_conversation("c1", "maria", NOW)
    log = EncounterLog()

    for minute in range(ENCOUNTER_LOG_SIZE + 3):
        at = NOW + datetime.timedelta(minutes=minute)
        assert log.add(social, "maria", at, "pass_by", "chance", "수다 확률 0.10") == "pass_by"

    assert len(log.records) == ENCOUNTER_LOG_SIZE
    last = log.records[-1]
    assert last.at == NOW + datetime.timedelta(minutes=ENCOUNTER_LOG_SIZE + 2)
    assert (last.other_id, last.choice, last.basis) == ("maria", "pass_by", "chance")
    assert last.friendship == social.friendship.score("maria") > 0
    assert last.last_talk == NOW and last.reason == "수다 확률 0.10"
