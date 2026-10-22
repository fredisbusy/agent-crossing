import numpy as np
from llm.embedding_encoder import EmbeddingEncodingContext, LlmEmbeddingEncoder
from llm.guardrails.similarity import embed_sentences
from settings import EMBEDDING_DIMENSION


def _vector_for(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[len(text) % EMBEDDING_DIMENSION] = 1.0
    return vector


class SingleEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(
        self,
        *,
        model: str | None = None,
        input: str,
        truncate: bool = True,
        keep_alive: str = "30m",
        expected_dimension: int | None = None,
    ) -> list[float]:
        self.calls.append(input)
        return _vector_for(input)


class BatchEmbeddingClient(SingleEmbeddingClient):
    def __init__(self) -> None:
        super().__init__()
        self.batches: list[list[str]] = []

    def embed_many(
        self,
        *,
        model: str | None = None,
        inputs: list[str],
        expected_dimension: int | None = None,
    ) -> list[list[float]]:
        self.batches.append(list(inputs))
        return [_vector_for(text) for text in inputs]


def _contexts(*texts: str) -> list[EmbeddingEncodingContext]:
    return [EmbeddingEncodingContext(text=text) for text in texts]


def test_encode_reuses_cached_embedding_for_same_text() -> None:
    client = SingleEmbeddingClient()
    encoder = LlmEmbeddingEncoder(client=client, model="m")

    first = encoder.encode(EmbeddingEncodingContext(text="철수가 광장에 있다"))
    second = encoder.encode(EmbeddingEncodingContext(text="철수가 광장에 있다"))

    assert client.calls == ["철수가 광장에 있다"]
    assert np.array_equal(first, second)
    assert not first.flags.writeable


def test_encode_many_sends_only_uncached_unique_texts_in_one_batch() -> None:
    client = BatchEmbeddingClient()
    encoder = LlmEmbeddingEncoder(client=client, model="m")
    _ = encoder.encode(EmbeddingEncodingContext(text="a"))

    vectors = encoder.encode_many(_contexts("a", "bb", "bb", "ccc"))

    assert client.batches == [["a"], ["bb", "ccc"]]
    assert client.calls == []
    assert [int(np.argmax(v)) for v in vectors] == [1, 2, 2, 3]


def test_encode_many_falls_back_to_single_calls_without_batch_support() -> None:
    client = SingleEmbeddingClient()
    encoder = LlmEmbeddingEncoder(client=client, model="m")

    _ = encoder.encode_many(_contexts("x", "yy", "x"))

    assert client.calls == ["x", "yy"]


def test_cache_evicts_least_recently_used_text() -> None:
    client = SingleEmbeddingClient()
    encoder = LlmEmbeddingEncoder(client=client, model="m", cache_size=2)

    for text in ["a", "bb", "a", "ccc", "a", "bb"]:
        _ = encoder.encode(EmbeddingEncodingContext(text=text))

    assert client.calls == ["a", "bb", "ccc", "bb"]


def test_cache_hit_survives_eviction_within_same_batch() -> None:
    client = BatchEmbeddingClient()
    encoder = LlmEmbeddingEncoder(client=client, model="m", cache_size=1)
    _ = encoder.encode(EmbeddingEncodingContext(text="a"))

    vectors = encoder.encode_many(_contexts("a", "bb", "ccc"))

    assert [int(np.argmax(v)) for v in vectors] == [1, 2, 3]


def test_embed_sentences_uses_batch_encoder() -> None:
    client = BatchEmbeddingClient()
    encoder = LlmEmbeddingEncoder(client=client, model="m")

    pairs = embed_sentences(sentences=["안녕", "반가워"], embedding_encoder=encoder)

    assert [sentence for sentence, _ in pairs] == ["안녕", "반가워"]
    assert client.batches == [["안녕", "반가워"]]
