from world.space import LocationTree

CAFE = "Smallville > Hobbs Cafe"
COUNTER = "Smallville > Hobbs Cafe > Counter"
SEATING = "Smallville > Hobbs Cafe > Seating"
PARK = "Smallville > Johnson Park"


def make_tree() -> LocationTree:
    return LocationTree([COUNTER, SEATING, PARK])


def test_intermediate_ancestors_become_nodes() -> None:
    tree = make_tree()
    assert CAFE in tree and "Smallville" in tree
    assert "Smallville > Nowhere" not in tree


def test_parent_children_ancestors() -> None:
    tree = make_tree()
    assert tree.parent(COUNTER) == CAFE
    assert tree.parent("Smallville") is None
    assert tree.children(CAFE) == (COUNTER, SEATING)
    assert tree.children("Smallville") == (CAFE, PARK)
    assert tree.ancestors(COUNTER) == (CAFE, "Smallville")
    assert tree.ancestors("Smallville") == ()
    assert tree.depth(COUNTER) == 3


def test_is_within() -> None:
    tree = make_tree()
    assert tree.is_within(COUNTER, CAFE)
    assert tree.is_within(CAFE, CAFE)
    assert not tree.is_within(CAFE, COUNTER)
    assert not tree.is_within("Smallville > Hobbs Cafe2", CAFE)


def test_subtree_keeps_only_known_paths_and_ancestors() -> None:
    sub = make_tree().subtree([COUNTER, "Smallville > Unknown"])
    assert sub.paths() == ("Smallville", CAFE, COUNTER)
    assert SEATING not in sub and PARK not in sub
