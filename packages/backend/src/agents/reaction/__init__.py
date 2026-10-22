from .contracts import (
    DialogueArc,
    GenerateClient,
    ReactionDecision,
    ReactionDecisionInput,
    ReactionCombined,
    ReactionDecisionTrace,
    ReactionIntent,
    ReactionUtterance,
)

__all__ = [
    "DialogueArc",
    "GenerateClient",
    "ReactionDecision",
    "ReactionDecisionInput",
    "ReactionCombined",
    "ReactionDecisionTrace",
    "ReactionIntent",
    "ReactionUtterance",
]


def __getattr__(name: str) -> object:
    if name == "ReactionGraphRunner":
        from .graph import ReactionGraphRunner

        return ReactionGraphRunner
    raise AttributeError(name)
