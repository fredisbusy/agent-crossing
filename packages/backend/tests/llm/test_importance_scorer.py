import json

from llm import (
    ImportanceScoringContext,
    LlmImportanceScorer,
    clamp_importance,
    parse_importance_value,
)


class StubGenerationClient:
    def __init__(self, response: str | Exception):
        self.response = response
        self.calls: int = 0
        self.last_format_json: bool | None = None

    def generate(self, **kwargs: object) -> str:
        self.calls += 1
        self.last_format_json = kwargs.get("format_json") is True
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_clamp_importance_bounds() -> None:
    assert clamp_importance(-3) == 1
    assert clamp_importance(5) == 5
    assert clamp_importance(42) == 10


def test_parse_importance_value_json_success() -> None:
    text = json.dumps({"importance": 8, "reason": "important"})
    assert parse_importance_value(text, fallback_importance=3) == 8


def test_parse_importance_value_string_and_clamp() -> None:
    text = json.dumps({"importance": "11", "reason": "critical"})
    assert parse_importance_value(text, fallback_importance=3) == 10


def test_parse_importance_value_malformed_fallback() -> None:
    assert parse_importance_value("not-json", fallback_importance=3) == 3


def test_llm_importance_scorer_success() -> None:
    client = StubGenerationClient('{"importance": 7, "reason": "goal relevant"}')
    scorer = LlmImportanceScorer(client=client)

    score = scorer.score(
        ImportanceScoringContext(
            observation="지호가 오늘 중요한 회의 약속을 잡았다.",
            agent_name="Jiho Park",
            identity_stable_set=["Jiho is reliable and values promises."],
            current_plan="오후 3시 미팅 참석",
        )
    )

    assert score == 7
    assert client.calls == 1
    assert client.last_format_json is True


def test_llm_importance_scorer_fallback_on_client_error() -> None:
    client = StubGenerationClient(TimeoutError("timed out"))
    scorer = LlmImportanceScorer(client=client, fallback_importance=3)

    score = scorer.score(
        ImportanceScoringContext(
            observation="일상 산책",
            agent_name="Jiho Park",
            identity_stable_set=[],
        )
    )
    assert score == 3
