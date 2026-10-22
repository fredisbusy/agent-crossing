from agents.brain.observation_text import build_observation_text


def test_minimal_observation_has_only_location_sentence() -> None:
    text = build_observation_text(
        agent_name="Jiho", location=None, observed_entities=[], observed_events=[]
    )

    assert text == "Jiho이(가) 알 수 없는 장소에 있다."


def test_same_situation_gives_same_text() -> None:
    first = build_observation_text(
        agent_name="Jiho",
        location="Town > Cafe",
        observed_entities=["Sujin"],
        observed_events=["a", "b"],
    )
    second = build_observation_text(
        agent_name="Jiho",
        location="Town > Cafe",
        observed_entities=["Sujin"],
        observed_events=["a", "b"],
    )

    assert first == second
    assert first.endswith("사건: a; b.")
