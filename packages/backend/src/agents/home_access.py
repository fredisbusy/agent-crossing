from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from agents.agent import AgentIdentity
from agents.memory.memory_object import MemoryObject
from agents.relationships import RelationshipService
from agents.relationships.rules import relationship_status_label
from planning_locations import CANONICAL_LOCATIONS, HOME_LOCATIONS


class RecentMemoryService(Protocol):
    def get_recent_memories(self, *, limit: int | None = None) -> list[MemoryObject]: ...


class HomeAccessAgent(Protocol):
    @property
    def identity(self) -> AgentIdentity: ...

    @property
    def memory_service(self) -> RecentMemoryService: ...


@dataclass(frozen=True)
class HomeAccessDecision:
    allowed: bool
    reason: str
    owner_agent_id: str | None


class HomeAccessPolicy:
    """Authoritative ownership, friendship, and invitation rules for homes."""

    def __init__(
        self,
        *,
        agents: Iterable[HomeAccessAgent],
        relationships: RelationshipService,
    ) -> None:
        self._agents: dict[str, HomeAccessAgent] = {
            str(agent.identity.id): agent for agent in agents
        }
        self._owners_by_home: dict[str, HomeAccessAgent] = {
            agent.identity.home: agent
            for agent in agents
            if agent.identity.home in HOME_LOCATIONS
        }
        self._relationships: RelationshipService = relationships

    def allowed_locations(self, agent_id: str) -> tuple[str, ...]:
        return tuple(
            location
            for location in CANONICAL_LOCATIONS
            if location not in HOME_LOCATIONS
            or self.decision(agent_id=agent_id, home_path=location).allowed
        )

    def can_enter_home(self, agent_id: str, home_path: str) -> bool:
        return self.decision(agent_id=agent_id, home_path=home_path).allowed

    def decision(self, *, agent_id: str, home_path: str) -> HomeAccessDecision:
        visitor = self._agents.get(agent_id)
        owner = self._owners_by_home.get(home_path)
        if owner is None:
            return HomeAccessDecision(False, "등록된 집주인이 없는 집", None)
        owner_id = str(owner.identity.id)
        if visitor is None:
            return HomeAccessDecision(False, "등록되지 않은 방문자", owner_id)
        if agent_id == owner_id:
            return HomeAccessDecision(True, "본인 소유의 집", owner_id)

        relationship = self._relationships.state_for(owner_id, agent_id)
        if relationship_status_label(relationship.metrics) == "가깝고 신뢰하는 관계":
            return HomeAccessDecision(True, "집주인이 가깝고 신뢰하는 관계", owner_id)
        if self._has_explicit_invitation(visitor=visitor, owner=owner):
            return HomeAccessDecision(True, "집주인의 명시적 초대 기록", owner_id)
        return HomeAccessDecision(
            False,
            "본인 집이 아니며 친밀 관계나 집주인의 초대 기록이 없음",
            owner_id,
        )

    @staticmethod
    def _has_explicit_invitation(
        *, visitor: HomeAccessAgent, owner: HomeAccessAgent
    ) -> bool:
        try:
            memories = visitor.memory_service.get_recent_memories(limit=100)
        except Exception:
            return False
        speech_prefix = f"{owner.identity.name}가 이렇게 말했다:"
        home_name = owner.identity.home.rsplit(" > ", maxsplit=1)[-1]
        home_markers = ("우리 집", "내 집", home_name)
        invitation_markers = (
            "초대",
            "놀러 와",
            "놀러와",
            "들어와",
            "와도 돼",
            "와도 좋",
            "오셔도",
            "같이 가자",
            "올래",
            "오면 좋",
            "들러",
            "방문해",
        )
        for memory in memories:
            content = memory.content.strip()
            if not content.startswith(speech_prefix):
                continue
            utterance = content[len(speech_prefix) :].strip()
            if any(marker in utterance for marker in home_markers) and any(
                marker in utterance for marker in invitation_markers
            ):
                return True
        return False
