from pathlib import Path

from agents.persona_loader import PersonaLoader
from agents.relationship_diagnostics import build_relationship_snapshot


def test_relationship_summary_preserves_private_asymmetric_perspectives() -> None:
    loader = PersonaLoader(Path(__file__).resolve().parents[1] / "persona")
    jiho = loader.load("Jiho")
    sujin = loader.load("Sujin")

    jiho_view = build_relationship_snapshot(
        identity_stable_set=jiho.identity_stable_set,
        memories=[],
        target_agent_id="sujin",
        target_name="Sujin Lee",
    )
    sujin_view = build_relationship_snapshot(
        identity_stable_set=sujin.identity_stable_set,
        memories=[],
        target_agent_id="jiho",
        target_name="Jiho Park",
    )

    assert jiho_view.affinity_score is None
    assert jiho_view.measurement == "not_modeled"
    assert jiho_view.summary is not None and "좋아" in jiho_view.summary
    assert sujin_view.summary is not None and "믿을 만한 친구" in sujin_view.summary
    assert "좋아" not in sujin_view.summary
    assert all(evidence.source == "persona" for evidence in jiho_view.evidence)


def test_relationship_summary_does_not_invent_unknown_relationships() -> None:
    relationship = build_relationship_snapshot(
        identity_stable_set=["Jiho는 Story House의 사서다."],
        memories=[],
        target_agent_id="newcomer",
        target_name="New Comer",
    )

    assert relationship.summary is None
    assert relationship.affinity_score is None
    assert relationship.evidence == ()
