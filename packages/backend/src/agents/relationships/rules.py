from .models import RelationshipEventType, RelationshipMetrics

EVENT_DELTAS: dict[RelationshipEventType, RelationshipMetrics] = {
    RelationshipEventType.DIALOGUE_COMPLETED: RelationshipMetrics(2, 0, 2, -2),
    RelationshipEventType.HELP_GIVEN: RelationshipMetrics(2, 2, 2, -2),
    RelationshipEventType.HELP_RECEIVED: RelationshipMetrics(2, 6, 4, -2),
    RelationshipEventType.PERSONAL_DISCLOSURE_RECEIVED: RelationshipMetrics(4, 4, 2, 0),
    RelationshipEventType.COMPLIMENT_RECEIVED: RelationshipMetrics(2, 2, 4, -2),
    RelationshipEventType.PROMISE_MADE: RelationshipMetrics(2, 2, 2, 0),
    RelationshipEventType.PROMISE_KEPT: RelationshipMetrics(2, 8, 4, -4),
    RelationshipEventType.PROMISE_BROKEN: RelationshipMetrics(0, -10, -4, 6),
    RelationshipEventType.CONFLICT: RelationshipMetrics(2, -4, -6, 8),
    RelationshipEventType.INSULT_RECEIVED: RelationshipMetrics(0, -6, -8, 10),
    RelationshipEventType.APOLOGY_ACCEPTED: RelationshipMetrics(2, 4, 4, -8),
    RelationshipEventType.ROMANTIC_INTEREST_RECOGNIZED: RelationshipMetrics(
        romantic_interest=8
    ),
    RelationshipEventType.ROMANTIC_GESTURE_WELCOMED: RelationshipMetrics(
        familiarity=2,
        trust=4,
        affinity=4,
        tension=-2,
        romantic_interest=8,
    ),
    RelationshipEventType.ROMANTIC_BOUNDARY_SET: RelationshipMetrics(
        romantic_interest=-10
    ),
}

METRIC_RANGES = {
    "familiarity": (0, 100),
    "trust": (-100, 100),
    "affinity": (-100, 100),
    "tension": (0, 100),
    "romantic_interest": (0, 100),
}

DAILY_GROSS_CAPS = {
    "familiarity": 12,
    "trust": 24,
    "affinity": 20,
    "tension": 24,
    "romantic_interest": 16,
}


def relationship_status_label(metrics: RelationshipMetrics) -> str:
    if metrics.tension >= 60:
        return "긴장된 관계"
    if metrics.trust <= -40:
        return "불신하는 관계"
    if metrics.affinity <= -40:
        return "거리감 있는 관계"
    if metrics.familiarity < 15:
        return "아직 낯선 사이"
    if metrics.trust >= 50 and metrics.affinity >= 50:
        return "가깝고 신뢰하는 관계"
    if metrics.affinity >= 40:
        return "인간적으로 호감 있는 관계"
    if metrics.trust >= 40:
        return "신뢰하는 관계"
    return "알아가는 관계"
