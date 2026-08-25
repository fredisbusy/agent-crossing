from pathlib import Path

from agents.persona_loader import PersonaLoader


def test_jiho_crush_is_private_and_sujin_retains_autonomy() -> None:
    loader = PersonaLoader(Path(__file__).resolve().parents[1] / "persona")
    jiho = loader.load("Jiho")
    sujin = loader.load("Sujin")
    jiho_knowledge = " ".join(
        [*jiho.identity_stable_set, *(memory.content for memory in jiho.seed_memories)]
    )
    sujin_knowledge = " ".join(
        [
            *sujin.identity_stable_set,
            *(memory.content for memory in sujin.seed_memories),
        ]
    )

    assert "좋아" in jiho_knowledge
    assert "지호만 아는" in jiho_knowledge
    assert "좋아" not in sujin_knowledge
    assert "숨은 감정" not in sujin_knowledge
    assert "그 이상의 관계를 전제하지 않는다" in sujin_knowledge
    assert "자신의 판단" in sujin_knowledge
