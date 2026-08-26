from dataclasses import dataclass, field


@dataclass
class AgentIdentity:
    """에이전트의 기본 정보와 특성을 담는 클래스."""

    id: str  # 고유 id
    name: str  # 에이전트 이름
    age: int  # 에이전트 나이
    traits: list[str]  # 성격 특성 (예: 친절함, 호기심 등)
    gender: str = "비공개"  # persona에 명시된 성별 표현


@dataclass(frozen=True)
class RelationshipBaseline:
    familiarity: int
    trust: int
    affinity: int
    tension: int
    romantic_interest: int = 0


@dataclass
class FixedPersona:
    identity_stable_set: list[str]
    relationship_baselines: dict[str, RelationshipBaseline] = field(
        default_factory=dict
    )


@dataclass
class ExtendedPersona:
    lifestyle_and_routine: list[str]
    current_plan_context: list[str]


@dataclass
class AgentProfile:
    fixed: FixedPersona
    extended: ExtendedPersona


@dataclass
class AgentContext:
    identity: AgentIdentity
    profile: AgentProfile
    brain: object
    memory_service: object
