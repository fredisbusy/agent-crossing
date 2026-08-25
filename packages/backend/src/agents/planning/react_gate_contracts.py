"""Leaf dataclasses for the §4.3.1 tick-level continue-vs-react gate.

Kept dependency-free from `llm.governance.parsing` (mirrors
`agents/reaction/contracts.py`) so both `agents/planning/react_gate.py` and
`llm/governance/parsing.py` can import these without forming an import cycle.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from agents.agent import AgentIdentity, AgentProfile


@dataclass(frozen=True)
class PlanDisruptionTrace:
    """Governance-facing trace for the continue/react judgment.

    Not merged into any `ActionLoopResult`-style domain object (AGENTS.md
    §9); callers should route this to a diagnostics/logging channel only.
    """

    raw_response: str
    parse_success: bool
    parse_error: str = ""


@dataclass(frozen=True)
class PlanDisruptionDecision:
    """The continue-vs-react verdict for the current tick's observation."""

    should_react: bool
    reason: str
    trace: PlanDisruptionTrace = PlanDisruptionTrace(
        raw_response="", parse_success=False, parse_error="uninitialized"
    )


@dataclass(frozen=True)
class PlanDisruptionInput:
    agent_identity: AgentIdentity
    profile: AgentProfile
    current_time: datetime.datetime
    agent_status: str
    observation_content: str
