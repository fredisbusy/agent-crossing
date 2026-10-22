import json
import re
from dataclasses import dataclass, replace
from typing import Protocol, cast, runtime_checkable

from .clients.types import (
    JsonObject,
    LlmGenerateOptions,
)
from .prompt_builders import (
    build_importance_batch_scoring_prompt,
    build_importance_scoring_prompt,
)


def clamp_importance(value: int) -> int:
    return max(1, min(10, value))


def _parse_json_object(text: str) -> JsonObject | None:
    try:
        parsed = cast(object, json.loads(text))
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(parsed, dict):
            return cast(JsonObject, parsed)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return None

    try:
        nested = cast(object, json.loads(match.group(0)))
    except json.JSONDecodeError:
        return None

    return cast(JsonObject, nested) if isinstance(nested, dict) else None


def parse_importance_value(text: str, fallback_importance: int) -> int:
    payload = _parse_json_object(text)
    if payload is None:
        return fallback_importance

    raw_importance = payload.get("importance")

    if isinstance(raw_importance, bool):
        return fallback_importance

    if isinstance(raw_importance, int):
        return clamp_importance(raw_importance)

    if isinstance(raw_importance, float):
        return clamp_importance(round(raw_importance))

    if isinstance(raw_importance, str):
        stripped = raw_importance.strip()
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            return clamp_importance(int(stripped))

    return fallback_importance


def _coerce_importance(raw: object, fallback_importance: int) -> int:
    if isinstance(raw, bool):
        return fallback_importance
    if isinstance(raw, int):
        return clamp_importance(raw)
    if isinstance(raw, float):
        return clamp_importance(round(raw))
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            return clamp_importance(int(stripped))
    return fallback_importance


def parse_importance_values(
    text: str, count: int, fallback_importance: int
) -> list[int]:
    """배치 응답({"importances": [...]})을 파싱한다. 개수가 다르거나 깨지면 전부 fallback."""
    fallback = [fallback_importance] * count
    payload = _parse_json_object(text)
    if payload is None:
        return fallback
    raw_values = payload.get("importances")
    if not isinstance(raw_values, list):
        return fallback
    items = cast(list[object], raw_values)
    if len(items) != count:
        return fallback
    return [_coerce_importance(item, fallback_importance) for item in items]


@dataclass(frozen=True)
class ImportanceScoringContext:
    observation: str
    agent_name: str
    identity_stable_set: list[str]
    current_plan: str | None = None


class ImportanceScorer(Protocol):
    def score(self, context: ImportanceScoringContext) -> int: ...


@runtime_checkable
class BatchImportanceScorer(Protocol):
    def score_many(self, contexts: list[ImportanceScoringContext]) -> list[int]: ...


class ImportanceGenerateClient(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        options: LlmGenerateOptions | None = None,
        system: str | None = None,
        format_json: bool = False,
    ) -> str: ...


SINGLE_NUM_PREDICT = 16
BATCH_BASE_NUM_PREDICT = 24
BATCH_NUM_PREDICT_PER_ITEM = 4


class LlmImportanceScorer:
    def __init__(
        self,
        client: ImportanceGenerateClient,
        fallback_importance: int = 3,
        options: LlmGenerateOptions | None = None,
    ) -> None:
        self.client: ImportanceGenerateClient = client
        self.fallback_importance: int = clamp_importance(fallback_importance)
        self.options: LlmGenerateOptions = options or LlmGenerateOptions(
            num_predict=SINGLE_NUM_PREDICT
        )
        self._explicit_options: bool = options is not None

    def score(self, context: ImportanceScoringContext) -> int:
        prompt = self._build_prompt(context)

        try:
            response = self.client.generate(
                prompt=prompt,
                options=self.options,
                format_json=True,
            )
        except (RuntimeError, TimeoutError, ValueError):
            return self.fallback_importance

        return parse_importance_value(response, self.fallback_importance)

    def score_many(self, contexts: list[ImportanceScoringContext]) -> list[int]:
        """관찰 여러 개를 한 번의 LLM 호출로 채점한다. 순서를 보존한다."""
        if not contexts:
            return []
        if len(contexts) == 1:
            return [self.score(contexts[0])]

        first = contexts[0]
        prompt = build_importance_batch_scoring_prompt(
            agent_name=first.agent_name,
            identity_stable_set=first.identity_stable_set,
            current_plan=first.current_plan,
            observations=[context.observation for context in contexts],
        )
        options = self.options
        if not self._explicit_options:
            options = replace(
                options,
                num_predict=BATCH_BASE_NUM_PREDICT
                + BATCH_NUM_PREDICT_PER_ITEM * len(contexts),
            )
        try:
            response = self.client.generate(
                prompt=prompt, options=options, format_json=True
            )
        except (RuntimeError, TimeoutError, ValueError):
            return [self.fallback_importance] * len(contexts)
        return parse_importance_values(
            response, len(contexts), self.fallback_importance
        )

    @staticmethod
    def _build_prompt(context: ImportanceScoringContext) -> str:
        return build_importance_scoring_prompt(
            agent_name=context.agent_name,
            identity_stable_set=context.identity_stable_set,
            current_plan=context.current_plan,
            observation=context.observation,
        )
