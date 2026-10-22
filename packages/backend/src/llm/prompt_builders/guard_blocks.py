from collections.abc import Sequence
from typing import Literal

from ..template_loader import render_template
from .shapes import REACTION_UTTERANCE_JSON_SHAPE


def language_system_prompt(language: Literal["ko", "en"]) -> str:
    if language == "ko":
        return render_template("language_system_ko.md").strip()

    return render_template("language_system_en.md").strip()


def build_overlap_guard_block(
    *,
    recent_sentences: Sequence[str],
    previous_candidate: str,
) -> str:
    recent_dialogue_lines = "\n".join(
        f"- {index}. {sentence}"
        for index, sentence in enumerate(recent_sentences, start=1)
    )
    return render_template(
        "overlap_guard.md",
        previous_candidate=previous_candidate,
        recent_dialogue_lines=recent_dialogue_lines,
        json_shape=REACTION_UTTERANCE_JSON_SHAPE,
    ).strip()


def build_semantic_guard_block(
    *,
    semantic_history: Sequence[str],
    previous_candidate: str,
    max_similarity: float,
    trigger: str,
    soft_threshold: float,
    hard_threshold: float,
) -> str:
    level = "hard block" if trigger == "hard" else "soft penalty"
    semantic_history_lines = "\n".join(
        f"- {index}. {sentence}"
        for index, sentence in enumerate(semantic_history, start=1)
    )
    return render_template(
        "semantic_guard.md",
        level=level,
        max_similarity=f"{max_similarity:.3f}",
        soft_threshold=str(soft_threshold),
        hard_threshold=str(hard_threshold),
        previous_candidate=previous_candidate,
        semantic_history_lines=semantic_history_lines,
        json_shape=REACTION_UTTERANCE_JSON_SHAPE,
    ).strip()


def build_partner_response_nudge_block(*, latest_partner_utterance: str) -> str:
    return render_template(
        "partner_response_nudge.md",
        latest_partner_utterance=latest_partner_utterance,
        json_shape=REACTION_UTTERANCE_JSON_SHAPE,
    ).strip()


def template_file_plan() -> list[str]:
    return [
        "salient_questions_instruction.md",
        "insights_instruction.md",
        "importance_scoring.md",
        "day_plan_broad_strokes_instruction.md",
        "hourly_plan_instruction.md",
        "minute_plan_instruction.md",
        "reaction_guidelines.md",
        "reaction_few_shot_examples.md",
        "reaction_combined_question.md",
        "reaction_decision_question.md",
        "reaction_intent_question.md",
        "reaction_utterance_question.md",
        "language_system_ko.md",
        "language_system_en.md",
        "overlap_guard.md",
        "semantic_guard.md",
        "partner_response_nudge.md",
    ]
