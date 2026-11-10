from minds.social import Friendship
from minds.social.friendship import CLOSE_FRIEND_LIMIT, CLOSE_FRIEND_SCORE


def test_closest_lists_high_scores_first_up_to_the_limit() -> None:
    friendship = Friendship()
    for index, name in enumerate(["a", "b", "c", "d"]):
        friendship.add(name, CLOSE_FRIEND_SCORE + index)
    friendship.add("stranger", CLOSE_FRIEND_SCORE - 1)

    closest = friendship.closest()

    assert [name for name, _ in closest] == ["d", "c", "b"]
    assert len(closest) == CLOSE_FRIEND_LIMIT and closest[0][1] == CLOSE_FRIEND_SCORE + 3


def test_closest_is_empty_without_close_friends() -> None:
    assert Friendship().closest() == ()
