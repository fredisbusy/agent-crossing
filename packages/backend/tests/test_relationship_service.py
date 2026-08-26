import datetime
import uuid
from dataclasses import replace

import pytest
from agents.relationships import (
    RelationshipEventType,
    RelationshipMetrics,
    RelationshipService,
)


def test_relationship_events_are_directional_and_idempotent() -> None:
    service = RelationshipService(["haeun", "jiho"])
    now = datetime.datetime(2026, 8, 26, 12, 0)

    event = service.record_event(
        subject_agent_id="haeun",
        target_agent_id="jiho",
        event_type=RelationshipEventType.HELP_RECEIVED,
        source_event_id="help:1",
        occurred_at=now,
    )

    assert event is not None
    assert service.state_for("haeun", "jiho").metrics.trust == 6
    assert service.state_for("haeun", "jiho").metrics.romantic_interest == 0
    assert service.state_for("jiho", "haeun").metrics.trust == 0
    assert (
        service.record_event(
            subject_agent_id="haeun",
            target_agent_id="jiho",
            event_type=RelationshipEventType.HELP_RECEIVED,
            source_event_id="help:1",
            occurred_at=now,
        )
        is None
    )


def test_relationship_daily_cap_and_metric_clamp_are_applied() -> None:
    service = RelationshipService(["haeun", "jiho"])
    now = datetime.datetime(2026, 8, 26, 12, 0)
    for index in range(10):
        service.record_event(
            subject_agent_id="haeun",
            target_agent_id="jiho",
            event_type=RelationshipEventType.INSULT_RECEIVED,
            source_event_id=f"insult:{index}",
            occurred_at=now,
        )

    state = service.state_for("haeun", "jiho")
    assert state.metrics.trust == -24
    assert state.metrics.affinity == -20
    assert state.metrics.tension == 24


def test_romantic_interest_changes_only_for_explicit_romantic_events() -> None:
    service = RelationshipService(["jiho", "sujin"])
    now = datetime.datetime(2026, 8, 26, 12, 0)
    service.record_event(
        subject_agent_id="jiho",
        target_agent_id="sujin",
        event_type=RelationshipEventType.DIALOGUE_COMPLETED,
        source_event_id="dialogue:1",
        occurred_at=now,
    )
    assert service.state_for("jiho", "sujin").metrics.romantic_interest == 0

    service.record_event(
        subject_agent_id="jiho",
        target_agent_id="sujin",
        event_type=RelationshipEventType.ROMANTIC_INTEREST_RECOGNIZED,
        source_event_id="romantic:1",
        occurred_at=now,
    )
    assert service.state_for("jiho", "sujin").metrics.romantic_interest == 8


def test_event_ids_are_unique_between_sessions() -> None:
    now = datetime.datetime(2026, 8, 26, 12, 0)
    ids = []
    for service in (
        RelationshipService(["jiho", "sujin"]),
        RelationshipService(["jiho", "sujin"]),
    ):
        event = service.record_event(
            subject_agent_id="jiho",
            target_agent_id="sujin",
            event_type=RelationshipEventType.DIALOGUE_COMPLETED,
            source_event_id="dialogue:1",
            occurred_at=now,
        )
        assert event is not None
        ids.append(event.id)
    assert ids[0] != ids[1]


def test_restore_rejects_noncanonical_romantic_delta_and_event_id() -> None:
    now = datetime.datetime(2026, 8, 26, 12, 0)
    source = RelationshipService(["jiho", "sujin"])
    event = source.record_event(
        subject_agent_id="jiho",
        target_agent_id="sujin",
        event_type=RelationshipEventType.DIALOGUE_COMPLETED,
        source_event_id="dialogue:1",
        occurred_at=now,
    )
    assert event is not None
    target = RelationshipService(["jiho", "sujin"])
    romantic_delta = replace(event.applied_delta, romantic_interest=1)
    romantic_after = replace(event.after, romantic_interest=1)

    with pytest.raises(ValueError, match="applied delta"):
        target.restore(
            states=[
                replace(
                    state,
                    metrics=(
                        romantic_after
                        if state.subject_agent_id == "jiho"
                        and state.target_agent_id == "sujin"
                        else state.metrics
                    ),
                )
                for state in source.states()
            ],
            events=[
                replace(
                    event,
                    applied_delta=romantic_delta,
                    after=romantic_after,
                )
            ],
            event_namespace=source.event_namespace,
        )

    with pytest.raises(ValueError, match="namespace"):
        target.restore(
            states=source.states(),
            events=[replace(event, id=str(uuid.uuid4()))],
            event_namespace=source.event_namespace,
        )


def test_restore_rejects_revision_without_events() -> None:
    source = RelationshipService(["jiho", "sujin"])
    states = list(source.states())
    states[0] = replace(states[0], metrics=RelationshipMetrics(affinity=10), revision=1)

    with pytest.raises(ValueError, match="event ledger"):
        source.restore(states=states, events=[])
