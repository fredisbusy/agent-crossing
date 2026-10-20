from llm.clients.litellm_client import LiteLlmClient
from llm.clients.provider_factory import build_provider_client


def test_build_provider_client_returns_litellm_client() -> None:
    client = build_provider_client(
        timeout_seconds=4.0,
        generation_model="ollama_chat/qwen2.5:7b-instruct",
        embedding_model="ollama/bge-m3",
        base_url="https://model.fredly.dev",
        api_key="test-key",
    )

    assert isinstance(client, LiteLlmClient)
    assert client.base_url == "https://model.fredly.dev"
    assert client.api_key == "test-key"


def test_build_provider_client_supports_google_model_names() -> None:
    client = build_provider_client(
        timeout_seconds=4.0,
        generation_model="gemini/gemini-2.5-flash-lite",
        embedding_model="gemini/gemini-embedding-001",
        base_url="https://generativelanguage.googleapis.com",
        api_key="test-key",
    )

    assert isinstance(client, LiteLlmClient)
    assert client.base_url == "https://generativelanguage.googleapis.com"
    assert client.api_key == "test-key"
