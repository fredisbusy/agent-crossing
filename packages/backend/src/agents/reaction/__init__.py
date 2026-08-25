from .contracts import (
    DialogueArc,
    GenerateClient,
    ReactionDecision,
    ReactionDecisionInput,
    ReactionDecisionTrace,
    ReactionIntent,
    ReactionUtterance,
)

__all__ = [
    "DialogueArc",
    "GenerateClient",
    "ReactionDecision",
    "ReactionDecisionInput",
    "ReactionDecisionTrace",
    "ReactionIntent",
    "ReactionUtterance",
]


def __getattr__(name: str) -> object:
    if name == "ReactionGraphRunner":
        from .graph import ReactionGraphRunner

        return ReactionGraphRunner
    if name in (
        "EncounterDecision",
        "EncounterDecisionInput",
        "EncounterDecisionTrace",
        "EncounterGate",
    ):
        from . import encounter

        return getattr(encounter, name)
    raise AttributeError(name)
