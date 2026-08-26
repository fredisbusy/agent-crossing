import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .agent import AgentIdentity, RelationshipBaseline
from .agent_brain import AgentBrain


class PersonaLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersonaMemory:
    content: str
    importance: int


@dataclass(frozen=True)
class AgentPersona:
    agent: AgentIdentity
    identity_stable_set: list[str]
    lifestyle_and_routine: list[str]
    current_plan_context: list[str]
    seed_memories: list[PersonaMemory]
    relationship_baselines: dict[str, RelationshipBaseline]


class PersonaLoader:
    def __init__(self, persona_dir: str | Path) -> None:
        self.persona_dir: Path = Path(persona_dir)

    def load(self, persona_name: str) -> AgentPersona:
        json_path = self.persona_dir / f"{persona_name}.json"
        if not json_path.exists():
            raise PersonaLoadError(f"Persona file not found: {json_path}")
        return _parse_persona_json(json_path)

    def list_names(self) -> list[str]:
        """Persona file stems available for `load()`, in the same order
        (sorted, `*.sample.json` excluded) as `load_all()`."""
        return [
            path.stem
            for path in sorted(self.persona_dir.glob("*.json"))
            if not path.name.endswith(".sample.json")
        ]

    def load_all(self) -> list[AgentPersona]:
        json_files = sorted(
            path
            for path in self.persona_dir.glob("*.json")
            if not path.name.endswith(".sample.json")
        )
        return [_parse_persona_json(path) for path in json_files]


def apply_persona_to_brain(
    *,
    brain: AgentBrain,
    persona: AgentPersona,
    now: datetime.datetime,
) -> None:
    current_plan = (
        persona.current_plan_context[0] if persona.current_plan_context else None
    )
    for memory in persona.seed_memories:
        brain.ingest_seed_memory(
            content=memory.content,
            now=now,
            importance=memory.importance,
            identity_stable_set=persona.identity_stable_set,
            current_plan=current_plan,
        )


def _parse_persona_json(path: Path) -> AgentPersona:
    payload = _as_object(cast(object, json.loads(path.read_text(encoding="utf-8"))))

    agent_data = _expect_mapping(payload, "agent")
    fixed_persona = _expect_mapping(payload, "fixed_persona")
    extended_persona = _expect_mapping(payload, "extended_persona")

    agent = AgentIdentity(
        id=_expect_string(agent_data, "agent_id"),
        name=_expect_string(agent_data, "name"),
        age=_expect_int(agent_data, "age"),
        traits=_expect_string_list(agent_data, "traits"),
    )

    memories = _expect_list(payload, "seed_memories")
    seed_memories: list[PersonaMemory] = []
    for memory_data in memories:
        memory = _as_object(memory_data)
        seed_memories.append(
            PersonaMemory(
                content=_expect_string(memory, "content"),
                importance=_expect_int(memory, "importance"),
            )
        )

    return AgentPersona(
        agent=agent,
        identity_stable_set=_expect_string_list(fixed_persona, "identity_stable_set"),
        lifestyle_and_routine=_expect_string_list(
            extended_persona, "lifestyle_and_routine"
        ),
        current_plan_context=_expect_string_list(
            extended_persona, "current_plan_context"
        ),
        seed_memories=seed_memories,
        relationship_baselines=_parse_relationship_baselines(fixed_persona),
    )


def _parse_relationship_baselines(
    fixed_persona: dict[str, object],
) -> dict[str, RelationshipBaseline]:
    raw = fixed_persona.get("relationship_baselines", {})
    if not isinstance(raw, dict):
        raise PersonaLoadError(
            "Persona JSON field 'relationship_baselines' must be an object"
        )
    result: dict[str, RelationshipBaseline] = {}
    for target, value in _as_object(cast(object, raw)).items():
        baseline = _as_object(value)
        metrics = RelationshipBaseline(
            familiarity=_expect_int(baseline, "familiarity"),
            trust=_expect_int(baseline, "trust"),
            affinity=_expect_int(baseline, "affinity"),
            tension=_expect_int(baseline, "tension"),
            romantic_interest=_expect_int(baseline, "romantic_interest"),
        )
        if not 0 <= metrics.familiarity <= 100 or not 0 <= metrics.tension <= 100:
            raise PersonaLoadError(
                "relationship baseline familiarity/tension out of range"
            )
        if not -100 <= metrics.trust <= 100 or not -100 <= metrics.affinity <= 100:
            raise PersonaLoadError("relationship baseline trust/affinity out of range")
        if not 0 <= metrics.romantic_interest <= 100:
            raise PersonaLoadError(
                "relationship baseline romantic_interest out of range"
            )
        result[target] = metrics
    return result


def _as_object(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        raise PersonaLoadError("Persona JSON root must be an object")

    raw = cast(dict[object, object], data)
    normalized: dict[str, object] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise PersonaLoadError("Persona JSON object keys must be strings")
        normalized[key] = value
    return normalized


def _expect_mapping(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise PersonaLoadError(f"Persona JSON field '{key}' must be an object")
    return _as_object(cast(object, value))


def _expect_list(data: dict[str, object], key: str) -> list[object]:
    value = data.get(key)
    if not isinstance(value, list):
        raise PersonaLoadError(f"Persona JSON field '{key}' must be a list")
    return cast(list[object], value)


def _expect_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise PersonaLoadError(f"Persona JSON field '{key}' must be a string")
    return value


def _expect_int(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise PersonaLoadError(f"Persona JSON field '{key}' must be an integer")
    return value


def _expect_string_list(data: dict[str, object], key: str) -> list[str]:
    values = _expect_list(data, key)
    result: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise PersonaLoadError(
                f"Persona JSON field '{key}' has non-string value at index {index}"
            )
        result.append(value)
    return result
