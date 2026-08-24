from dataclasses import dataclass
from typing import Any, cast

import litellm
from settings import EMBEDDING_DIMENSION

from .types import LlmGenerateOptions


class LiteLlmClientError(RuntimeError):
    pass


def _coerce_text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _read_attr_or_key(value: object, key: str) -> object:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _coerce_float_vector(value: object) -> list[float] | None:
    if not isinstance(value, list):
        return None

    vector: list[float] = []
    for item in cast(list[object], value):
        if not isinstance(item, (int, float)):
            return None
        vector.append(float(item))
    return vector


@dataclass(frozen=True)
class LiteLlmClient:
    """ProviderClient adapter backed by LiteLLM."""

    default_generate_model: str
    default_embedding_model: str
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float | None = 10.0

    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
        model: str | None = None,
    ) -> str:
        final_options = options or LlmGenerateOptions()
        selected_model = model or self.default_generate_model
        messages: list[dict[str, str]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": final_options.temperature,
            "top_p": final_options.top_p,
            "max_tokens": final_options.num_predict,
            "num_retries": 2,
        }
        if self.timeout_seconds is not None:
            kwargs["timeout"] = self.timeout_seconds
        if self.base_url:
            kwargs["api_base"] = self.base_url
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if "qwen" in selected_model.lower():
            kwargs["reasoning_effort"] = "low"
        if selected_model.startswith(("ollama/", "ollama_chat/")):
            kwargs["drop_params"] = True
            if final_options.repeat_penalty is not None:
                kwargs["repeat_penalty"] = final_options.repeat_penalty
            if final_options.presence_penalty is not None:
                kwargs["presence_penalty"] = final_options.presence_penalty
            if final_options.frequency_penalty is not None:
                kwargs["frequency_penalty"] = final_options.frequency_penalty
        if format_json:
            if selected_model.startswith(("ollama/", "ollama_chat/")):
                kwargs["format"] = "json"
            else:
                kwargs["response_format"] = {"type": "json_object"}

        try:
            response = litellm.completion(**kwargs)
        except Exception as exc:
            raise LiteLlmClientError(f"LiteLLM completion failed: {exc}") from exc

        choices = _read_attr_or_key(response, "choices")
        if not isinstance(choices, list) or not choices:
            raise LiteLlmClientError("LiteLLM response is missing choices")

        first_choice = cast(object, choices[0])
        message = _read_attr_or_key(first_choice, "message")
        content = _read_attr_or_key(message, "content")
        text = _coerce_text(content)
        if text is None:
            raise LiteLlmClientError("LiteLLM response is missing message content")
        return text

    def embed(
        self,
        *,
        model: str | None = None,
        input: str,
        truncate: bool = True,
        keep_alive: str = "30m",
        expected_dimension: int | None = None,
    ) -> list[float]:
        _ = truncate
        _ = keep_alive
        expected_dim = (
            expected_dimension
            if expected_dimension is not None
            else EMBEDDING_DIMENSION
        )
        kwargs: dict[str, Any] = {
            "model": model or self.default_embedding_model,
            "input": [input],
            "num_retries": 2,
            "dimensions": expected_dim,
        }
        if self.timeout_seconds is not None:
            kwargs["timeout"] = self.timeout_seconds
        if self.base_url:
            kwargs["api_base"] = self.base_url
        if self.api_key:
            kwargs["api_key"] = self.api_key

        try:
            response = litellm.embedding(**kwargs)
        except Exception as exc:
            raise LiteLlmClientError(f"LiteLLM embedding failed: {exc}") from exc

        data = _read_attr_or_key(response, "data")
        if not isinstance(data, list) or not data:
            raise LiteLlmClientError("LiteLLM embedding response is missing data")

        first_item = cast(object, data[0])
        embedding = _read_attr_or_key(first_item, "embedding")
        vector = _coerce_float_vector(embedding)
        if vector is None:
            raise LiteLlmClientError("LiteLLM embedding response has invalid vector")
        if len(vector) != expected_dim:
            raise LiteLlmClientError(
                f"Embedding dimension mismatch: expected {expected_dim}, got {len(vector)}"
            )
        return vector
