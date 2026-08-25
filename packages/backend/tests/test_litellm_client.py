from __future__ import annotations

import json
from typing import Any

import litellm
from pydantic import BaseModel, ConfigDict, Field

from llm.clients.litellm_client import LiteLlmClient
from llm.clients.types import LlmGenerateOptions
from llm.structured_outputs import DayPlanOutput


class StatusOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=12)


def test_generate_uses_litellm_completion_shape(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> dict[str, object]:
        captured.update(kwargs)
        return {"choices": [{"message": {"content": '{"status":"ok"}'}}]}

    monkeypatch.setattr(litellm, "completion", fake_completion)
    client = LiteLlmClient(
        base_url="https://model.byfred.io",
        api_key="test-key",
        timeout_seconds=7.0,
        default_generate_model="ollama_chat/qwen3.8:27b-mlx",
        default_embedding_model="ollama/bge-m3",
    )

    response = client.generate(
        prompt="Return JSON",
        system="You are concise.",
        options=LlmGenerateOptions(
            temperature=0.3,
            top_p=0.8,
            num_predict=60,
            repeat_penalty=1.2,
            presence_penalty=0.4,
            frequency_penalty=0.1,
        ),
        format_json=True,
    )

    assert response == '{"status":"ok"}'
    assert captured["model"] == "ollama_chat/qwen3.8:27b-mlx"
    assert captured["api_base"] == "https://model.byfred.io"
    assert captured["api_key"] == "test-key"
    assert captured["timeout"] == 7.0
    assert captured["num_retries"] == 2
    assert captured["messages"] == [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Return JSON"},
    ]
    assert captured["temperature"] == 0.3
    assert captured["top_p"] == 0.8
    assert captured["max_tokens"] == 60
    assert captured["reasoning_effort"] == "none"
    assert captured["drop_params"] is True
    assert captured["repeat_penalty"] == 1.2
    assert captured["presence_penalty"] == 0.4
    assert captured["frequency_penalty"] == 0.1
    assert captured["format"] == "json"


def test_generate_suppresses_reasoning_for_non_qwen_ollama_thinking_model(
    monkeypatch,
) -> None:
    """Not qwen-specific: any Ollama "thinking"-capable model (e.g. gemma4)
    should skip reasoning_content for structured calls too, or it burns the
    output budget on it and needs a retry (reproduced against a live
    gemma4:26b before this fix: truncated at 256 tokens, ~12s; fixed: no
    retry, ~1s)."""
    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> dict[str, object]:
        captured.update(kwargs)
        return {"choices": [{"message": {"content": '{"status":"ok"}'}}]}

    monkeypatch.setattr(litellm, "completion", fake_completion)
    client = LiteLlmClient(
        default_generate_model="ollama_chat/gemma4:26b",
        default_embedding_model="ollama/bge-m3",
    )

    _ = client.generate(
        prompt="Return JSON",
        options=LlmGenerateOptions(num_predict=60),
        response_model=StatusOutput,
    )

    assert captured["reasoning_effort"] == "none"


def test_generate_uses_strict_response_schema_without_penalties_for_non_ollama(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> dict[str, object]:
        captured.update(kwargs)
        return {"choices": [{"message": {"content": '{"status":"ok"}'}}]}

    monkeypatch.setattr(litellm, "completion", fake_completion)
    client = LiteLlmClient(
        default_generate_model="gemini/gemini-2.5-flash-lite",
        default_embedding_model="gemini/text-embedding-004",
    )

    _ = client.generate(
        prompt="Return JSON",
        options=LlmGenerateOptions(
            repeat_penalty=1.2,
            presence_penalty=0.4,
            frequency_penalty=0.1,
        ),
        response_model=StatusOutput,
    )

    assert captured["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "StatusOutput",
            "strict": True,
            "schema": StatusOutput.model_json_schema(),
        },
    }
    assert "reasoning_effort" not in captured
    assert "repeat_penalty" not in captured
    assert "presence_penalty" not in captured
    assert "frequency_penalty" not in captured


def test_generate_passes_pydantic_json_schema_to_ollama() -> None:
    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"status":"ok"}'},
                }
            ]
        }

    original_completion = litellm.completion
    litellm.completion = fake_completion
    try:
        client = LiteLlmClient(
            default_generate_model="ollama_chat/qwen3.8:27b-mlx",
            default_embedding_model="ollama/bge-m3",
        )
        response = client.generate(
            prompt="Return status",
            response_model=StatusOutput,
        )
    finally:
        litellm.completion = original_completion

    assert response == '{"status":"ok"}'
    assert captured["format"] == StatusOutput.model_json_schema()
    assert captured["reasoning_effort"] == "none"


def test_generate_retries_truncated_structured_output_with_larger_budget(
    monkeypatch,
) -> None:
    calls: list[dict[str, Any]] = []
    responses = [
        {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": '{"status":"'},
                }
            ]
        },
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"status":"ok"}'},
                }
            ]
        },
    ]

    def fake_completion(**kwargs: Any) -> dict[str, object]:
        calls.append(dict(kwargs))
        return responses.pop(0)

    monkeypatch.setattr(litellm, "completion", fake_completion)
    client = LiteLlmClient(
        default_generate_model="ollama_chat/qwen3.8:27b-mlx",
        default_embedding_model="ollama/bge-m3",
    )

    response = client.generate(
        prompt="Return status",
        options=LlmGenerateOptions(num_predict=64),
        response_model=StatusOutput,
    )

    assert response == '{"status":"ok"}'
    assert [call["max_tokens"] for call in calls] == [64, 192]


def test_generate_retries_output_that_violates_text_length_schema(
    monkeypatch,
) -> None:
    calls: list[dict[str, Any]] = []
    responses = [
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"status":"far too long for schema"}'},
                }
            ]
        },
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"status":"ok"}'},
                }
            ]
        },
    ]

    def fake_completion(**kwargs: Any) -> dict[str, object]:
        calls.append(dict(kwargs))
        return responses.pop(0)

    monkeypatch.setattr(litellm, "completion", fake_completion)
    client = LiteLlmClient(
        default_generate_model="ollama_chat/qwen3.8:27b-mlx",
        default_embedding_model="ollama/bge-m3",
    )

    response = client.generate(
        prompt="Return status",
        response_model=StatusOutput,
    )

    assert response == '{"status":"ok"}'
    assert len(calls) == 2
    assert calls[1]["messages"][-2] == {
        "role": "assistant",
        "content": '{"status":"far too long for schema"}',
    }
    correction = calls[1]["messages"][-1]
    assert correction["role"] == "user"
    assert "status: String should have at most 12 characters" in correction["content"]
    assert "replacement JSON document only" in correction["content"]


def test_generate_tells_day_plan_retry_to_reduce_items_to_schema_maximum(
    monkeypatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def day_plan(count: int) -> str:
        return json.dumps(
            {
                "items": [
                    {
                        "start_time": "2026-08-25T06:00:00",
                        "end_time": "2026-08-25T07:00:00",
                        "location": "브라이어 코브 > 지호의 집",
                        "action_content": f"하루 일과 {index + 1}을 준비한다.",
                    }
                    for index in range(count)
                ]
            },
            ensure_ascii=False,
        )

    responses = [
        {"choices": [{"message": {"content": day_plan(10)}}]},
        {"choices": [{"message": {"content": day_plan(8)}}]},
    ]

    def fake_completion(**kwargs: Any) -> dict[str, object]:
        calls.append(dict(kwargs))
        return responses.pop(0)

    monkeypatch.setattr(litellm, "completion", fake_completion)
    client = LiteLlmClient(
        default_generate_model="ollama_chat/qwen3.8:27b-mlx",
        default_embedding_model="ollama/bge-m3",
    )

    response = client.generate(
        prompt="Return 5 to 8 day-plan items",
        response_model=DayPlanOutput,
    )

    assert len(DayPlanOutput.model_validate_json(response).items) == 8
    correction = calls[1]["messages"][-1]["content"]
    assert "items: List should have at most 8 items" in correction


def test_generate_omits_timeout_when_local_model_has_no_deadline(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> dict[str, object]:
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "done"}}]}

    monkeypatch.setattr(litellm, "completion", fake_completion)
    client = LiteLlmClient(
        timeout_seconds=None,
        default_generate_model="ollama_chat/qwen3.8:27b-mlx",
        default_embedding_model="ollama/bge-m3",
    )

    assert client.generate(prompt="Take the time needed") == "done"
    assert "timeout" not in captured


def test_generate_keeps_low_reasoning_for_unstructured_qwen_output(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> dict[str, object]:
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "done"}}]}

    monkeypatch.setattr(litellm, "completion", fake_completion)
    client = LiteLlmClient(
        timeout_seconds=None,
        default_generate_model="ollama_chat/qwen3.8:27b-mlx",
        default_embedding_model="ollama/bge-m3",
    )

    assert client.generate(prompt="Think about this") == "done"
    assert captured["reasoning_effort"] == "low"


def test_embed_reads_litellm_embedding_vector(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_embedding(**kwargs: Any) -> dict[str, object]:
        captured.update(kwargs)
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    monkeypatch.setattr(litellm, "embedding", fake_embedding)
    client = LiteLlmClient(
        base_url="https://model.byfred.io",
        default_generate_model="ollama_chat/qwen3.8:27b-mlx",
        default_embedding_model="ollama/bge-m3",
    )

    embedding = client.embed(input="hello", expected_dimension=3)

    assert embedding == [0.1, 0.2, 0.3]
    assert captured["model"] == "ollama/bge-m3"
    assert captured["input"] == ["hello"]
    assert captured["num_retries"] == 2
    assert captured["dimensions"] == 3
