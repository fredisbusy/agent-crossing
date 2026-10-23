import threading
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from typing import Any, cast

import litellm
from settings import EMBEDDING_DIMENSION, LLM_MAX_CONCURRENCY, LLM_NUM_RETRIES

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
    timeout_seconds: float = 10.0
    embedding_base_url: str | None = None
    """임베딩 전용 엔드포인트. 없으면 `base_url`."""
    embedding_api_key: str | None = None
    """임베딩 전용 키. 없으면 `api_key`."""
    reasoning_effort: str | None = None
    """추론 모델에 보내는 추론 강도. 없으면 보내지 않는다."""
    num_retries: int = LLM_NUM_RETRIES
    """LiteLLM 재시도 횟수. 호출 하나의 최악 소요는 timeout x (1 + 재시도)."""
    max_concurrency: int = LLM_MAX_CONCURRENCY
    """동시 요청 상한. 주민 마음들이 동시에 부르므로 Ollama 같은 직렬 백엔드의 대기열을 막는다."""
    _slots: threading.BoundedSemaphore | None = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        slots = (
            threading.BoundedSemaphore(self.max_concurrency)
            if self.max_concurrency > 0
            else None
        )
        object.__setattr__(self, "_slots", slots)

    def _slot(self) -> AbstractContextManager[object]:
        return self._slots if self._slots is not None else nullcontext()

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
            "timeout": self.timeout_seconds,
            "num_retries": self.num_retries,
        }
        if self.base_url:
            kwargs["api_base"] = self.base_url
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
            # LiteLLM 모델 표에 아직 없는 새 모델(예: gpt-6-luna)도 이 값을 그대로 보낸다.
            kwargs["allowed_openai_params"] = ["reasoning_effort"]
        if selected_model.startswith(("ollama/", "ollama_chat/")):
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
            with self._slot():
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
        return self.embed_many(
            model=model, inputs=[input], expected_dimension=expected_dimension
        )[0]

    def embed_many(
        self,
        *,
        model: str | None = None,
        inputs: list[str],
        expected_dimension: int | None = None,
    ) -> list[list[float]]:
        """여러 문장을 한 번의 요청으로 임베딩한다. 결과 순서는 `inputs`와 같다."""
        if not inputs:
            return []
        expected_dim = (
            expected_dimension
            if expected_dimension is not None
            else EMBEDDING_DIMENSION
        )
        kwargs: dict[str, Any] = {
            "model": model or self.default_embedding_model,
            "input": inputs,
            "timeout": self.timeout_seconds,
            "num_retries": self.num_retries,
            "dimensions": expected_dim,
        }
        base_url = self.embedding_base_url or self.base_url
        api_key = self.embedding_api_key or self.api_key
        if base_url:
            kwargs["api_base"] = base_url
        if api_key:
            kwargs["api_key"] = api_key

        try:
            with self._slot():
                response = litellm.embedding(**kwargs)
        except Exception as exc:
            raise LiteLlmClientError(f"LiteLLM embedding failed: {exc}") from exc

        data = _read_attr_or_key(response, "data")
        if not isinstance(data, list) or len(data) != len(inputs):
            raise LiteLlmClientError(
                "LiteLLM embedding response does not match the number of inputs"
            )
        items = cast(list[object], data)
        return [
            _parse_embedding_item(item, expected_dim=expected_dim) for item in items
        ]


def _parse_embedding_item(item: object, *, expected_dim: int) -> list[float]:
    vector = _coerce_float_vector(_read_attr_or_key(item, "embedding"))
    if vector is None:
        raise LiteLlmClientError("LiteLLM embedding response has invalid vector")
    if len(vector) != expected_dim:
        raise LiteLlmClientError(
            f"Embedding dimension mismatch: expected {expected_dim}, got {len(vector)}"
        )
    return vector
