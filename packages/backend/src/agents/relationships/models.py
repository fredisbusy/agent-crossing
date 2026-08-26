from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import StrEnum

RELATIONSHIP_RULE_VERSION = "relationship-v1"


class RelationshipEventType(StrEnum):
    DIALOGUE_COMPLETED = "DIALOGUE_COMPLETED"
    HELP_GIVEN = "HELP_GIVEN"
    HELP_RECEIVED = "HELP_RECEIVED"
    PERSONAL_DISCLOSURE_RECEIVED = "PERSONAL_DISCLOSURE_RECEIVED"
    COMPLIMENT_RECEIVED = "COMPLIMENT_RECEIVED"
    PROMISE_MADE = "PROMISE_MADE"
    PROMISE_KEPT = "PROMISE_KEPT"
    PROMISE_BROKEN = "PROMISE_BROKEN"
    CONFLICT = "CONFLICT"
    INSULT_RECEIVED = "INSULT_RECEIVED"
    APOLOGY_ACCEPTED = "APOLOGY_ACCEPTED"
    ROMANTIC_INTEREST_RECOGNIZED = "ROMANTIC_INTEREST_RECOGNIZED"
    ROMANTIC_GESTURE_WELCOMED = "ROMANTIC_GESTURE_WELCOMED"
    ROMANTIC_BOUNDARY_SET = "ROMANTIC_BOUNDARY_SET"


@dataclass(frozen=True)
class RelationshipMetrics:
    familiarity: int = 0
    trust: int = 0
    affinity: int = 0
    tension: int = 0
    romantic_interest: int = 0


@dataclass(frozen=True)
class RelationshipState:
    subject_agent_id: str
    target_agent_id: str
    metrics: RelationshipMetrics
    last_interaction_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    revision: int = 0


@dataclass(frozen=True)
class RelationshipEvent:
    id: str
    source_event_id: str
    subject_agent_id: str
    target_agent_id: str
    event_type: RelationshipEventType
    occurred_at: datetime.datetime
    requested_delta: RelationshipMetrics
    applied_delta: RelationshipMetrics
    before: RelationshipMetrics
    after: RelationshipMetrics
    rule_version: str = RELATIONSHIP_RULE_VERSION
    source_kind: str = "runtime"
