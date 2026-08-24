import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from llm.guardrails.similarity import (
    SEMANTIC_HARD_BLOCK_THRESHOLD,
    SEMANTIC_SOFT_PENALTY_THRESHOLD,
)
from settings import (
    EMBEDDING_MODEL,
    GOOGLE_AI_STUDIO_API_KEY,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)
from world.runtime import WorldRuntimeConfig, build_world_runtime


@dataclass(frozen=True)
class LoopSimulationConfig:
    agent_persona_names: list[str]
    """시뮬레이션에 참여할 에이전트 persona id 목록."""
    turns: int
    """총 턴 수."""
    base_url: str | None
    """LiteLLM provider server base URL."""
    api_key: str | None
    """LiteLLM provider API key."""
    llm_model: str
    """발화/추론에 사용할 LLM 모델명."""
    embedding_model: str
    """임베딩에 사용할 모델명."""
    timeout_seconds: float
    """LLM 요청 타임아웃(초)."""
    persona_dir: str
    """persona JSON 파일 경로."""
    dialogue_turn_window: int | None = None
    """대화 이력 컨텍스트 윈도우(턴). None이면 전체 이력 사용."""
    dialogue_target_turns: int = 5
    """짧은 대화 아크에서 선호하는 목표 턴 수."""
    language: Literal["ko"] = "ko"
    """시뮬레이션 언어. Agent Crossing은 한국어만 사용한다."""
    fallback_on_empty_reply: bool = False
    """최종 발화가 비었을 때 fallback 문장을 주입할지 여부."""
    suppress_repeated_replies: bool = True
    """최근 발화와 중복되는 발화를 억제할지 여부."""
    repetition_window: int = 4
    """중복 판정 시 비교할 최근 발화 수."""
    turn_time_step_seconds: int = 45
    """한 턴당 시뮬레이션 시간 증가량(초)."""
    log_mode: Literal["basic", "debug"] = "basic"
    """로그 출력 모드. basic은 축약, debug는 원문 포함."""


DEFAULT_CONFIG = LoopSimulationConfig(
    agent_persona_names=["Jiho", "Sujin"],
    turns=10,
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY or GOOGLE_AI_STUDIO_API_KEY,
    llm_model=LLM_MODEL,
    embedding_model=EMBEDDING_MODEL,
    timeout_seconds=LLM_TIMEOUT_SECONDS,
    persona_dir=str(Path(__file__).resolve().parents[1] / "persona"),
)


def _run_simulation(
    *,
    config: LoopSimulationConfig,
) -> None:
    language = config.language
    agent_persona_names = config.agent_persona_names
    if len(agent_persona_names) != 2:
        raise ValueError("This simulation currently supports exactly two agents")

    runtime = build_world_runtime(
        config=WorldRuntimeConfig(
            agent_persona_names=agent_persona_names,
            base_url=config.base_url,
            api_key=config.api_key,
            llm_model=config.llm_model,
            embedding_model=config.embedding_model,
            timeout_seconds=config.timeout_seconds,
            persona_dir=config.persona_dir,
            dialogue_turn_window=config.dialogue_turn_window,
            dialogue_target_turns=config.dialogue_target_turns,
            language=language,
            fallback_on_empty_reply=config.fallback_on_empty_reply,
            suppress_repeated_replies=config.suppress_repeated_replies,
            repetition_window=config.repetition_window,
            turn_time_step_seconds=config.turn_time_step_seconds,
        )
    )

    _print_session_log_header(config=config)

    for turn in range(1, config.turns + 1):
        speaker = runtime.session.agents[(turn - 1) % len(runtime.session.agents)]
        step_result = runtime.step()
        filtered_trace = _format_decision_trace_for_log(
            trace=step_result.trace,
            log_mode=config.log_mode,
        )
        observability = step_result.observability

        _print_log_line(
            turn=turn,
            tag="CRITIQUE_OR_REASON",
            speaker_name=speaker.name,
            message=observability.thought,
        )
        if observability.model_thought:
            _print_log_line(
                turn=turn,
                tag="MODEL_THOUGHT",
                speaker_name=speaker.name,
                message=observability.model_thought,
            )
        if observability.self_critique:
            _print_log_line(
                turn=turn,
                tag="SELF_CRITIQUE",
                speaker_name=speaker.name,
                message=observability.self_critique,
            )
        _print_log_line(
            turn=turn,
            tag="ACTION",
            speaker_name=speaker.name,
            message=observability.action_summary,
        )
        _print_log_json_block(
            turn=turn,
            tag="PROCESS",
            speaker_name=speaker.name,
            payload=observability.decision_process,
        )
        _print_log_json_block(
            turn=turn,
            tag="DECISION_TRACE",
            speaker_name=speaker.name,
            payload=filtered_trace,
        )

        if not step_result.reply:
            silent_reason = step_result.silent_reason or "unknown"
            print(f"[{turn:02d}] [SILENT] {speaker.name} reason={silent_reason}")
            continue

        print(f"{speaker.name}: {step_result.reply}")

    print("\nRecent memories")
    for agent in runtime.agents:
        print(f"\n- {agent.name}")
        memories = agent.memory_service.get_recent_memories(limit=5)
        for memory in memories:
            print(f"  [{memory.node_type.value}] {memory.content}")

    metrics = runtime.metrics()
    print("\nSimulation metrics")
    print(f"- parse_failure_rate={metrics.parse_failure_rate:.3f}")
    print(f"- silent_rate={metrics.silent_rate:.3f}")
    print(f"- semantic_repeat_rate={metrics.semantic_repeat_rate:.3f}")
    print(f"- topic_progress_rate={metrics.topic_progress_rate:.3f}")


def _print_session_log_header(*, config: LoopSimulationConfig) -> None:
    print("Simulation log mode")
    print(f"- mode={config.log_mode}")
    print(f"- llm_model={config.llm_model}")
    print(f"- semantic_hard_threshold={SEMANTIC_HARD_BLOCK_THRESHOLD}")
    print(f"- semantic_soft_threshold={SEMANTIC_SOFT_PENALTY_THRESHOLD}")
    print(f"- dialogue_target_turns={config.dialogue_target_turns}")
    print(f"- suppress_repeated_replies={config.suppress_repeated_replies}")
    print(f"- fallback_on_empty_reply={config.fallback_on_empty_reply}")


def _format_decision_trace_for_log(
    *,
    trace: dict[str, object],
    log_mode: Literal["basic", "debug"],
) -> dict[str, object]:
    constants_to_hide = {"semantic_hard_threshold", "semantic_soft_threshold"}
    empty_optional_fields = {"parse_error", "fallback_reason", "suppress_reason"}
    filtered: dict[str, object] = {}
    for key, value in trace.items():
        if log_mode == "basic" and key == "raw_response":
            continue
        if log_mode == "basic" and key in constants_to_hide:
            continue
        if log_mode == "basic" and key in empty_optional_fields and value == "":
            continue
        filtered[key] = value
    return filtered


def _print_log_line(*, turn: int, tag: str, speaker_name: str, message: str) -> None:
    print(f"[{turn:02d}] [{tag}] {speaker_name}: {message}")


def _print_log_json_block(
    *,
    turn: int,
    tag: str,
    speaker_name: str,
    payload: dict[str, object],
) -> None:
    print(f"[{turn:02d}] [{tag}] {speaker_name}:")
    pretty_payload = json.dumps(payload, ensure_ascii=False, indent=2)
    for line in pretty_payload.splitlines():
        print(f"  {line}")


def main() -> None:
    _run_simulation(config=DEFAULT_CONFIG)


if __name__ == "__main__":
    main()
