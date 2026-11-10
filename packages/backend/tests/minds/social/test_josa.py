import pytest

from minds.social import josa
from minds.social.events import has_final


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("파티", False),
        ("도서관", True),
        ("Mei Lin", True),
        ("Eddy Lin", True),
        ("Sam", True),
        ("Oak Hill", True),
        ("Wang", True),
        ("Jack", True),
        ("Bob", True),
        ("Philip", True),
        ("Isabella Rodriguez", False),
        ("Klaus Mueller", False),
        ("Maria Lopez", False),
        ("Sam Moore", False),
        ("Maria", False),
        ("Eddy", False),
        ("Mark", False),
        ("3", True),
        ("2", False),
        ("", False),
    ],
)
def test_has_final_reads_hangul_roman_names_and_digits(
    word: str, expected: bool
) -> None:
    assert has_final(word) is expected


def test_josa_picks_the_particle_for_roman_names() -> None:
    assert josa("Mei Lin", "이", "가") == "Mei Lin이"
    assert josa("Eddy Lin", "은", "는") == "Eddy Lin은"
    assert josa("John Lin", "을", "를") == "John Lin을"
    assert josa("Isabella Rodriguez", "이", "가") == "Isabella Rodriguez가"
    assert josa("Klaus Mueller", "은", "는") == "Klaus Mueller는"


def test_josa_ignores_trailing_punctuation() -> None:
    assert josa("밸런타인데이 파티", "이", "가") == "밸런타인데이 파티가"
    assert has_final("도서관.") and not has_final("카페!")
