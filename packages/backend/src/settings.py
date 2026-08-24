"""Backend-wide configuration constants."""

import os
from pathlib import Path
from typing import Final, Literal, cast

from dotenv import load_dotenv

_ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_ROOT_ENV_PATH)

EMBEDDING_DIMENSION: Final[int] = 1024

_raw_llm_backend = os.getenv("LLM_BACKEND", "ollama")
if _raw_llm_backend not in {"ollama", "google_ai_studio"}:
    _raw_llm_backend = "ollama"
LLM_BACKEND: Final[Literal["ollama", "google_ai_studio"]] = cast(
    Literal["ollama", "google_ai_studio"],
    _raw_llm_backend,
)

_default_base_url = (
    "https://model.byfred.io"
    if LLM_BACKEND == "ollama"
    else "https://generativelanguage.googleapis.com/v1beta"
)
_default_llm_model = (
    "ollama_chat/qwen3.8:27b-mlx"
    if LLM_BACKEND == "ollama"
    else "gemini/gemini-2.5-flash-lite"
)
_default_embedding_model = (
    "ollama/bge-m3"
    if LLM_BACKEND == "ollama"
    else "gemini/gemini-embedding-001"
)

LLM_BASE_URL: Final[str] = os.getenv("LLM_BASE_URL", _default_base_url)
LLM_MODEL: Final[str] = os.getenv("LLM_MODEL", _default_llm_model)
EMBEDDING_MODEL: Final[str] = os.getenv("EMBEDDING_MODEL", _default_embedding_model)
LLM_TIMEOUT_SECONDS: Final[float] = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
GOOGLE_AI_STUDIO_API_KEY: Final[str] = os.getenv("GOOGLE_AI_STUDIO_API_KEY", "")
LLM_API_KEY: Final[str] = os.getenv(
    "LLM_API_KEY",
    GOOGLE_AI_STUDIO_API_KEY if LLM_BACKEND == "google_ai_studio" else "",
)
WORLD_TICK_INTERVAL_SECONDS: Final[float] = float(
    os.getenv("WORLD_TICK_INTERVAL_SECONDS", "1.0")
)
WORLD_COGNITIVE_TIME_STEP_SECONDS: Final[int] = int(
    os.getenv("WORLD_COGNITIVE_TIME_STEP_SECONDS", "30")
)
