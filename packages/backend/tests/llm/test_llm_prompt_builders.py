import datetime

import numpy as np
from agents.memory.memory_object import MemoryObject, NodeType
from agents.planning.models import DayPlanItem, HourlyPlanItem
from agents.reaction import DialogueArc
from llm.prompt_builders import (
    build_day_plan_prompt,
    build_hourly_plan_prompt,
    build_minute_plan_prompt,
    build_reaction_intent_prompt,
    build_reaction_utterance_prompt,
    build_salient_questions_prompt,
)
from llm_gateway_helpers import (
    build_reaction_input,
)


def test_reaction_prompt_includes_concise_utterance_constraint() -> None:
    request = build_reaction_input(dialogue_history=[])
    prompt = build_reaction_utterance_prompt(
        agent_identity=request.agent_identity,
        current_time=request.current_time,
        observation_content=request.observation_content,
        dialogue_history=request.dialogue_history,
        profile=request.profile,
        retrieved_memories=request.retrieved_memories,
        intent_reason="react",
        intent_thought="",
        intent_critique="",
        dialogue_arc=None,
    )

    assert "Keep utterance concise and short" in prompt
    assert "80 Korean characters" in prompt


def test_reaction_prompt_includes_few_shot_and_reflection_anchor() -> None:
    reflection_memory = MemoryObject(
        id=1,
        node_type=NodeType.REFLECTION,
        citations=None,
        content="상대의 요청이 원칙과 충돌하면 정중히 거절한다.",
        created_at=datetime.datetime(2026, 2, 27, 13, 0, 0),
        last_accessed_at=datetime.datetime(2026, 2, 27, 13, 0, 0),
        importance=8,
        embedding=np.asarray([0.1, 0.2], dtype=np.float32),
    )

    request = build_reaction_input(
        dialogue_history=[],
        retrieved_memories=[reflection_memory],
    )
    prompt = build_reaction_utterance_prompt(
        agent_identity=request.agent_identity,
        current_time=request.current_time,
        observation_content=request.observation_content,
        dialogue_history=request.dialogue_history,
        profile=request.profile,
        retrieved_memories=request.retrieved_memories,
        intent_reason="react",
        intent_thought="",
        intent_critique="",
        dialogue_arc=None,
    )

    assert "[Identity Anchor - highest priority]" in prompt
    assert "Few-shot calibration examples" in prompt
    assert "polite refusal" in prompt


def test_reaction_intent_prompt_requests_intent_shape() -> None:
    request = build_reaction_input(dialogue_history=[])
    prompt = build_reaction_intent_prompt(
        agent_identity=request.agent_identity,
        current_time=request.current_time,
        observation_content=request.observation_content,
        dialogue_history=request.dialogue_history,
        profile=request.profile,
        retrieved_memories=request.retrieved_memories,
        dialogue_arc=None,
    )

    assert "Should [Jiho Park] react to the observation right now?" in prompt
    assert '"should_react": <boolean>' in prompt


def test_reaction_prompt_includes_short_dialogue_arc_guidance() -> None:
    request = build_reaction_input(dialogue_history=[("안녕", "안녕")])
    prompt = build_reaction_utterance_prompt(
        agent_identity=request.agent_identity,
        current_time=request.current_time,
        observation_content=request.observation_content,
        dialogue_history=request.dialogue_history,
        profile=request.profile,
        retrieved_memories=request.retrieved_memories,
        intent_reason="respond",
        intent_thought="",
        intent_critique="",
        dialogue_arc=DialogueArc(
            goal="Ask briefly about the decaf blend and wrap up naturally.",
            turns_taken=4,
            target_turns=5,
            remaining_turns=1,
            phase="closing",
            should_wrap_up=True,
        ),
    )

    assert "[Short Conversation Arc]" in prompt
    assert (
        "Conversation goal: Ask briefly about the decaf blend and wrap up naturally."
        in prompt
    )
    assert "phase=closing" in prompt
    assert "Do not introduce a new major topic" in prompt
    assert "set end_dialogue=true" in prompt


def test_day_plan_prompt_contains_persona_and_json_shape() -> None:
    prompt = build_day_plan_prompt(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background=(
            "Eddy Lin is a student at Oak Hill College studying music theory and composition."
        ),
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary=(
            "woke up and completed the morning routine at 7:00 am, [...] got ready to sleep around 10 pm."
        ),
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert "Name: Eddy Lin (age: 19)" in prompt
    assert "Innate traits: friendly, outgoing, hospitable" in prompt
    assert "Today is Friday February 13 2026" in prompt
    assert "Draft Eddy Lin's structured day plan." in prompt
    assert "Use the same calendar date as `Today is ...`" in prompt
    assert "Framing reference (for style, not output format):" in prompt
    assert "Return strict JSON only with this exact shape and no extra text:" in prompt
    assert '"items": [' in prompt
    assert '"start_time": "<ISO-8601 datetime>"' in prompt
    assert '"end_time": "<ISO-8601 datetime later than start_time>"' in prompt


def test_hourly_plan_prompt_contains_context_and_json_shape() -> None:
    prompt = build_hourly_plan_prompt(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 45, 0),
        day_plan_item=DayPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 8, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 10, 0, 0),
            location="Town > Home > Kitchen",
            action_content="Review composition notes and plan",
        ),
    )

    assert (
        "Decompose the active day-plan block into a chronological hourly plan for the near future."
        in prompt
    )
    assert "Friday February 13 2026 at 8:45 AM" in prompt
    assert "Planning date (must stay consistent): 2026-02-13" in prompt
    assert "Prefer 30-180 minute blocks" in prompt
    assert "Do not restate or regenerate the entire day plan." in prompt
    assert "Review composition notes and plan" in prompt
    assert "Attend class" not in prompt
    assert "Study alone" not in prompt
    assert "Return strict JSON only with this exact shape and no extra text:" in prompt
    assert "'items': [" not in prompt
    assert '"items": [' in prompt
    assert '"end_time": "<ISO-8601 datetime later than start_time>"' in prompt


def test_minute_plan_prompt_contains_context_and_json_shape() -> None:
    prompt = build_minute_plan_prompt(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 12, 20, 0),
        hourly_plan_item=HourlyPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 12, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 13, 0, 0),
            location="Town > Home > Study",
            action_content="Draft project outline",
        ),
    )

    assert "Generate an executable minute plan for the current phase." in prompt
    assert "Friday February 13 2026 at 12:20 PM" in prompt
    assert "Planning date (must stay consistent): 2026-02-13" in prompt
    assert "Do not simply copy hourly-plan summaries" in prompt
    assert "Draft project outline" in prompt
    assert "Take lunch break" not in prompt
    assert "Resume focused writing" not in prompt
    assert "end_time" in prompt
    assert "Return strict JSON only with this exact shape and no extra text:" in prompt
    assert '"end_time": "<ISO-8601 datetime 5-15 minutes after start_time>"' in prompt


def test_salient_prompt_uses_strict_json_contract_line() -> None:
    memory = MemoryObject(
        id=1,
        node_type=NodeType.OBSERVATION,
        citations=None,
        content="Met classmate at the cafe.",
        created_at=datetime.datetime(2026, 2, 27, 10, 0, 0),
        last_accessed_at=datetime.datetime(2026, 2, 27, 10, 0, 0),
        importance=4,
        embedding=np.asarray([0.1, 0.2], dtype=np.float32),
    )
    prompt = build_salient_questions_prompt(agent_name="Eddy Lin", memories=[memory])

    assert "Return strict JSON only with this exact shape and no extra text:" in prompt
    assert '"questions": [' in prompt
