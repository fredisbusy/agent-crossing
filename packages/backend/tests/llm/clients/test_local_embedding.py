import numpy as np
import pytest

from llm.clients import LocalEmbeddingClient
from llm.clients.litellm_client import LiteLlmClient, LiteLlmClientError
from llm.clients.provider_factory import build_provider_client


class _Inner:
    default_generate_model = "gen-model"

    def generate(self, *, prompt: str, **_: object) -> str:
        return f"re:{prompt}"


class _FakeModel:
    def __init__(self, dimension: int) -> None:
        self.dimension = dimension
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str], **_: object) -> np.ndarray:
        self.calls.append(texts)
        return np.ones((len(texts), self.dimension), dtype=np.float32)


def _client(dimension: int) -> tuple[LocalEmbeddingClient, _FakeModel]:
    client = LocalEmbeddingClient(_Inner(), "local/BAAI/bge-m3")
    model = _FakeModel(dimension)
    client._model = model
    return client, model


def test_embeds_locally_and_delegates_generation() -> None:
    client, model = _client(4)

    vectors = client.embed_many(inputs=["a", "b"], expected_dimension=4)

    assert vectors == [[1.0] * 4, [1.0] * 4] and model.calls == [["a", "b"]]
    assert client.embed(input="c", expected_dimension=4) == [1.0] * 4
    assert client.embed_many(inputs=[]) == []
    assert client.generate(prompt="hi") == "re:hi"
    assert client.default_generate_model == "gen-model"


def test_rejects_wrong_dimension() -> None:
    client, _ = _client(3)

    with pytest.raises(LiteLlmClientError):
        client.embed_many(inputs=["a"], expected_dimension=4)


def test_factory_wraps_only_local_embedding_models() -> None:
    local = build_provider_client(
        timeout_seconds=4.0,
        generation_model="openai/some-model",
        embedding_model="local/BAAI/bge-m3",
        cache_path=None,
    )
    remote = build_provider_client(
        timeout_seconds=4.0,
        generation_model="openai/some-model",
        embedding_model="gemini/gemini-embedding-001",
        cache_path=None,
    )

    assert isinstance(local, LocalEmbeddingClient)
    assert isinstance(remote, LiteLlmClient)


def test_model_failures_surface_as_client_errors() -> None:
    class _Broken:
        def encode(self, texts: list[str], **_: object) -> np.ndarray:
            raise OSError("model files missing")

    client = LocalEmbeddingClient(_Inner(), "local/BAAI/bge-m3")
    client._model = _Broken()

    with pytest.raises(LiteLlmClientError, match="model files missing"):
        client.embed_many(inputs=["a"])
