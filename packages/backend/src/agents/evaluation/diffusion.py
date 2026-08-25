"""§7.1.1 information diffusion / relationship density measurement.

Pure functions over `InterviewAnswer` results and acknowledgment pairs —
no LLM I/O here. Callers run `InterviewGate.ask` across agents first, then
feed the results in.
"""

from __future__ import annotations

from dataclasses import dataclass

from .interview import InterviewAnswer


@dataclass(frozen=True)
class DiffusionResult:
    """§7.1.1 information diffusion rate: aware agents / total interviewed."""

    aware_agent_names: list[str]
    total_agent_count: int

    @property
    def aware_count(self) -> int:
        return len(self.aware_agent_names)

    @property
    def rate(self) -> float:
        if self.total_agent_count == 0:
            return 0.0
        return self.aware_count / self.total_agent_count


def compute_diffusion_rate(
    answers_by_agent_name: dict[str, InterviewAnswer],
) -> DiffusionResult:
    """§7.1.1: fraction of interviewed agents whose grounded answer is 'yes'.

    Uses `InterviewAnswer.aware` (the hallucination-filtered verdict), not
    the model's raw `answer_yes` claim.
    """
    aware_agent_names = [
        name for name, answer in answers_by_agent_name.items() if answer.aware
    ]
    return DiffusionResult(
        aware_agent_names=aware_agent_names,
        total_agent_count=len(answers_by_agent_name),
    )


@dataclass(frozen=True)
class RelationshipEdge:
    agent_a: str
    agent_b: str


@dataclass(frozen=True)
class RelationshipDensityResult:
    """§7.1.1 network density eta = 2|E| / (|V|(|V|-1))."""

    edges: list[RelationshipEdge]
    agent_count: int

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def density(self) -> float:
        if self.agent_count < 2:
            return 0.0
        possible_pairs = self.agent_count * (self.agent_count - 1) / 2
        return self.edge_count / possible_pairs


def compute_relationship_density(
    *,
    agent_names: list[str],
    mutual_acknowledgment_pairs: list[tuple[str, str]],
) -> RelationshipDensityResult:
    """§7.1.1: mutual acknowledgment pairs -> undirected edges -> density.

    Each pair in `mutual_acknowledgment_pairs` must already represent a
    *mutual* "Do you know of <name>?" yes from both sides (§7.1 method) —
    this function only dedupes and computes eta, it does not itself decide
    mutuality.
    """
    seen: set[frozenset[str]] = set()
    edges: list[RelationshipEdge] = []
    for agent_a, agent_b in mutual_acknowledgment_pairs:
        if agent_a == agent_b:
            continue
        pair_key = frozenset((agent_a, agent_b))
        if pair_key in seen:
            continue
        seen.add(pair_key)
        edges.append(RelationshipEdge(agent_a=agent_a, agent_b=agent_b))

    return RelationshipDensityResult(edges=edges, agent_count=len(agent_names))
