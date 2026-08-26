import datetime
import os
import uuid

import pytest
from db.models import (
    GameSessionRecord,
    GameSessionStatus,
    SessionCharacterRecord,
    SessionMemoryRecord,
)
from db.session import SessionLocal
from persistence.contracts import (
    CharacterSave,
    MemorySave,
    PointSave,
    RelationshipMetricsSave,
    RelationshipStateSave,
    RuntimeSaveState,
    sanitized_diagnostics,
)
from persistence.repository import GameSessionRepository, SaveVersionConflictError
from sqlalchemy import delete, func, select


def _state(*, turn: int = 7) -> RuntimeSaveState:
    game_time = datetime.datetime(2026, 8, 25, 9, 30)
    characters = []
    for index, (agent_id, name) in enumerate((("Jiho", "박지호"), ("Sujin", "김수진"))):
        characters.append(
            CharacterSave(
                agent_id=agent_id,
                name=name,
                age=25 + index,
                traits=["친절함"],
                identity_stable_set=["브라이어 코브 주민"],
                lifestyle_and_routine=["아침 산책"],
                current_plan_context=["마을 광장으로 이동"],
                reflection_accumulated_importance=index,
                memories=[
                    MemorySave(
                        id=0,
                        node_type="OBSERVATION",
                        citations=None,
                        content=f"{name}의 첫 기억",
                        created_at=game_time,
                        last_accessed_at=game_time,
                        importance=5,
                        embedding=[0.0] * 1024,
                    )
                ],
                planning=None,
                tile_position=PointSave(x=10 + index, y=12),
                goal=None,
                route=[],
                destination_path=None,
                explicit_location=None,
                current_action="idle",
                plan="마을 광장으로 이동",
                cognitive_kind=None,
                cognitive_text="",
            )
        )
    return RuntimeSaveState(
        map_id="briar-cove",
        current_time=game_time,
        turn=turn,
        revision=11,
        parse_failures=0,
        silent_turns=0,
        scheduler_was_running=True,
        planning_error=None,
        pair_cooldown_until={},
        conversations=[],
        characters=characters,
        dashboard_events=[],
        relationship_states=[
            RelationshipStateSave(
                subject_agent_id=subject,
                target_agent_id=target,
                metrics=RelationshipMetricsSave(
                    familiarity=0,
                    trust=0,
                    affinity=0,
                    tension=0,
                    romantic_interest=0,
                ),
                last_interaction_at=None,
                updated_at=None,
                revision=0,
            )
            for subject, target in (("Jiho", "Sujin"), ("Sujin", "Jiho"))
        ],
    )


def test_persisted_diagnostics_remove_private_provider_fields() -> None:
    result = sanitized_diagnostics(
        {
            "parse": {"ok": True, "raw_response": "secret"},
            "prompt": "private",
            "api_key": "private",
        }
    )

    assert result == {"parse": {"ok": True}}


def test_runtime_save_rejects_wrong_embedding_dimension() -> None:
    state = _state()
    character = state.characters[0]
    invalid = character.memories[0].model_dump()
    invalid["embedding"] = [0.0]

    with pytest.raises(ValueError, match="1024 dimensions"):
        _ = MemorySave.model_validate(invalid)


@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 to use the local PostgreSQL integration database",
)
def test_repository_round_trip_and_optimistic_save() -> None:
    repository = GameSessionRepository()
    with SessionLocal() as db:
        prior_active_id = db.scalar(
            select(GameSessionRecord.id).where(
                GameSessionRecord.status == GameSessionStatus.ACTIVE
            )
        )
    summary = repository.create(
        name=f"통합 테스트 {uuid.uuid4().hex[:8]}",
        state=_state(),
    )
    try:
        loaded = repository.get(summary.id)
        assert loaded is not None
        loaded_summary, loaded_state = loaded
        assert loaded_summary.turn == 7
        assert loaded_state.characters[0].memories[0].content.endswith("첫 기억")

        with SessionLocal() as db:
            character_count = db.scalar(
                select(func.count())
                .select_from(SessionCharacterRecord)
                .where(SessionCharacterRecord.session_id == summary.id)
            )
            memory_count = db.scalar(
                select(func.count())
                .select_from(SessionMemoryRecord)
                .join(
                    SessionCharacterRecord,
                    SessionMemoryRecord.character_id == SessionCharacterRecord.id,
                )
                .where(SessionCharacterRecord.session_id == summary.id)
            )
        assert character_count == 2
        assert memory_count == 2

        saved = repository.save(
            session_id=summary.id,
            state=_state(turn=8),
            expected_save_version=summary.save_version,
        )
        assert saved is not None
        assert saved.turn == 8
        assert saved.save_version == summary.save_version + 1

        with pytest.raises(SaveVersionConflictError):
            _ = repository.save(
                session_id=summary.id,
                state=_state(turn=9),
                expected_save_version=summary.save_version,
            )
    finally:
        with SessionLocal.begin() as db:
            db.execute(
                delete(GameSessionRecord).where(GameSessionRecord.id == summary.id)
            )
        if prior_active_id is not None:
            _ = repository.activate(session_id=prior_active_id)
