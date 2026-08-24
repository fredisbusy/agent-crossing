from typing import Protocol

from .litellm_client import LiteLlmClient
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
    timeout_seconds: float | None,
    generation_model: str,
    embedding_model: str,
    base_url: str | None = None,
    api_key: str | None = None,
) -> ProviderClient:
    return LiteLlmClient(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        default_generate_model=generation_model,
        default_embedding_model=embedding_model,
    )


__all__ = [
    "ProviderClient",
    "build_provider_client",
]
