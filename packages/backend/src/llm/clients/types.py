from dataclasses import dataclass
from typing import Literal, TypeAlias

JsonObject: TypeAlias = dict[str, object]

ReasoningEffort: TypeAlias = Literal["none", "low", "medium", "high"]


class LlmGenerationError(RuntimeError):
    """A provider generation failed after the client's recovery policy."""


class LlmOutputTruncatedError(LlmGenerationError):
    """A provider exhausted its output-token budget before finishing."""


class LlmStructuredOutputError(LlmGenerationError):
    """A structured provider response could not satisfy its schema."""


@dataclass(frozen=True)
class LlmGenerateOptions:
    temperature: float = 0.0
    top_p: float = 0.9
    num_predict: int = 80
    repeat_penalty: float | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    """Explicit reasoning budget override.

    Low-frequency, high-stakes calls (day planning, reaction intent) can opt into a
    non-``none`` value here. Left unset, the client falls back to its own heuristic
    (``none`` for structured/JSON output on local Ollama Qwen models, ``low`` otherwise).
    """
    reasoning_effort: ReasoningEffort | None = None
