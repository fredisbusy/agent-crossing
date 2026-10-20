import json
import os
import subprocess
import sys
from pathlib import Path


def _load_settings_with_env(env: dict[str, str]) -> dict[str, str]:
    script = """
import json
import settings

print(json.dumps({
    "LLM_BACKEND": settings.LLM_BACKEND,
    "LLM_BASE_URL": settings.LLM_BASE_URL,
    "LLM_MODEL": settings.LLM_MODEL,
    "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
    "LLM_API_KEY": settings.LLM_API_KEY,
}))
"""
    process_env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "LLM_BACKEND",
            "LLM_BASE_URL",
            "LLM_MODEL",
            "EMBEDDING_MODEL",
            "LLM_API_KEY",
            "GOOGLE_AI_STUDIO_API_KEY",
        }
    }
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    existing_pythonpath = process_env.get("PYTHONPATH", "")
    process_env["PYTHONPATH"] = (
        f"{src_path}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else src_path
    )
    process_env.update(env)
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        env=process_env,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_settings_ollama_backend_uses_fredly_gateway() -> None:
    settings_payload = _load_settings_with_env({"LLM_BACKEND": "ollama"})

    assert settings_payload == {
        "LLM_BACKEND": "ollama",
        "LLM_BASE_URL": "https://model.fredly.dev",
        "LLM_MODEL": "ollama_chat/qwen2.5:7b-instruct",
        "EMBEDDING_MODEL": "ollama/bge-m3",
        "LLM_API_KEY": "",
    }


def test_settings_google_backend_uses_gemini_model_and_api_key() -> None:
    settings_payload = _load_settings_with_env(
        {
            "LLM_BACKEND": "google_ai_studio",
            "GOOGLE_AI_STUDIO_API_KEY": "test-google-key",
        }
    )

    assert settings_payload == {
        "LLM_BACKEND": "google_ai_studio",
        "LLM_BASE_URL": "https://generativelanguage.googleapis.com/v1beta",
        "LLM_MODEL": "gemini/gemini-2.5-flash-lite",
        "EMBEDDING_MODEL": "gemini/gemini-embedding-001",
        "LLM_API_KEY": "test-google-key",
    }
