from __future__ import annotations

from typing import Any

import litellm

from llm.clients.litellm_client import LiteLlmClient
from llm.clients.types import LlmGenerateOptions


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


def test_generate_uses_response_format_without_penalties_for_non_ollama_json(
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
        format_json=True,
    )

    assert captured["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in captured
    assert "repeat_penalty" not in captured
    assert "presence_penalty" not in captured
    assert "frequency_penalty" not in captured


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
