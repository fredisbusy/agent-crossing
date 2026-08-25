from agents.evaluation.diffusion import (
    compute_diffusion_rate,
    compute_relationship_density,
)
from agents.evaluation.interview import InterviewAnswer


def _answer(*, aware: bool) -> InterviewAnswer:
    return InterviewAnswer(
        answer_yes=aware, aware=aware, reason="", citation_memory_ids=[]
    )


def test_diffusion_rate_counts_only_grounded_aware_agents() -> None:
    """§7.1.1: Sam 후보 출마 소식이 1명 -> 8명(32%)으로 확산되는 형태를 재현한다."""
    answers = {
        "Sam": _answer(aware=True),
        "Tom": _answer(aware=True),
        "Latoya": _answer(aware=False),
    }

    result = compute_diffusion_rate(answers)

    assert result.aware_count == 2
    assert result.total_agent_count == 3
    assert result.rate == 2 / 3
    assert set(result.aware_agent_names) == {"Sam", "Tom"}


def test_diffusion_rate_is_zero_with_no_agents() -> None:
    result = compute_diffusion_rate({})

    assert result.rate == 0.0
    assert result.aware_count == 0


def test_relationship_density_formula() -> None:
    """§7.1.1: eta = 2|E| / (|V|(|V|-1))."""
    result = compute_relationship_density(
        agent_names=["A", "B", "C", "D"],
        mutual_acknowledgment_pairs=[("A", "B"), ("A", "C")],
    )

    assert result.edge_count == 2
    assert result.density == 2 * 2 / (4 * 3)


def test_relationship_density_dedupes_reversed_and_duplicate_pairs() -> None:
    result = compute_relationship_density(
        agent_names=["A", "B"],
        mutual_acknowledgment_pairs=[("A", "B"), ("B", "A"), ("A", "B")],
    )

    assert result.edge_count == 1
    assert result.density == 1.0


def test_relationship_density_ignores_self_pairs() -> None:
    result = compute_relationship_density(
        agent_names=["A", "B"],
        mutual_acknowledgment_pairs=[("A", "A")],
    )

    assert result.edge_count == 0
    assert result.density == 0.0


def test_relationship_density_zero_for_single_agent() -> None:
    result = compute_relationship_density(
        agent_names=["A"], mutual_acknowledgment_pairs=[]
    )

    assert result.density == 0.0
