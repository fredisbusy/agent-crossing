from typing import Protocol

from settings import LLM_NUM_RETRIES, LLM_RESPONSE_CACHE, LLM_RESPONSE_CACHE_MODE

from .litellm_client import LiteLlmClient
from .local_embedding import LocalEmbeddingClient, is_local_embedding_model
from .response_cache import CachingProviderClient, ResponseCache, parse_cache_mode
from .types import LlmGenerateOptions


class ProviderClient(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
    ) -> str: ...

    def embed(
        self,
        *,
        model: str | None = None,
        input: str,
        truncate: bool = True,
        keep_alive: str = "30m",
        expected_dimension: int | None = None,
    ) -> list[float]: ...


def build_provider_client(
    *,
    timeout_seconds: float,
    generation_model: str,
    embedding_model: str,
    base_url: str | None = None,
    api_key: str | None = None,
    embedding_base_url: str | None = None,
    embedding_api_key: str | None = None,
    reasoning_effort: str | None = None,
    num_retries: int = LLM_NUM_RETRIES,
    cache_path: str | None = LLM_RESPONSE_CACHE,
    cache_mode: str = LLM_RESPONSE_CACHE_MODE,
) -> ProviderClient:
    client = LiteLlmClient(
        base_url=base_url,
        api_key=api_key,
        embedding_base_url=embedding_base_url,
        embedding_api_key=embedding_api_key,
        reasoning_effort=reasoning_effort,
        timeout_seconds=timeout_seconds,
        default_generate_model=generation_model,
        default_embedding_model=embedding_model,
        num_retries=num_retries,
    )
    provider: ProviderClient = client
    if is_local_embedding_model(embedding_model):
        provider = LocalEmbeddingClient(client, embedding_model)
    mode = parse_cache_mode(cache_mode)
    if not cache_path or mode == "off":
        return provider
    return CachingProviderClient(provider, ResponseCache(cache_path), mode)


__all__ = [
    "ProviderClient",
    "build_provider_client",
]
