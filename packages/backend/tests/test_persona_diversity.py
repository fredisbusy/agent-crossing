from pathlib import Path

from agents.persona_loader import PersonaLoader


PERSONA_DIR = Path(__file__).resolve().parents[1] / "persona"

EXPECTED_SIGNATURES: dict[str, tuple[str, ...]] = {
    "Haeun": ("야구", "새 취미", "플러팅", "삐"),
    "Jiho": ("수선", "건조한 농담", "독서 모임"),
    "Jungwoo": ("나무", "짧은 문장", "수프"),
    "Minji": ("즉석카메라", "말이 빠", "개인 에세이"),
    "Sujin": ("십자말풀이", "거절", "휴식"),
    "Taeo": ("손북", "과장", "피크닉"),
}

EXPECTED_MBTI: dict[str, str] = {
    "Haeun": "ESTP",
    "Jiho": "INFJ",
    "Jungwoo": "ISTP",
    "Minji": "ENFP",
    "Sujin": "ESTJ",
    "Taeo": "ESFP",
}


def test_roster_personas_have_distinct_non_work_behavioral_anchors() -> None:
    loader = PersonaLoader(PERSONA_DIR)

    assert set(loader.list_names()) == set(EXPECTED_SIGNATURES)

    for persona_name, signatures in EXPECTED_SIGNATURES.items():
        persona = loader.load(persona_name)
        persona_text = " ".join(
            [
                *persona.identity_stable_set,
                *persona.lifestyle_and_routine,
                *persona.current_plan_context,
                *(memory.content for memory in persona.seed_memories),
            ]
        )

        assert len(persona.identity_stable_set) >= 5
        assert len(persona.lifestyle_and_routine) >= 5
        assert len(persona.current_plan_context) >= 3
        assert len(persona.seed_memories) >= 6
        assert all(signature in persona_text for signature in signatures)


def test_roster_personas_encode_boundaries_and_repair_after_social_missteps() -> None:
    loader = PersonaLoader(PERSONA_DIR)

    for persona in loader.load_all():
        identity_text = " ".join(persona.identity_stable_set)
        assert any(
            marker in identity_text
            for marker in ("싫어", "경계", "거절", "재촉", "불편", "부담")
        )

    minji_text = " ".join(loader.load("Minji").identity_stable_set)
    taeo_text = " ".join(loader.load("Taeo").identity_stable_set)
    assert "사과" in minji_text
    assert "선택권" in taeo_text


def test_roster_personas_translate_mbti_and_romantic_preferences_into_behavior() -> None:
    loader = PersonaLoader(PERSONA_DIR)

    for persona_name, mbti in EXPECTED_MBTI.items():
        persona = loader.load(persona_name)
        prompt_visible_identity = " ".join(persona.identity_stable_set[:3])

        assert mbti in persona.agent.traits
        assert mbti in prompt_visible_identity
        assert any(
            marker in prompt_visible_identity for marker in ("끌린다", "설렐")
        )
        assert any(
            marker in prompt_visible_identity
            for marker in ("호감이 낮", "마음이 멀", "거리를 둔다", "삐")
        )


def test_introverted_personas_encode_repeated_unwanted_contact_as_a_boundary() -> None:
    loader = PersonaLoader(PERSONA_DIR)

    for persona_name in ("Jiho", "Jungwoo"):
        identity_text = " ".join(loader.load(persona_name).identity_stable_set[:3])
        assert any(
            marker in identity_text
            for marker in ("계속 말을", "거듭 침범", "재촉")
        )
        assert "호감이 낮" in identity_text


def test_haeun_is_active_flirtatious_and_quick_to_sulk() -> None:
    haeun = PersonaLoader(PERSONA_DIR).load("Haeun")
    persona_text = " ".join(
        [
            *haeun.agent.traits,
            *haeun.identity_stable_set,
            *haeun.lifestyle_and_routine,
            *haeun.current_plan_context,
            *(memory.content for memory in haeun.seed_memories),
        ]
    )

    assert all(
        marker in persona_text
        for marker in ("ESTP", "활동적", "야구", "새 취미", "남자", "플러팅", "삐")
    )
    assert "명확한 거절 뒤에는 더 조르지 않는다" in persona_text
    assert haeun.relationship_baselines["jiho"].romantic_interest == 30
