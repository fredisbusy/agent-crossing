from dataclasses import dataclass


@dataclass(frozen=True)
class InsightWithCitation:
    context: str
    citation_memory_ids: list[int]
