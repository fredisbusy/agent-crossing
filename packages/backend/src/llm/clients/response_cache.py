"""LLM 응답 기록·재생 캐시.

같은 시드 + 같은 LLM 응답 캐시 -> 같은 결과 (AGENTS.md §10-4, SPEC §14).
temperature>0이라도 같은 프롬프트·옵션이면 기록된 응답을 그대로 재생한다.
이것이 재현 실행의 의도이며, 다양한 표본이 필요하면 캐시를 끄거나 경로를 바꾼다.
"""

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Literal

from settings import EMBEDDING_DIMENSION

from .litellm_client import LiteLlmClientError
from .types import LlmGenerateOptions

CacheMode = Literal["readwrite", "replay", "off"]
CACHE_MODES: tuple[CacheMode, ...] = ("readwrite", "replay", "off")


def parse_cache_mode(value: str) -> CacheMode:
    normalized = value.strip().lower()
    for mode in CACHE_MODES:
        if mode == normalized:
            return mode
    raise ValueError(f"Unknown LLM response cache mode: {value!r}")


def _hash(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_key(
    *,
    model: str,
    system: str | None,
    prompt: str,
    options: LlmGenerateOptions,
    format_json: bool,
    reasoning_effort: str | None,
    base_url: str | None = None,
) -> str:
    return _hash(
        {
            "kind": "generate",
            "model": model,
            "system": system,
            "prompt": prompt,
            "temperature": options.temperature,
            "top_p": options.top_p,
            "max_tokens": options.num_predict,
            "format_json": format_json,
            "repeat_penalty": options.repeat_penalty,
            "presence_penalty": options.presence_penalty,
            "frequency_penalty": options.frequency_penalty,
            "reasoning_effort": reasoning_effort,
            "base_url": base_url,
        }
    )


def embedding_key(
    *, model: str, dimensions: int, text: str, base_url: str | None = None
) -> str:
    return _hash(
        {
            "kind": "embed",
            "model": model,
            "dimensions": dimensions,
            "text": text,
            "base_url": base_url,
        }
    )


class ResponseCache:
    """sqlite 기반 키-값 저장소. 여러 스레드가 동시에 불러도 안전하다."""

    def __init__(self, path: str | Path) -> None:
        target = Path(path)
        if str(target) != ":memory:":
            target.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(target), check_same_thread=False)
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS responses "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self._conn.commit()

    def get(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM responses WHERE key = ?", (key,)
            ).fetchone()
        return None if row is None else str(row[0])

    def put(self, key: str, value: str) -> str:
        """먼저 쓴 값이 이긴다. 실제로 저장된 값을 돌려준다."""
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO responses (key, value) VALUES (?, ?)",
                (key, value),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT value FROM responses WHERE key = ?", (key,)
            ).fetchone()
        return str(row[0])

    def __enter__(self) -> "ResponseCache":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _is_storable(text: str, format_json: bool) -> bool:
    """쓸 수 없는 응답(빈 문자열, JSON을 요구했는데 `{`가 없는 응답)은 고정하지 않는다."""
    if not text.strip():
        return False
    return not (format_json and "{" not in text)


class CachingProviderClient:
    """`ProviderClient`를 감싸 응답을 기록·재생하는 데코레이터.

    - readwrite: 적중하면 반환, 아니면 호출 후 저장한다.
    - replay: 적중하지 않으면 `LiteLlmClientError`를 낸다.
    - off: 그대로 위임한다.

    temperature>0이라도 같은 프롬프트·옵션이면 기록된 응답을 재생한다(재현 실행의 의도).
    """

    def __init__(
        self,
        inner: Any,
        cache: ResponseCache,
        mode: CacheMode = "readwrite",
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._mode = mode

    def _generate_model(self, model: str | None) -> str:
        return model or str(getattr(self._inner, "default_generate_model", ""))

    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
        model: str | None = None,
    ) -> str:
        if self._mode == "off":
            return self._call_generate(prompt, system, options, format_json, model)
        key = generate_key(
            model=self._generate_model(model),
            system=system,
            prompt=prompt,
            options=options or LlmGenerateOptions(),
            format_json=format_json,
            reasoning_effort=getattr(self._inner, "reasoning_effort", None),
            base_url=getattr(self._inner, "base_url", None),
        )
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        if self._mode == "replay":
            raise LiteLlmClientError(f"LLM response cache miss (replay): {key[:12]}")
        text = self._call_generate(prompt, system, options, format_json, model)
        if not _is_storable(text, format_json):
            return text
        return self._cache.put(key, text)

    def _call_generate(
        self,
        prompt: str,
        system: str | None,
        options: LlmGenerateOptions | None,
        format_json: bool,
        model: str | None,
    ) -> str:
        return self._inner.generate(
            prompt=prompt,
            system=system,
            options=options,
            format_json=format_json,
            model=model,
        )

    def embed(
        self,
        *,
        model: str | None = None,
        input: str,
        truncate: bool = True,
        keep_alive: str = "30m",
        expected_dimension: int | None = None,
    ) -> list[float]:
        return self.embed_many(
            model=model, inputs=[input], expected_dimension=expected_dimension
        )[0]

    def embed_many(
        self,
        *,
        model: str | None = None,
        inputs: list[str],
        expected_dimension: int | None = None,
    ) -> list[list[float]]:
        if self._mode == "off":
            return self._inner.embed_many(
                model=model, inputs=inputs, expected_dimension=expected_dimension
            )
        dims = (
            expected_dimension
            if expected_dimension is not None
            else EMBEDDING_DIMENSION
        )
        selected = model or str(getattr(self._inner, "default_embedding_model", ""))
        emb_url = getattr(self._inner, "embedding_base_url", None) or getattr(
            self._inner, "base_url", None
        )
        keys = [
            embedding_key(model=selected, dimensions=dims, text=text, base_url=emb_url)
            for text in inputs
        ]
        found: dict[int, list[float]] = {}
        missing: list[int] = []
        for index, key in enumerate(keys):
            raw = self._cache.get(key)
            if raw is None:
                missing.append(index)
            else:
                found[index] = [float(v) for v in json.loads(raw)]
        if missing:
            if self._mode == "replay":
                raise LiteLlmClientError(
                    f"LLM embedding cache miss (replay): {len(missing)} text(s)"
                )
            fetched: list[list[float]] = self._inner.embed_many(
                model=model,
                inputs=[inputs[i] for i in missing],
                expected_dimension=expected_dimension,
            )
            for index, vector in zip(missing, fetched, strict=True):
                stored = self._cache.put(keys[index], json.dumps(vector))
                found[index] = [float(v) for v in json.loads(stored)]
        return [found[i] for i in range(len(inputs))]
