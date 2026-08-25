"""Leaf dataclasses for the §3.4/§4.3 pass-by vs converse encounter gate.

Kept dependency-free from `llm.governance.parsing` so both
`agents/reaction/encounter.py` and `llm/governance/parsing.py` can import
these without forming an import cycle.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from agents.agent import AgentIdentity, AgentProfile
from agents.memory.memory_object import MemoryObject


@dataclass(frozen=True)
class EncounterDecisionTrace:
    """Governance-facing trace; never merged into a Brain domain result."""

    raw_response: str
    parse_success: bool
    parse_error: str = ""


@dataclass(frozen=True)
class EncounterDecision:
    should_converse: bool
    relationship_summary: str
    context_summary: str
    reason: str
    trace: EncounterDecisionTrace = EncounterDecisionTrace(
        raw_response="", parse_success=False, parse_error="uninitialized"
    )


@dataclass(frozen=True)
class EncounterDecisionInput:
    self_identity: AgentIdentity
    other_identity: AgentIdentity
    self_profile: AgentProfile
    current_time: datetime.datetime
    retrieved_memories: list[MemoryObject]
