"""반응 결정을 남기는 plan 기억 문장 (SPEC §7)."""

import datetime

from minds.llm.planning.reaction_notes import QUOTED_MAX_CHARS, decision_memory
from world.contracts import Observation

NOW = datetime.datetime(2023, 2, 13, 13, 34)
HALL = "Smallville > Hobbs Cafe > Seating"
NAMES = {"eddy_lin": "Eddy Lin", "maria_lopez": "Maria Lopez"}


def sight(text: str, who: str | None) -> Observation:
    return Observation(
        kind="sight" if who else "event",
        text=text,
        observed_at=NOW,
        location_path=HALL,
        subject_id=who,
    )


def test_decision_names_who_was_seen_instead_of_pasting_observations() -> None:
    seen = [
        sight("Eddy Lin이 홉스 카페 홀에서 오크힐 대학 도서관 쪽으로 이동한다", "eddy_lin"),
        sight("Maria Lopez가 홉스 카페 홀에서 오크힐 대학 도서관 쪽으로 이동한다", "maria_lopez"),
        sight("Eddy Lin이 홉스 카페에서 오크힐 대학 도서관 쪽으로 이동한다", "eddy_lin"),
    ]
    text = decision_memory(
        "Isabella Rodriguez",
        seen,
        NAMES,
        "Eddy와 Maria에게 따뜻하게 손을 흔들며 인사한다.",
    )
    assert text == (
        "Isabella Rodriguez는 Eddy Lin, Maria Lopez를 보고 이렇게 하기로 했다: "
        "Eddy와 Maria에게 따뜻하게 손을 흔들며 인사한다"
    )
    assert "한다.하기로" not in text and ";" not in text


def test_particles_follow_the_last_name_and_unknown_ids_get_a_readable_name() -> None:
    seen = [sight("Mei Lin이 홉스 카페 홀에서 점심을 먹는다", "mei_lin")]
    text = decision_memory("Eddy Lin", seen, {}, "인사한다")
    assert text == "Eddy Lin은 Mei Lin을 보고 이렇게 하기로 했다: 인사한다"


def test_event_without_subject_is_quoted_and_truncated() -> None:
    text = decision_memory("Isabella", [sight("오늘은 밸런타인데이다.", None)], {}, "장식을 단다")
    assert text == "Isabella는 '오늘은 밸런타인데이다'를 보고 이렇게 하기로 했다: 장식을 단다"
    long = decision_memory("Isabella", [sight("가" * 200, None)], {}, "쉰다")
    assert "가" * QUOTED_MAX_CHARS + "…'를 보고" in long
    assert "가" * (QUOTED_MAX_CHARS + 1) not in long
