"""들은 사실을 말투에 맞게 전하는 문장 (TODO 6-B 실측 품질 문제)."""

import datetime
import random

import pytest

from minds.schedule.lines import relay, render

NOW = datetime.datetime(2026, 10, 19, 10, 0)
RESEARCH = "저소득 지역사회에 미치는 젠트리피케이션의 영향을 조사하고 있다."


@pytest.mark.parametrize(
    ("fact", "polite", "casual"),
    [
        (RESEARCH, RESEARCH[:-2] + "대요.", RESEARCH[:-2] + "대."),
        ("비교표를 정리하고 논문을 쓰고 있다", "비교표를 정리하고 논문을 쓰고 있대요", "비교표를 정리하고 논문을 쓰고 있대"),
        ("내일 가게를 쉰다.", "내일 가게를 쉰대요.", "내일 가게를 쉰대."),
        ("어제 파티를 열었다. 다들 즐거워했다.", "어제 파티를 열었대요. 다들 즐거워했대요.", "어제 파티를 열었대. 다들 즐거워했대."),
        ("Klaus는 대학원생이다.", "Klaus는 대학원생이래요.", "Klaus는 대학원생이래."),
        ("소문은 사실이 아니다", "소문은 사실이 아니래요", "소문은 사실이 아니래"),
    ],
)
def test_plain_statements_become_hearsay_in_the_speakers_tone(
    fact: str, polite: str, casual: str
) -> None:
    assert relay(fact, "polite") == polite
    assert relay(fact, "casual") == casual


@pytest.mark.parametrize(
    "fact", ["토요일", "토요일에 열린대요", "내일 쉽니다.", "다음 주에 다시 엽니다", "다 같이 간대"]
)
def test_other_endings_are_left_alone(fact: str) -> None:
    assert relay(fact, "polite") == fact
    assert relay(fact, "casual") == fact


@pytest.mark.parametrize("tone", ["polite", "casual"])
def test_share_fact_lines_never_end_in_a_plain_statement(tone: str) -> None:
    for seed in range(12):
        text = render(
            "share_fact",
            tone,  # pyright: ignore[reportArgumentType]
            random.Random(seed),
            now=NOW,
            topic="연구",
            fact=RESEARCH,
        )
        assert "조사하고 있다" not in text
        assert "조사하고 있대요" in text if tone == "polite" else "조사하고 있대" in text


@pytest.mark.parametrize(
    ("topic", "expected"),
    [
        ("파티", "파티는"),
        ("용건", "용건은"),
        ("도서관에 가는지", "그"),
        ("Eddy가 현재 있는 곳", "그"),
        ("오늘입은옷의색깔과무늬", "그"),
        ("", "그"),
    ],
)
def test_unknown_topic_is_echoed_only_when_it_is_a_single_word(
    topic: str, expected: str
) -> None:
    for tone in ("polite", "casual"):
        for seed in range(4):
            text = render("unknown", tone, random.Random(seed), now=NOW, topic=topic)
            assert expected in text
            if expected == "그":
                assert topic == "" or topic not in text
