from pathlib import Path

from agents.persona_loader import PersonaLoader


PERSONA_DIR = Path(__file__).resolve().parents[1] / "persona"

EXPECTED_SIGNATURES: dict[str, tuple[str, ...]] = {
    "Haeun": ("수채화", "침묵", "전시"),
    "Jiho": ("수선", "건조한 농담", "독서 모임"),
    "Jungwoo": ("나무", "짧은 문장", "수프"),
    "Minji": ("즉석카메라", "말이 빠", "개인 에세이"),
    "Sujin": ("십자말풀이", "거절", "휴식"),
    "Taeo": ("손북", "과장", "피크닉"),
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

