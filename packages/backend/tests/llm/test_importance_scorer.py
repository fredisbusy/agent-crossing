import json

from llm.clients.types import LlmGenerateOptions

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


class RecordingClient:
    def __init__(self, response: str | Exception):
        self.response = response
        self.prompts: list[str] = []
        self.num_predicts: list[int] = []

    def generate(self, **kwargs: object) -> str:
        self.prompts.append(str(kwargs.get("prompt")))
        options = kwargs.get("options")
        assert isinstance(options, LlmGenerateOptions)
        self.num_predicts.append(options.num_predict)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _contexts(n: int) -> list[ImportanceScoringContext]:
    return [
        ImportanceScoringContext(
            observation=f"관찰 {i}", agent_name="Jiho Park", identity_stable_set=[]
        )
        for i in range(n)
    ]


def test_score_many_single_llm_call_preserves_order() -> None:
    client = RecordingClient(json.dumps({"importances": [2, 9, 5]}))
    scorer = LlmImportanceScorer(client=client)

    assert scorer.score_many(_contexts(3)) == [2, 9, 5]
    assert len(client.prompts) == 1
    for i in range(3):
        assert f"{i + 1}. 관찰 {i}" in client.prompts[0]


def test_score_many_clamps_and_falls_back_per_item() -> None:
    client = RecordingClient(json.dumps({"importances": [42, "x", 0]}))
    scorer = LlmImportanceScorer(client=client, fallback_importance=3)

    assert scorer.score_many(_contexts(3)) == [10, 3, 1]


def test_score_many_parse_failure_falls_back() -> None:
    scorer = LlmImportanceScorer(client=RecordingClient("not json"))
    assert scorer.score_many(_contexts(2)) == [3, 3]


def test_score_many_length_mismatch_falls_back() -> None:
    scorer = LlmImportanceScorer(
        client=RecordingClient(json.dumps({"importances": [8]}))
    )
    assert scorer.score_many(_contexts(2)) == [3, 3]


def test_score_many_client_error_falls_back() -> None:
    scorer = LlmImportanceScorer(client=RecordingClient(TimeoutError("t")))
    assert scorer.score_many(_contexts(2)) == [3, 3]


def test_score_many_single_item_uses_single_path_and_small_budget() -> None:
    client = RecordingClient(json.dumps({"importance": 7}))
    scorer = LlmImportanceScorer(client=client)

    assert scorer.score_many(_contexts(1)) == [7]
    assert client.num_predicts == [16]
    assert scorer.score_many([]) == []


def test_score_many_num_predict_grows_with_batch_size() -> None:
    client = RecordingClient(json.dumps({"importances": [1] * 8}))
    scorer = LlmImportanceScorer(client=client)
    scorer.score_many(_contexts(2))
    scorer.score_many(_contexts(8))

    assert client.num_predicts[0] < client.num_predicts[1]
