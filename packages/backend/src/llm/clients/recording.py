"""LLM 호출을 한 건씩 기록하는 클라이언트 (실측용 governance trace, AGENTS.md §9).

호출 결과는 바꾸지 않는다. 기록은 `sink`로만 나가고 도메인 상태에 섞이지 않는다.
"""

import threading
import time
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .types import LlmGenerateOptions


class CallRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    op: Literal["generate", "embed"]
    label: str
    """호출 시점에 붙인 표지(예: 게임 시각)."""
    seconds: float
    thread: str
    concurrent: int
    """이 호출이 시작될 때 진행 중이던 호출 수(자신 포함)."""
    prompt: str = ""
    response: str = ""
    format_json: bool = False
    input_count: int = 0
    """임베딩 호출의 문장 수."""
    error: str | None = None


class RecordingProviderClient:
    """`ProviderClient`를 감싸 호출마다 `CallRecord`를 `sink`에 넘긴다."""

    def __init__(self, inner: Any, sink: Callable[[CallRecord], None]) -> None:
        self._inner = inner
        self._sink = sink
        self._lock = threading.Lock()
        self._in_flight = 0
        self.label = ""
        """다음 호출들에 붙일 표지. 실행 쪽이 틱마다 갱신한다."""

    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: LlmGenerateOptions | None = None,
        format_json: bool = False,
        model: str | None = None,
    ) -> str:
        started, concurrent = self._enter()
        response = ""
        error: str | None = None
        try:
            response = str(
                self._inner.generate(
                    prompt=prompt,
                    system=system,
                    options=options,
                    format_json=format_json,
                    **({} if model is None else {"model": model}),
                )
            )
            return response
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self._leave(
                CallRecord(
                    op="generate",
                    label=self.label,
                    seconds=time.perf_counter() - started,
                    thread=threading.current_thread().name,
                    concurrent=concurrent,
                    prompt=prompt,
                    response=response,
                    format_json=format_json,
                    error=error,
                )
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
        _ = (truncate, keep_alive)
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
        started, concurrent = self._enter()
        error: str | None = None
        try:
            vectors: list[list[float]] = self._inner.embed_many(
                model=model, inputs=inputs, expected_dimension=expected_dimension
            )
            return vectors
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self._leave(
                CallRecord(
                    op="embed",
                    label=self.label,
                    seconds=time.perf_counter() - started,
                    thread=threading.current_thread().name,
                    concurrent=concurrent,
                    input_count=len(inputs),
                    error=error,
                )
            )

    def _enter(self) -> tuple[float, int]:
        with self._lock:
            self._in_flight += 1
            return time.perf_counter(), self._in_flight

    def _leave(self, record: CallRecord) -> None:
        with self._lock:
            self._in_flight -= 1
            self._sink(record)


__all__ = ["CallRecord", "RecordingProviderClient"]
