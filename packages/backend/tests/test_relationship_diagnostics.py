from pathlib import Path

from agents.persona_loader import PersonaLoader
from agents.relationship_diagnostics import build_relationship_snapshot
from agents.memory.memory_object import MemoryObject, NodeType
import datetime
import numpy as np


def test_relationship_summary_preserves_private_asymmetric_perspectives() -> None:
    loader = PersonaLoader(Path(__file__).resolve().parents[1] / "persona")
    jiho = loader.load("Jiho")
    sujin = loader.load("Sujin")

    jiho_view = build_relationship_snapshot(
        identity_stable_set=jiho.identity_stable_set,
        memories=[],
        target_agent_id="sujin",
        target_name="수진",
    )
    sujin_view = build_relationship_snapshot(
        identity_stable_set=sujin.identity_stable_set,
        memories=[],
        target_agent_id="jiho",
        target_name="지호",
    )

    assert jiho_view.summary_status == "available"
    assert jiho_view.summary is not None and "좋아" in jiho_view.summary
    assert sujin_view.summary is not None and "믿을 만한 친구" in sujin_view.summary
    assert "좋아" not in sujin_view.summary
    assert all(evidence.source == "persona" for evidence in jiho_view.evidence)


def test_relationship_summary_does_not_invent_unknown_relationships() -> None:
    relationship = build_relationship_snapshot(
        identity_stable_set=["지호는 스토리하우스 도서관의 사서다."],
        memories=[],
        target_agent_id="newcomer",
        target_name="New Comer",
    )

    assert relationship.summary is None
    assert relationship.summary_status == "no_explicit_evidence"
    assert relationship.evidence_total == 0
    assert relationship.evidence == ()


def test_relationship_summary_rejects_name_only_persona_and_invalid_reflection() -> (
    None
):
    now = datetime.datetime(2026, 8, 26, 9, 0)
    reflection = MemoryObject(
        id=2,
        node_type=NodeType.REFLECTION,
        citations=[999],
        content="지호와 대화하며 더 가까운 친구가 되었다.",
        created_at=now,
        last_accessed_at=now,
        importance=5,
        embedding=np.zeros(768, dtype=np.float32),
    )
    relationship = build_relationship_snapshot(
        identity_stable_set=["지호는 스토리하우스 도서관에서 일한다."],
        memories=[reflection],
        target_agent_id="jiho",
        target_name="지호",
    )

    assert relationship.summary is None
    assert relationship.evidence == ()


def test_relationship_summary_filters_plan_and_internal_action_codes() -> None:
    now = datetime.datetime(2026, 8, 26, 9, 0)
    memories = [
        MemoryObject(
            id=index,
            node_type=node_type,
            citations=None,
            content=content,
            created_at=now,
            last_accessed_at=now,
            importance=5,
            embedding=np.zeros(768, dtype=np.float32),
        )
        for index, (node_type, content) in enumerate(
            [
                (NodeType.PLAN, "지호와 도서관에 가는 계획"),
                (NodeType.OBSERVATION, "지호가 at:지호의 집 상태이다."),
                (NodeType.OBSERVATION, "지호와 대화 prompt=비공개 지시"),
                (NodeType.OBSERVATION, "지호와 차를 마시며 편안하게 대화했다."),
            ]
        )
    ]
    relationship = build_relationship_snapshot(
        identity_stable_set=[],
        memories=memories,
        target_agent_id="jiho",
        target_name="지호",
    )

    assert relationship.evidence_total == 1
    assert relationship.summary == "지호와 차를 마시며 편안하게 대화했다."
