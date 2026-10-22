import datetime

from minds.social import Slot, SocialSeed, SocialState, event_act
from world.contracts import Holiday, SocialEvent, SpeechAct, Utterance

NOW = datetime.datetime(2023, 2, 13, 10, 0)
CAFE = "Smallville > Hobbs Cafe > Seating"
HOME = "Smallville > Lin Family House > Kitchen"
PARTY = SocialEvent(
    name="밸런타인데이 파티",
    start_time=datetime.datetime(2023, 2, 14, 17, 0),
    end_time=datetime.datetime(2023, 2, 14, 19, 0),
    location_path=CAFE,
)
VALENTINE = Holiday(name="밸런타인데이", gift_item="초콜릿")


class HomeRoutine:
    def slot_at(self, now: datetime.datetime) -> Slot:
        return Slot(HOME, "쉰다", None, "idle", now, now + datetime.timedelta(hours=1))


def _state(resident_id: str = "maria") -> SocialState:
    return SocialState(resident_id, HomeRoutine())


def _said(speaker: str, listener: str, *acts: SpeechAct, minute: int = 0) -> Utterance:
    return Utterance(
        speaker_id=speaker,
        listener_ids=(listener,),
        text=f"{speaker}의 말 {minute}",
        acts=acts,
        spoken_at=NOW + datetime.timedelta(minutes=minute),
    )


def test_host_seed_commits_and_becomes_talking_point() -> None:
    isabella = _state("isabella")
    isabella.apply_seed(SocialSeed(hosting=(PARTY,)), NOW)
    [commitment] = isabella.agenda.commitments
    assert commitment.role == "host" and commitment.event.host_id == "isabella"
    points = isabella.talking_points("maria", NOW)
    assert [p.kind for p in points] == ["invite"]
    assert points[0].event == PARTY.name and points[0].end_time == PARTY.end_time


def test_invite_once_then_no_longer_a_talking_point() -> None:
    isabella = _state("isabella")
    isabella.host(PARTY, NOW)
    isabella.said(_said("isabella", "maria", event_act("invite", PARTY)), NOW)
    assert isabella.talking_points("maria", NOW) == ()
    assert [p.kind for p in isabella.talking_points("klaus", NOW)] == ["invite"]


def test_heard_invite_teaches_event_with_host_and_accept_commits() -> None:
    maria = _state()
    maria.hear(_said("isabella", "maria", event_act("invite", PARTY)), NOW)
    known = maria.facts.get(PARTY.name)
    assert known is not None and known.event is not None
    assert known.event.host_id == "isabella" and "Seating" in known.fact
    maria.said(_said("maria", "isabella", event_act("accept", PARTY), minute=1), NOW)
    [commitment] = maria.agenda.commitments
    assert commitment.role == "guest" and commitment.event.host_id == "isabella"
    assert maria.friendship.score("isabella") == 1


def test_overheard_invite_is_not_an_invitation_but_rumor_is_learned() -> None:
    eddy = _state("eddy")
    eddy.hear(_said("isabella", "maria", event_act("invite", PARTY)), NOW)
    assert eddy.facts.get(PARTY.name) is None
    rumor = event_act("share_fact", PARTY, topic=PARTY.name, fact="파티 한대")
    eddy.hear(_said("maria", "klaus", rumor, minute=1), NOW)
    assert eddy.facts.get(PARTY.name) is not None


def test_same_utterance_is_applied_once() -> None:
    isabella = _state("isabella")
    gift = _said("maria", "isabella", SpeechAct(kind="gift", item="초콜릿"))
    isabella.hear(gift, NOW)
    isabella.hear(gift, NOW)
    assert isabella.friendship.score("maria") == 5


def test_guest_invites_close_friend_and_gifts_on_holiday() -> None:
    maria = _state()
    maria.apply_seed(SocialSeed(friendships={"klaus": 30, "eddy": 5}), NOW)
    maria.hear(_said("isabella", "maria", event_act("invite", PARTY)), NOW)
    maria.said(_said("maria", "isabella", event_act("accept", PARTY), minute=1), NOW)
    to_klaus = [p.kind for p in maria.talking_points("klaus", NOW, (VALENTINE,))]
    assert to_klaus == ["invite", "gift"]
    to_eddy = [p.kind for p in maria.talking_points("eddy", NOW, (VALENTINE,))]
    assert to_eddy == ["share_fact"]
    maria.said(
        _said("maria", "klaus", SpeechAct(kind="gift", item="초콜릿"), minute=2), NOW
    )
    after = [p.kind for p in maria.talking_points("klaus", NOW, (VALENTINE,))]
    assert after == ["invite"]


def test_new_invite_makes_the_speaker_host_it() -> None:
    klaus = _state("klaus")
    coffee = SpeechAct(
        kind="invite",
        event="커피 한잔",
        start_time=datetime.datetime(2023, 2, 13, 15, 0),
        location_path=CAFE,
    )
    klaus.said(_said("klaus", "maria", coffee), NOW)
    [commitment] = klaus.agenda.commitments
    assert commitment.role == "host" and commitment.event.name == "커피 한잔"
    assert commitment.event.end_time == datetime.datetime(2023, 2, 13, 16, 0)


def test_inviting_to_a_rumored_party_is_a_companion_invite_not_hosting() -> None:
    hosted = PARTY.model_copy(update={"host_id": "isabella"})
    rumor = event_act("share_fact", hosted, topic=PARTY.name, fact="파티 한대")
    maria = _state()
    maria.hear(_said("eddy", "maria", rumor), NOW)
    maria.said(_said("maria", "klaus", event_act("invite", hosted), minute=1), NOW)
    assert maria.agenda.commitments == []
    known = maria.facts.get(PARTY.name)
    assert known is not None and known.event is not None
    assert known.event.host_id == "isabella"


def test_host_survives_rumor_and_companion_invite() -> None:
    hosted = PARTY.model_copy(update={"host_id": "isabella"})
    klaus = _state("klaus")
    klaus.apply_seed(SocialSeed(friendships={"isabella": 30}), NOW)
    klaus.hear(_said("maria", "klaus", event_act("invite", hosted)), NOW)
    known = klaus.facts.get(PARTY.name)
    assert known is not None and known.event is not None
    assert known.event.host_id == "isabella"
    klaus.said(_said("klaus", "maria", event_act("accept", hosted), minute=1), NOW)
    assert klaus.talking_points("isabella", NOW) == ()


def test_rumor_text_is_dated_when_told_and_told_once_per_topic() -> None:
    eddy = _state("eddy")
    rumor = event_act("share_fact", PARTY, topic=PARTY.name, fact="파티 한대")
    eddy.hear(_said("maria", "eddy", rumor), NOW)
    next_day = NOW + datetime.timedelta(days=1)
    [point] = eddy.talking_points("klaus", next_day)
    assert point.fact is not None and point.fact.startswith("오늘 오후 5시")
    eddy.said(_said("eddy", "klaus", point, minute=1), next_day)
    eddy.hear(_said("sam", "eddy", rumor, minute=2), next_day)
    assert eddy.talking_points("klaus", next_day) == ()


def test_accept_that_overlaps_another_commitment_is_not_kept() -> None:
    maria = _state()
    dinner = PARTY.model_copy(update={"name": "저녁 약속"})
    maria.said(_said("maria", "klaus", event_act("accept", dinner)), NOW)
    maria.said(_said("maria", "isabella", event_act("accept", PARTY), minute=1), NOW)
    assert [c.event.name for c in maria.agenda.commitments] == ["저녁 약속"]


def test_redundant_acts_are_detected_per_partner() -> None:
    hosted = PARTY.model_copy(update={"host_id": "isabella"})
    isabella = _state("isabella")
    isabella.host(hosted, NOW)
    isabella.said(_said("isabella", "sam", event_act("invite", hosted)), NOW)
    assert isabella.is_redundant(event_act("invite", hosted), "sam", NOW)
    assert not isabella.is_redundant(event_act("invite", hosted), "klaus", NOW)
    assert isabella.is_redundant(event_act("accept", hosted), "sam", NOW)
    mei = _state("mei")
    mei.hear(_said("isabella", "mei", event_act("invite", hosted)), NOW)
    rumor = mei.fact_act(mei.facts.all()[0], NOW)
    assert mei.is_redundant(rumor, "isabella", NOW)
    assert not mei.is_redundant(rumor, "eddy", NOW)


def test_partner_who_said_yes_is_not_invited_again_and_noted() -> None:
    hosted = PARTY.model_copy(update={"host_id": "isabella"})
    isabella = _state("isabella")
    isabella.host(hosted, NOW)
    isabella.hear(_said("klaus", "isabella", event_act("accept", hosted)), NOW)
    assert isabella.talking_points("klaus", NOW) == ()
    notes = [n.format(partner="Klaus") for n in isabella.partner_notes("klaus", NOW)]
    assert notes == ["Klaus는 밸런타인데이 파티에 가겠다고 이미 말했다."]
