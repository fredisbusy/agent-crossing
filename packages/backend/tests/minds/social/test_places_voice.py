import random

from minds.social import VOICE_DESCRIPTION, SpeechStyle, place_name, place_names
from world.residents import load_resident_configs
from world.space import load_town_space


def test_every_map_place_has_a_korean_name() -> None:
    names = place_names()
    missing = [p for p in load_town_space().location_paths() if p not in names]
    assert missing == []


def test_place_name_falls_back_to_the_closest_named_ancestor() -> None:
    assert place_name("Smallville > Hobbs Cafe > Seating") == "홉스 카페 홀"
    assert place_name("Smallville > Hobbs Cafe > Seating > Table 3") == "홉스 카페 홀"
    assert place_name("Elsewhere > Hut") == "Hut"


def test_every_resident_has_a_distinct_voice() -> None:
    configs = load_resident_configs()
    voices = [c.voice for c in configs]
    assert None not in voices and len(set(voices)) == len(voices)


def test_style_describes_and_decorates_with_catchphrase() -> None:
    style = SpeechStyle(voice="bright", catchphrase="헤헤")
    assert style.tone == "casual"
    assert (
        VOICE_DESCRIPTION["bright"] in style.describe() and "헤헤" in style.describe()
    )
    rng = random.Random(0)
    texts = {style.decorate("안녕!", rng) for _ in range(30)}
    assert texts == {"안녕!", "안녕! 헤헤"}
