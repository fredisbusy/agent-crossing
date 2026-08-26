from llm.governance import (
    is_repetitive_reply,
    recent_replies_for_echo_check,
    semantic_repeat_rate,
    topic_progress_rate,
)
from run_agent_loop_simulation import (
    DEFAULT_CONFIG,
)
from world.session import build_turn_observed_events


def test_recent_replies_for_echo_check_collects_cross_speaker_history() -> None:
    history = [
        ("Jiho Park", "안녕하세요!"),
        ("Sujin Lee", "안녕하세요!"),
        ("Jiho Park", "책 정리 마무리 중이에요."),
    ]

    replies = recent_replies_for_echo_check(session_history=history, window=2)

    assert replies == ["안녕하세요!", "책 정리 마무리 중이에요."]


def test_is_repetitive_reply_blocks_cross_speaker_echo() -> None:
    history = [
        ("Jiho Park", "안녕하세요!"),
        ("Sujin Lee", "안녕하세요!"),
    ]
    recent_replies = recent_replies_for_echo_check(session_history=history, window=4)

    assert is_repetitive_reply("안녕하세요.", recent_replies) is True


def test_recent_replies_for_echo_check_returns_empty_for_non_positive_window() -> None:
    history = [("Jiho Park", "안녕하세요!")]

    replies = recent_replies_for_echo_check(session_history=history, window=0)

    assert replies == []


def test_build_turn_observed_events_uses_co_location_on_opening_turn() -> None:
    observed_events = build_turn_observed_events(
        language="ko",
        partner_name="Sujin Lee",
        incoming_partner_utterance=None,
    )

    assert observed_events == ["같은 장소에 도착한 상대: Sujin Lee."]


def test_build_turn_observed_events_prefers_latest_utterance_when_present() -> None:
    observed_events = build_turn_observed_events(
        language="ko",
        partner_name="Sujin Lee",
        incoming_partner_utterance="새로운 디카프 블렌드 테스트 중이에요.",
    )

    assert observed_events == [
        "Sujin Lee의 직전 발화를 들음: 새로운 디카프 블렌드 테스트 중이에요."
    ]


def test_default_turn_time_step_seconds() -> None:
    assert DEFAULT_CONFIG.turn_time_step_seconds == 45


def test_semantic_repeat_rate_detects_highly_similar_replies() -> None:
    history = [
        ("Jiho Park", "오늘은 커피 이야기하자"),
        ("Sujin Lee", "오늘은 커피 이야기하자"),
        ("Jiho Park", "다른 주제도 괜찮아"),
    ]

    rate = semantic_repeat_rate(session_history=history)

    assert rate > 0.0


def test_topic_progress_rate_rewards_new_content() -> None:
    history = [
        ("Jiho Park", "오늘은 커피 이야기하자"),
        ("Sujin Lee", "좋아, 나는 디카프 추출도 궁금해"),
        ("Jiho Park", "그럼 원두 로스팅 차이도 같이 보자"),
    ]

    rate = topic_progress_rate(history)

    assert rate >= 0.66
