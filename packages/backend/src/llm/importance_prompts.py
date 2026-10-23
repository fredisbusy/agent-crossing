from .template_loader import render_template

IMPORTANCE_JSON_SHAPE = '{"importance": <int 1-10>}'

IMPORTANCE_BATCH_JSON_SHAPE = '{"importances": [<int 1-10>, <int 1-10>]}'


def build_importance_scoring_prompt(
    *,
    agent_name: str,
    identity_stable_set: list[str],
    current_plan: str | None,
    observation: str,
) -> str:
    identity_text = " | ".join(identity_stable_set[:3]) or "N/A"
    current_plan_text = current_plan or "N/A"
    return render_template(
        "importance_scoring.md",
        json_shape=IMPORTANCE_JSON_SHAPE,
        agent_name=agent_name,
        identity_text=identity_text,
        current_plan_text=current_plan_text,
        observation=observation,
    )


def build_importance_batch_scoring_prompt(
    *,
    agent_name: str,
    identity_stable_set: list[str],
    current_plan: str | None,
    observations: list[str],
) -> str:
    identity_text = " | ".join(identity_stable_set[:3]) or "N/A"
    current_plan_text = current_plan or "N/A"
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(observations, 1))
    return render_template(
        "importance_scoring_batch.md",
        json_shape=IMPORTANCE_BATCH_JSON_SHAPE,
        agent_name=agent_name,
        identity_text=identity_text,
        current_plan_text=current_plan_text,
        observations=numbered,
        count=str(len(observations)),
    )
