from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from llm.clients.litellm_client import LiteLlmClientError
from llm.clients.provider_factory import build_provider_client
from llm.clients.response_cache import (
    CachingProviderClient,
    ResponseCache,
    parse_cache_mode,
)
from llm.clients.types import LlmGenerateOptions


class FakeInner:
    default_generate_model = "m-gen"
    default_embedding_model = "m-emb"
    reasoning_effort = None

    def __init__(self) -> None:
        self.generate_calls = 0
        self.embed_inputs: list[list[str]] = []

    def generate(self, *, prompt, system=None, options=None, format_json=False, model=None):
        self.generate_calls += 1
        return f"answer-{self.generate_calls}:{prompt}"

    def embed_many(self, *, model=None, inputs, expected_dimension=None):
        self.embed_inputs.append(list(inputs))
        return [[float(len(t)), 1.0] for t in inputs]


def make(tmp_path: Path, mode="readwrite"):
    inner = FakeInner()
    cache = ResponseCache(tmp_path / "c.sqlite")
    return inner, cache, CachingProviderClient(inner, cache, mode)


def test_generate_hit_and_miss(tmp_path: Path) -> None:
    inner, _, client = make(tmp_path)
    first = client.generate(prompt="hi", options=LlmGenerateOptions(temperature=0.9))
    second = client.generate(prompt="hi", options=LlmGenerateOptions(temperature=0.9))
    assert first == second
    assert inner.generate_calls == 1
    client.generate(prompt="other")
    assert inner.generate_calls == 2


def test_key_changes_with_options(tmp_path: Path) -> None:
    inner, _, client = make(tmp_path)
    client.generate(prompt="p")
    client.generate(prompt="p", options=LlmGenerateOptions(temperature=0.5))
    client.generate(prompt="p", options=LlmGenerateOptions(num_predict=10))
    client.generate(prompt="p", format_json=True)
    client.generate(prompt="p", system="s")
    client.generate(prompt="p", model="other-model")
    assert inner.generate_calls == 6


def test_replay_miss_raises(tmp_path: Path) -> None:
    _, cache, _ = make(tmp_path)
    replay = CachingProviderClient(FakeInner(), cache, "replay")
    with pytest.raises(LiteLlmClientError):
        replay.generate(prompt="never seen")
    with pytest.raises(RuntimeError):
        replay.embed(input="never seen")


def test_replay_hit_after_record(tmp_path: Path) -> None:
    inner, cache, client = make(tmp_path)
    recorded = client.generate(prompt="x")
    replay = CachingProviderClient(FakeInner(), cache, "replay")
    assert replay.generate(prompt="x") == recorded


def test_persists_across_reopen(tmp_path: Path) -> None:
    inner, cache, client = make(tmp_path)
    recorded = client.generate(prompt="x")
    cache.close()
    inner2 = FakeInner()
    client2 = CachingProviderClient(
        inner2, ResponseCache(tmp_path / "c.sqlite"), "readwrite"
    )
    assert client2.generate(prompt="x") == recorded
    assert inner2.generate_calls == 0


def test_embed_many_partial_hit_requests_only_missing(tmp_path: Path) -> None:
    inner, _, client = make(tmp_path)
    client.embed_many(inputs=["aa", "bbb"])
    result = client.embed_many(inputs=["bbb", "c", "aa", "dddd"])
    assert inner.embed_inputs[-1] == ["c", "dddd"]
    assert result == [[3.0, 1.0], [1.0, 1.0], [2.0, 1.0], [4.0, 1.0]]
    client.embed_many(inputs=["c", "dddd"])
    assert len(inner.embed_inputs) == 2


def test_off_mode_delegates(tmp_path: Path) -> None:
    inner, _, client = make(tmp_path, "off")
    client.generate(prompt="p")
    client.generate(prompt="p")
    assert inner.generate_calls == 2


def test_concurrent_writes(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "c.sqlite")

    def work(i: int) -> None:
        for j in range(20):
            cache.put(f"k{i}-{j}", f"v{i}-{j}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(8)))
    assert all(cache.get(f"k{i}-{j}") == f"v{i}-{j}" for i in range(8) for j in range(20))


def test_factory_wraps_only_when_path_set(tmp_path: Path) -> None:
    common = dict(timeout_seconds=1.0, generation_model="a", embedding_model="b")
    assert not isinstance(
        build_provider_client(**common, cache_path=""), CachingProviderClient
    )
    assert isinstance(
        build_provider_client(**common, cache_path=str(tmp_path / "f.sqlite")),
        CachingProviderClient,
    )
    assert not isinstance(
        build_provider_client(
            **common, cache_path=str(tmp_path / "g.sqlite"), cache_mode="off"
        ),
        CachingProviderClient,
    )


def test_parse_cache_mode_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        parse_cache_mode("bogus")
