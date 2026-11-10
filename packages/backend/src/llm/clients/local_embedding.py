"""임베딩만 이 컴퓨터의 sentence-transformers 모델로 계산하는 클라이언트.

`EMBEDDING_MODEL=local/BAAI/bge-m3`처럼 `local/` 접두사를 쓰면 켜진다.
임베딩 API를 쓸 수 없을 때(크레딧 소진, 오프라인)도 마을을 돌릴 수 있게 한다.
"""

import threading
from typing import Any

from settings import EMBEDDING_DIMENSION

from .litellm_client import LiteLlmClientError
from .types import LlmGenerateOptions

LOCAL_EMBEDDING_PREFIX = "local/"


def is_local_embedding_model(model: str) -> bool:
    return model.startswith(LOCAL_EMBEDDING_PREFIX)


class LocalEmbeddingClient:
    """생성은 `inner`에 맡기고 임베딩만 로컬 모델로 계산한다. 벡터는 정규화한다."""

    def __init__(self, inner: Any, model: str) -> None:
        self._inner = inner
        self._model_name = model.removeprefix(LOCAL_EMBEDDING_PREFIX)
        self._model: Any = None
        self._lock = threading.Lock()
        """모델 로딩과 인코딩을 한 번에 하나씩만 한다(sentence-transformers는 스레드 안전을 보장하지 않는다)."""

    def __getattr__(self, name: str) -> Any:
        """캐시 키에 쓰이는 `default_generate_model` 같은 속성은 감싼 클라이언트 것을 그대로 보인다."""
        return getattr(self._inner, name)

    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
        model: str | None = None,
    ) -> str:
        return str(
            self._inner.generate(
                prompt=prompt,
                system=system,
                options=options,
                format_json=format_json,
                **({} if model is None else {"model": model}),
            )
        )

    def embed(
        self,
        *,
        model: str | None = None,
        input: str,
        truncate: bool = True,
        keep_alive: str = "30m",
        expected_dimension: int | None = None,
    ) -> list[float]:
        _ = (truncate, keep_alive)
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
        _ = model
        if not inputs:
            return []
        expected = (
            expected_dimension if expected_dimension is not None else EMBEDDING_DIMENSION
        )
        with self._lock:
            vectors = self._load().encode(
                list(inputs), normalize_embeddings=True, show_progress_bar=False
            )
        result = [[float(value) for value in vector] for vector in vectors]
        if any(len(vector) != expected for vector in result):
            raise LiteLlmClientError(
                f"Local embedding dimension mismatch: expected {expected}, "
                f"got {len(result[0])} from {self._model_name}"
            )
        return result

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise LiteLlmClientError(
                    "sentence-transformers is required for local embeddings"
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        return self._model


__all__ = ["LOCAL_EMBEDDING_PREFIX", "LocalEmbeddingClient", "is_local_embedding_model"]
