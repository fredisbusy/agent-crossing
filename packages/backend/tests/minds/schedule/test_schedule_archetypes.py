import pytest

from minds.schedule import load_archetype

ARCHETYPES = ("cafe_owner", "student", "pharmacist", "professor", "retiree", "artist")
PLACEHOLDERS = {
    "home": "Smallville > Lin Family House > Kitchen",
    "bedroom": "Smallville > Lin Family House > Bedroom",
}
CANONICAL_PATHS = {
    "Smallville > Town Square",
    "Smallville > Johnson Park > Garden",
    "Smallville > Hobbs Cafe > Counter",
    "Smallville > Hobbs Cafe > Seating",
    "Smallville > The Willows Market > Store",
    "Smallville > Oak Hill College > Classroom",
    "Smallville > Oak Hill College > Library",
    "Smallville > The Rose and Crown Pub > Bar",
    "Smallville > Lin Family House > Kitchen",
    "Smallville > Lin Family House > Bedroom",
    "Smallville > Moore Family House > Living Room",
    "Smallville > Moore Family House > Bedroom",
    "Smallville > Dorm for Oak Hill College > Klaus's Room",
    "Smallville > Dorm for Oak Hill College > Maria's Room",
    "Smallville > Dorm for Oak Hill College > Common Room",
    "Smallville > Isabella's Apartment > Bedroom",
    "Smallville > Artist's Co-living Space > Common Room",
    "Smallville > Artist's Co-living Space > Studio",
}


@pytest.mark.parametrize("name", ARCHETYPES)
def test_archetype_loads_with_all_paths_canonical(name: str) -> None:
    config = load_archetype(name, placeholders=PLACEHOLDERS)
    assert config.entries
    assert any(entry.action == "sleep" for entry in config.entries)
    for entry in config.entries:
        assert entry.location_path in CANONICAL_PATHS, entry.location_path


def test_placeholders_are_replaced_with_resident_places() -> None:
    config = load_archetype(
        "student",
        placeholders={
            "home": "Smallville > Dorm for Oak Hill College > Common Room",
            "bedroom": "Smallville > Dorm for Oak Hill College > Klaus's Room",
        },
    )
    paths = {entry.location_path for entry in config.entries}
    assert "Smallville > Dorm for Oak Hill College > Klaus's Room" in paths
    assert not any("{" in path for path in paths)


def test_missing_placeholder_raises() -> None:
    with pytest.raises(ValueError):
        load_archetype("student", placeholders={"home": PLACEHOLDERS["home"]})
