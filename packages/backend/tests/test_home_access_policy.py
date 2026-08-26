import datetime
from dataclasses import dataclass

import numpy as np

from agents.agent import AgentIdentity
from agents.home_access import HomeAccessPolicy
from agents.memory.memory_object import MemoryObject, NodeType
from agents.relationships import RelationshipMetrics, RelationshipService


class FakeMemoryService:
    def __init__(self, contents: list[str] | None = None) -> None:
        now = datetime.datetime(2026, 8, 26, 18, 0)
        self._memories = [
            MemoryObject(
                id=index,
                node_type=NodeType.OBSERVATION,
                citations=None,
                content=content,
                created_at=now,
                last_accessed_at=now,
                importance=5,
                embedding=np.zeros(3),
            )
            for index, content in enumerate(contents or [])
        ]

    def get_recent_memories(self, *, limit: int | None = None) -> list[MemoryObject]:
        memories = list(reversed(self._memories))
        return memories if limit is None else memories[:limit]


@dataclass
class FakeAgent:
    identity: AgentIdentity
    memory_service: FakeMemoryService


def _agent(
    agent_id: str,
    name: str,
    home: str,
    memories: list[str] | None = None,
) -> FakeAgent:
    return FakeAgent(
        identity=AgentIdentity(
            id=agent_id,
            name=name,
            age=30,
            traits=["차분함"],
            home=home,
            workplace="브라이어 코브 > 마을 광장",
        ),
        memory_service=FakeMemoryService(memories),
    )


def test_home_owner_is_allowed_but_unfamiliar_visitor_is_denied() -> None:
    jiho = _agent("jiho", "지호", "브라이어 코브 > 지호의 집")
    byeongyong = _agent("byeongyong", "병용", "브라이어 코브 > 병용의 집")
    policy = HomeAccessPolicy(
        agents=[jiho, byeongyong],
        relationships=RelationshipService(["jiho", "byeongyong"]),
    )

    assert policy.can_enter_home("jiho", jiho.identity.home)
    denied = policy.decision(
        agent_id="byeongyong", home_path=jiho.identity.home
    )
    assert not denied.allowed
    assert "초대 기록이 없음" in denied.reason
    assert jiho.identity.home not in policy.allowed_locations("byeongyong")


def test_owner_defined_close_relationship_allows_home_access() -> None:
    jiho = _agent("jiho", "지호", "브라이어 코브 > 지호의 집")
    byeongyong = _agent("byeongyong", "병용", "브라이어 코브 > 병용의 집")
    relationships = RelationshipService(
        ["jiho", "byeongyong"],
        baselines={
            ("jiho", "byeongyong"): RelationshipMetrics(
                familiarity=70, trust=60, affinity=55, tension=0
            )
        },
    )
    policy = HomeAccessPolicy(
        agents=[jiho, byeongyong], relationships=relationships
    )

    decision = policy.decision(
        agent_id="byeongyong", home_path=jiho.identity.home
    )
    assert decision.allowed
    assert decision.reason == "집주인이 가깝고 신뢰하는 관계"


def test_explicit_owner_utterance_grants_invited_visitor_access() -> None:
    jiho = _agent("jiho", "지호", "브라이어 코브 > 지호의 집")
    byeongyong = _agent(
        "byeongyong",
        "병용",
        "브라이어 코브 > 병용의 집",
        memories=["지호가 이렇게 말했다: 오늘 저녁 우리 집에 놀러 와도 돼."],
    )
    policy = HomeAccessPolicy(
        agents=[jiho, byeongyong],
        relationships=RelationshipService(["jiho", "byeongyong"]),
    )

    decision = policy.decision(
        agent_id="byeongyong", home_path=jiho.identity.home
    )
    assert decision.allowed
    assert decision.reason == "집주인의 명시적 초대 기록"


def test_third_person_plan_about_inviting_friends_is_not_an_invitation() -> None:
    jiho = _agent("jiho", "지호", "브라이어 코브 > 지호의 집")
    byeongyong = _agent(
        "byeongyong",
        "병용",
        "브라이어 코브 > 병용의 집",
        memories=["지호는 저녁에 친구들을 자기 집으로 초대할 계획이다."],
    )
    policy = HomeAccessPolicy(
        agents=[jiho, byeongyong],
        relationships=RelationshipService(["jiho", "byeongyong"]),
    )

    assert not policy.can_enter_home("byeongyong", jiho.identity.home)
