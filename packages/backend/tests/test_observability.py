import datetime

from world.engine import SimulationStepObservability, SimulationStepResult
from world.observability import DashboardEventBuffer


def _result(*, minute: int, reply: str = "") -> SimulationStepResult:
    return SimulationStepResult(
        now=datetime.datetime(2026, 8, 24, 9, minute),
        speaker_name="Jiho",
        trace={"parse_success": True, "raw_response": "provider payload"},
        reply=reply,
        silent_reason="" if reply else "no_reaction",
        parse_failure=False,
        observability=SimulationStepObservability(
            thought="상대의 의도를 살핀다.",
            model_thought="대화를 이어갈지 판단한다.",
            self_critique="성급하게 결론 내리지 않는다.",
            decision_reason="지금은 듣는 편이 자연스럽다.",
            action_summary="continue_current_plan",
            decision_process={"action": {"speak_decision": bool(reply)}},
        ),
    )


def test_dashboard_event_buffer_is_bounded_and_cursor_resumable() -> None:
    events = DashboardEventBuffer(capacity=2)
    for turn in range(1, 4):
        events.append(
            turn=turn,
            agent_id="Jiho",
            agent_name="Jiho Park",
            result=_result(minute=turn, reply=f"reply-{turn}"),
        )

    snapshot = events.snapshot(after_sequence=1, limit=10)

    assert [event.sequence for event in snapshot] == [2, 3]
    assert snapshot[-1].reply == "reply-3"
    assert events.latest_sequence == 3


def test_dashboard_event_buffer_preserves_structured_observability() -> None:
    events = DashboardEventBuffer()

    event = events.append(
        turn=7,
        agent_id="Jiho",
        agent_name="Jiho Park",
        result=_result(minute=7),
    )

    assert event.thought == "상대의 의도를 살핀다."
    assert event.self_critique == "성급하게 결론 내리지 않는다."
    assert event.decision_process["action"] == {"speak_decision": False}
    assert event.silent_reason == "no_reaction"
