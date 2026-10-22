from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from settings import EMBEDDING_CACHE_SIZE, EMBEDDING_DIMENSION


@dataclass(frozen=True)
class EmbeddingEncodingContext:
    text: str


class EmbeddingEncoder(Protocol):
    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray: ...


@runtime_checkable
class BatchEmbeddingEncoder(Protocol):
    def encode_many(
        self, contexts: list[EmbeddingEncodingContext]
    ) -> list[np.ndarray]: ...


class EmbeddingClient(Protocol):
    def embed(
        self,
        *,
        model: str | None = None,
        input: str,
        truncate: bool = True,
        keep_alive: str = "30m",
        expected_dimension: int | None = None,
    ) -> list[float]: ...


@runtime_checkable
class BatchEmbeddingClient(Protocol):
    def embed_many(
        self,
        *,
        model: str | None = None,
        inputs: list[str],
        expected_dimension: int | None = None,
    ) -> list[list[float]]: ...


class LlmEmbeddingEncoder:
    """
    텍스트를 임베딩한다. 같은 텍스트는 다시 요청하지 않도록 LRU 캐시에 담고,
    여러 텍스트는 클라이언트가 지원하면 한 번의 요청으로 묶는다.
    """

    def __init__(
        self,
        client: EmbeddingClient,
        model: str = "bge-m3",
        cache_size: int = EMBEDDING_CACHE_SIZE,
    ) -> None:
        self.client: EmbeddingClient = client
        self.model: str = model
        self.cache_size: int = cache_size
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()

    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray:
        return self.encode_many([context])[0]

    def encode_many(self, contexts: list[EmbeddingEncodingContext]) -> list[np.ndarray]:
        texts = [context.text for context in contexts]
        resolved: dict[str, np.ndarray] = {}
        missing: list[str] = []
        for text in dict.fromkeys(texts):
            cached = self._cached(text)
            if cached is None:
                missing.append(text)
            else:
                resolved[text] = cached
        for text, vector in zip(missing, self._fetch(missing)):
            self._store(text, vector)
            resolved[text] = vector
        return [resolved[text] for text in texts]

    def _fetch(self, texts: list[str]) -> list[np.ndarray]:
        if not texts:
            return []
        if isinstance(self.client, BatchEmbeddingClient):
            vectors = self.client.embed_many(
                model=self.model,
                inputs=texts,
                expected_dimension=EMBEDDING_DIMENSION,
            )
        else:
            vectors = [
                self.client.embed(
                    model=self.model,
                    input=text,
                    truncate=True,
                    keep_alive="30m",
                    expected_dimension=EMBEDDING_DIMENSION,
                )
                for text in texts
            ]
        return [_frozen_vector(vector) for vector in vectors]

    def _cached(self, text: str) -> np.ndarray | None:
        vector = self._cache.get(text)
        if vector is not None:
            self._cache.move_to_end(text)
        return vector

    def _store(self, text: str, vector: np.ndarray) -> None:
        if self.cache_size <= 0:
            return
        self._cache[text] = vector
        self._cache.move_to_end(text)
        while len(self._cache) > self.cache_size:
            _ = self._cache.popitem(last=False)


def _frozen_vector(vector: list[float]) -> np.ndarray:
    """캐시가 같은 배열을 여러 기억에 나눠 주므로 읽기 전용으로 만든다."""
    array = np.asarray(vector, dtype=np.float32)
    array.flags.writeable = False
    return array
