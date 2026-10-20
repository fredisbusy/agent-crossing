import json
from pathlib import Path

import pytest
from world.residents import (
    DEFAULT_RESIDENTS_DIR,
    ResidentConfig,
    apply_mind_selection,
    load_resident_configs,
)

ARCHETYPES = {"cafe_owner", "student", "pharmacist", "professor", "retiree", "artist"}


def test_default_directory_has_eight_residents_in_priority_order() -> None:
    configs = load_resident_configs()
    assert [c.agent_priority for c in configs] == list(range(1, 9))
    assert configs[0].resident_id == "isabella_rodriguez"
    assert {c.archetype for c in configs} <= ARCHETYPES
    assert {c.resident_id for c in configs if c.mind == "llm"} == {
        "isabella_rodriguez",
        "klaus_mueller",
    }
    for config in configs:
        assert {"home", "bedroom"} <= set(config.placeholders)


def test_locations_use_canonical_paths() -> None:
    for config in load_resident_configs():
        assert config.home_location.startswith("Smallville > ")
        assert config.start_location.startswith("Smallville > ")


def test_loader_skips_subdirectories(tmp_path: Path) -> None:
    sample = load_resident_configs()[0]
    (tmp_path / "a.json").write_text(sample.model_dump_json(), encoding="utf-8")
    sub = tmp_path / "archetypes"
    sub.mkdir()
    (sub / "student.json").write_text(json.dumps({"entries": []}), encoding="utf-8")
    assert [c.resident_id for c in load_resident_configs(tmp_path)] == [sample.resident_id]
    assert DEFAULT_RESIDENTS_DIR.name == "residents"


def _llm_ids(configs: list[ResidentConfig]) -> set[str]:
    return {c.resident_id for c in configs if c.mind == "llm"}


def test_selection_by_ids() -> None:
    chosen = apply_mind_selection(load_resident_configs(), agent_ids=["sam_moore"])
    assert _llm_ids(chosen) == {"sam_moore"}


def test_selection_by_count_uses_priority() -> None:
    chosen = apply_mind_selection(load_resident_configs(), agent_count=3)
    assert _llm_ids(chosen) == {"isabella_rodriguez", "klaus_mueller", "maria_lopez"}
    assert _llm_ids(apply_mind_selection(load_resident_configs(), agent_count=0)) == set()


def test_selection_without_arguments_keeps_file_values() -> None:
    configs = load_resident_configs()
    assert apply_mind_selection(configs) == configs


def test_selection_rejects_unknown_id() -> None:
    with pytest.raises(ValueError):
        apply_mind_selection(load_resident_configs(), agent_ids=["nobody"])
