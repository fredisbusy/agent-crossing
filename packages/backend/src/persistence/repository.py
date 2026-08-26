from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from pydantic import ValidationError
from db.models import (
    AgentRosterRecord,
    GameSessionRecord,
    GameSessionStatus,
    MemoryNodeType,
    PlanLevel,
    SessionCharacterRecord,
    SessionCognitiveLogRecord,
    SessionDialogueStateRecord,
    SessionMemoryCitationRecord,
    SessionMemoryRecord,
    SessionPlanItemRecord,
    SessionPositionHistoryRecord,
    SessionRelationshipEventRecord,
    SessionRelationshipStateRecord,
)
from db.session import SessionLocal
from persistence.contracts import RuntimeSaveState
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session


class SaveVersionConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class PositionHistoryPoint:
    agent_id: str
    turn: int
    occurred_at: datetime.datetime
    tile_x: int
    tile_y: int
    destination_path: str | None
    current_action: str


@dataclass(frozen=True)
class AgentRosterSetting:
    agent_id: str
    enabled: bool


@dataclass(frozen=True)
class SessionSummary:
    id: uuid.UUID
    name: str
    status: GameSessionStatus
    map_id: str
    world_time: datetime.datetime
    turn: int
    revision: int
    save_version: int
    created_at: datetime.datetime
    saved_at: datetime.datetime


class GameSessionRepository:
    def sync_agent_roster(self, *, agent_ids: list[str]) -> list[AgentRosterSetting]:
        """Register newly authored personas without overwriting saved choices."""
        ordered_ids = list(dict.fromkeys(agent_ids))
        with SessionLocal.begin() as db:
            existing = {
                record.agent_id: record
                for record in db.scalars(
                    select(AgentRosterRecord).where(
                        AgentRosterRecord.agent_id.in_(ordered_ids)
                    )
                ).all()
            }
            for agent_id in ordered_ids:
                if agent_id not in existing:
                    record = AgentRosterRecord(agent_id=agent_id, enabled=True)
                    db.add(record)
                    existing[agent_id] = record
            db.flush()
            return [
                AgentRosterSetting(
                    agent_id=agent_id,
                    enabled=existing[agent_id].enabled,
                )
                for agent_id in ordered_ids
            ]

    def set_agent_enabled(
        self, *, agent_id: str, enabled: bool
    ) -> AgentRosterSetting | None:
        now = datetime.datetime.now(datetime.UTC)
        with SessionLocal.begin() as db:
            record = db.scalar(
                select(AgentRosterRecord)
                .where(AgentRosterRecord.agent_id == agent_id)
                .with_for_update()
            )
            if record is None:
                return None
            record.enabled = enabled
            record.updated_at = now
            db.flush()
            return AgentRosterSetting(agent_id=record.agent_id, enabled=record.enabled)

    def list_sessions(self, *, limit: int = 50) -> list[SessionSummary]:
        bounded_limit = max(1, min(limit, 100))
        with SessionLocal() as db:
            records = db.scalars(
                select(GameSessionRecord)
                .order_by(GameSessionRecord.saved_at.desc())
                .limit(bounded_limit)
            ).all()
            return [_summary(record) for record in records]

    def latest_session(self) -> tuple[SessionSummary, RuntimeSaveState] | None:
        with SessionLocal.begin() as db:
            records = db.scalars(
                select(GameSessionRecord)
                .where(GameSessionRecord.status != GameSessionStatus.ERROR)
                .order_by(
                    (GameSessionRecord.status == GameSessionStatus.ACTIVE).desc(),
                    GameSessionRecord.saved_at.desc(),
                )
            ).all()
            for record in records:
                try:
                    state = RuntimeSaveState.model_validate(record.snapshot)
                except ValidationError:
                    record.status = GameSessionStatus.ERROR
                    continue
                return _summary(record), state
        return None

    def mark_error(self, *, session_id: uuid.UUID) -> SessionSummary | None:
        """Quarantine a snapshot that cannot be restored by the current runtime."""
        now = datetime.datetime.now(datetime.UTC)
        with SessionLocal.begin() as db:
            record = db.scalar(
                select(GameSessionRecord)
                .where(GameSessionRecord.id == session_id)
                .with_for_update()
            )
            if record is None:
                return None
            record.status = GameSessionStatus.ERROR
            record.updated_at = now
            db.flush()
            return _summary(record)

    def get(
        self, session_id: uuid.UUID
    ) -> tuple[SessionSummary, RuntimeSaveState] | None:
        with SessionLocal() as db:
            record = db.get(GameSessionRecord, session_id)
            if record is None:
                return None
            return _summary(record), RuntimeSaveState.model_validate(record.snapshot)

    def create(self, *, name: str, state: RuntimeSaveState) -> SessionSummary:
        session_id = uuid.uuid4()
        now = datetime.datetime.now(datetime.UTC)
        with SessionLocal.begin() as db:
            _mark_all_saved(db)
            record = GameSessionRecord(
                id=session_id,
                name=name,
                status=GameSessionStatus.ACTIVE,
                map_id=state.map_id,
                world_time=state.current_time,
                turn=state.turn,
                revision=state.revision,
                parse_failures=state.parse_failures,
                silent_turns=state.silent_turns,
                last_dialogue_end_at=None,
                scheduler_was_running=state.scheduler_was_running,
                planning_error=state.planning_error,
                schema_version=state.schema_version,
                save_version=1,
                snapshot=state.model_dump(mode="json"),
                created_at=now,
                updated_at=now,
                saved_at=now,
            )
            db.add(record)
            _write_projection(db, session_id=session_id, state=state)
            db.flush()
            summary = _summary(record)
        return summary

    def save(
        self,
        *,
        session_id: uuid.UUID,
        state: RuntimeSaveState,
        expected_save_version: int | None,
    ) -> SessionSummary | None:
        now = datetime.datetime.now(datetime.UTC)
        with SessionLocal.begin() as db:
            record = db.scalar(
                select(GameSessionRecord)
                .where(GameSessionRecord.id == session_id)
                .with_for_update()
            )
            if record is None:
                return None
            if (
                expected_save_version is not None
                and record.save_version != expected_save_version
            ):
                raise SaveVersionConflictError(
                    f"expected save version {expected_save_version}, got {record.save_version}"
                )
            record.map_id = state.map_id
            record.world_time = state.current_time
            record.turn = state.turn
            record.revision = state.revision
            record.parse_failures = state.parse_failures
            record.silent_turns = state.silent_turns
            record.last_dialogue_end_at = None
            record.scheduler_was_running = state.scheduler_was_running
            record.planning_error = state.planning_error
            record.schema_version = state.schema_version
            record.save_version += 1
            record.snapshot = state.model_dump(mode="json")
            record.updated_at = now
            record.saved_at = now
            _delete_projection(db, session_id=session_id)
            _write_projection(db, session_id=session_id, state=state)
            db.flush()
            summary = _summary(record)
        return summary

    def position_at(
        self,
        *,
        session_id: uuid.UUID,
        agent_id: str,
        at_time: datetime.datetime,
    ) -> PositionHistoryPoint | None:
        """Reconstruct where `agent_id` was at (or just before) `at_time`.

        Returns the latest recorded position change with
        `occurred_at <= at_time`, i.e. the position the agent held
        throughout `[occurred_at, next change)`.
        """
        with SessionLocal() as db:
            record = db.scalar(
                select(SessionPositionHistoryRecord)
                .where(
                    SessionPositionHistoryRecord.session_id == session_id,
                    SessionPositionHistoryRecord.agent_id == agent_id,
                    SessionPositionHistoryRecord.occurred_at <= at_time,
                )
                .order_by(SessionPositionHistoryRecord.occurred_at.desc())
                .limit(1)
            )
            if record is None:
                return None
            return PositionHistoryPoint(
                agent_id=record.agent_id,
                turn=record.turn,
                occurred_at=record.occurred_at,
                tile_x=record.tile_x,
                tile_y=record.tile_y,
                destination_path=record.destination_path,
                current_action=record.current_action,
            )

    def position_history(
        self,
        *,
        session_id: uuid.UUID,
        agent_id: str | None = None,
        limit: int = 500,
    ) -> list[PositionHistoryPoint]:
        """Chronological position-change log for replay/reconstruction UIs."""
        bounded_limit = max(1, min(limit, 5000))
        with SessionLocal() as db:
            query = select(SessionPositionHistoryRecord).where(
                SessionPositionHistoryRecord.session_id == session_id
            )
            if agent_id is not None:
                query = query.where(SessionPositionHistoryRecord.agent_id == agent_id)
            query = query.order_by(
                SessionPositionHistoryRecord.occurred_at.asc()
            ).limit(bounded_limit)
            records = db.scalars(query).all()
            return [
                PositionHistoryPoint(
                    agent_id=record.agent_id,
                    turn=record.turn,
                    occurred_at=record.occurred_at,
                    tile_x=record.tile_x,
                    tile_y=record.tile_y,
                    destination_path=record.destination_path,
                    current_action=record.current_action,
                )
                for record in records
            ]

    def activate(self, *, session_id: uuid.UUID) -> SessionSummary | None:
        now = datetime.datetime.now(datetime.UTC)
        with SessionLocal.begin() as db:
            record = db.scalar(
                select(GameSessionRecord)
                .where(GameSessionRecord.id == session_id)
                .with_for_update()
            )
            if record is None:
                return None
            _mark_all_saved(db)
            record.status = GameSessionStatus.ACTIVE
            record.updated_at = now
            db.flush()
            summary = _summary(record)
        return summary


def _mark_all_saved(db: Session) -> None:
    db.execute(
        update(GameSessionRecord)
        .where(GameSessionRecord.status == GameSessionStatus.ACTIVE)
        .values(status=GameSessionStatus.SAVED)
    )


def _delete_projection(db: Session, *, session_id: uuid.UUID) -> None:
    db.execute(
        delete(SessionRelationshipEventRecord).where(
            SessionRelationshipEventRecord.session_id == session_id
        )
    )
    db.execute(
        delete(SessionRelationshipStateRecord).where(
            SessionRelationshipStateRecord.session_id == session_id
        )
    )
    db.execute(
        delete(SessionPositionHistoryRecord).where(
            SessionPositionHistoryRecord.session_id == session_id
        )
    )
    db.execute(
        delete(SessionCognitiveLogRecord).where(
            SessionCognitiveLogRecord.session_id == session_id
        )
    )
    db.execute(
        delete(SessionDialogueStateRecord).where(
            SessionDialogueStateRecord.session_id == session_id
        )
    )
    db.execute(
        delete(SessionCharacterRecord).where(
            SessionCharacterRecord.session_id == session_id
        )
    )


def _write_projection(
    db: Session, *, session_id: uuid.UUID, state: RuntimeSaveState
) -> None:
    character_ids: dict[str, uuid.UUID] = {}
    memory_ids: dict[tuple[str, int], uuid.UUID] = {}
    for character in state.characters:
        character_id = uuid.uuid4()
        character_ids[character.agent_id] = character_id
        planning_reason = (
            character.planning.last_replan_reason
            if character.planning is not None
            else None
        )
        db.add(
            SessionCharacterRecord(
                id=character_id,
                session_id=session_id,
                agent_id=character.agent_id,
                name=character.name,
                persona_snapshot={
                    "age": character.age,
                    "traits": character.traits,
                    "identity_stable_set": character.identity_stable_set,
                    "lifestyle_and_routine": character.lifestyle_and_routine,
                },
                tile_x=character.tile_position.x,
                tile_y=character.tile_position.y,
                goal_x=character.goal.x if character.goal is not None else None,
                goal_y=character.goal.y if character.goal is not None else None,
                destination_path=character.destination_path,
                route=[point.model_dump() for point in character.route],
                current_action=character.current_action,
                plan=character.plan,
                current_plan_context=list(character.current_plan_context),
                reflection_accumulated_importance=(
                    character.reflection_accumulated_importance
                ),
                last_replan_reason=planning_reason,
            )
        )
        if character.planning is not None:
            plan_groups = (
                (PlanLevel.DAY, character.planning.day_items),
                (PlanLevel.HOURLY, character.planning.hourly_items),
                (PlanLevel.MINUTE, character.planning.minute_items),
            )
            for level, items in plan_groups:
                for ordinal, item in enumerate(items):
                    db.add(
                        SessionPlanItemRecord(
                            id=uuid.uuid4(),
                            character_id=character_id,
                            parent_id=None,
                            level=level,
                            ordinal=ordinal,
                            start_time=item.start_time,
                            end_time=item.end_time,
                            location=item.location,
                            action_content=item.action_content,
                            is_active=(
                                item.start_time <= state.current_time < item.end_time
                            ),
                        )
                    )
        for memory in character.memories:
            memory_id = uuid.uuid4()
            memory_ids[(character.agent_id, memory.id)] = memory_id
            db.add(
                SessionMemoryRecord(
                    id=memory_id,
                    character_id=character_id,
                    runtime_local_id=memory.id,
                    node_type=MemoryNodeType(memory.node_type),
                    content=memory.content,
                    importance=memory.importance,
                    embedding=memory.embedding,
                    game_created_at=memory.created_at,
                    last_accessed_at=memory.last_accessed_at,
                )
            )
    db.flush()
    for character in state.characters:
        for memory in character.memories:
            for position, cited_local_id in enumerate(memory.citations or []):
                cited_id = memory_ids.get((character.agent_id, cited_local_id))
                if cited_id is None:
                    raise ValueError(
                        f"memory {memory.id} cites unknown memory {cited_local_id}"
                    )
                db.add(
                    SessionMemoryCitationRecord(
                        memory_id=memory_ids[(character.agent_id, memory.id)],
                        cited_memory_id=cited_id,
                        position=position,
                    )
                )
    if state.conversations:
        conversation = state.conversations[0]
        db.add(
            SessionDialogueStateRecord(
                session_id=session_id,
                is_active=conversation.is_active,
                turn_index=conversation.turn_index,
                dialogue_turn_window=conversation.dialogue_turn_window,
                dialogue_target_turns=conversation.dialogue_target_turns,
                dialogue_turns_taken=conversation.dialogue_turns_taken,
                dialogue_goal=conversation.dialogue_goal,
                history=[list(item) for item in conversation.history],
                history_by_agent={
                    agent: [list(item) for item in history]
                    for agent, history in conversation.dialogue_history_by_agent.items()
                },
                incoming_queues_by_agent={
                    agent: list(queue)
                    for agent, queue in conversation.incoming_utterances_by_agent.items()
                },
            )
        )
    for entry in state.position_history:
        character_id = character_ids.get(entry.agent_id)
        if character_id is None:
            continue
        db.add(
            SessionPositionHistoryRecord(
                session_id=session_id,
                character_id=character_id,
                agent_id=entry.agent_id,
                turn=entry.turn,
                occurred_at=entry.occurred_at,
                tile_x=entry.tile_position.x,
                tile_y=entry.tile_position.y,
                destination_path=entry.destination_path,
                current_action=entry.current_action,
            )
        )
    for event in state.dashboard_events:
        db.add(
            SessionCognitiveLogRecord(
                session_id=session_id,
                character_id=character_ids.get(event.agent_id),
                sequence=event.sequence,
                turn=event.turn,
                occurred_at=event.occurred_at,
                agent_id=event.agent_id,
                agent_name=event.agent_name,
                reply=event.reply,
                silent_reason=event.silent_reason,
                parse_failure=event.parse_failure,
                display_thought=event.display_thought,
                model_thought=event.model_thought,
                self_critique=event.self_critique,
                decision_reason=event.decision_reason,
                action_summary=event.action_summary,
                decision_process=event.decision_process,
                governance_trace=event.governance_trace,
            )
        )
    relationship_namespace = uuid.UUID("605a2c89-32a2-5f0d-a37f-43127cefed12")
    for relationship in state.relationship_states:
        db.add(
            SessionRelationshipStateRecord(
                id=uuid.uuid5(
                    relationship_namespace,
                    f"{session_id}:{relationship.subject_agent_id}:{relationship.target_agent_id}",
                ),
                session_id=session_id,
                subject_character_id=character_ids[relationship.subject_agent_id],
                target_character_id=character_ids[relationship.target_agent_id],
                familiarity=relationship.metrics.familiarity,
                trust=relationship.metrics.trust,
                affinity=relationship.metrics.affinity,
                tension=relationship.metrics.tension,
                romantic_interest=relationship.metrics.romantic_interest,
                revision=relationship.revision,
                last_interaction_at=relationship.last_interaction_at,
                updated_at=relationship.updated_at,
            )
        )
    for relationship_event in state.relationship_events:
        db.add(
            SessionRelationshipEventRecord(
                id=uuid.UUID(relationship_event.id),
                session_id=session_id,
                subject_character_id=character_ids[relationship_event.subject_agent_id],
                target_character_id=character_ids[relationship_event.target_agent_id],
                source_event_id=relationship_event.source_event_id,
                event_type=relationship_event.event_type,
                familiarity_delta=relationship_event.applied_delta.familiarity,
                trust_delta=relationship_event.applied_delta.trust,
                affinity_delta=relationship_event.applied_delta.affinity,
                tension_delta=relationship_event.applied_delta.tension,
                romantic_interest_delta=(
                    relationship_event.applied_delta.romantic_interest
                ),
                before_metrics=relationship_event.before.model_dump(),
                after_metrics=relationship_event.after.model_dump(),
                occurred_at=relationship_event.occurred_at,
                rule_version=relationship_event.rule_version,
                source_kind=relationship_event.source_kind,
            )
        )


def _summary(record: GameSessionRecord) -> SessionSummary:
    return SessionSummary(
        id=record.id,
        name=record.name,
        status=record.status,
        map_id=record.map_id,
        world_time=record.world_time,
        turn=record.turn,
        revision=record.revision,
        save_version=record.save_version,
        created_at=record.created_at,
        saved_at=record.saved_at,
    )
