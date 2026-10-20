"""일정 원형 JSON 로더. `{home}`·`{bedroom}` 같은 자리표시자를 주민별 장소로 치환한다."""

import json
import re
from pathlib import Path
from typing import Any

from .config import ScheduleConfig

_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


def default_archetype_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "residents" / "archetypes"


def load_archetype(
    name: str,
    *,
    placeholders: dict[str, str],
    directory: Path | None = None,
) -> ScheduleConfig:
    """`<directory>/<name>.json`을 읽고 `{key}`를 `placeholders[key]`로 바꿔 검증한다."""
    path = (directory or default_archetype_dir()) / f"{name}.json"
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    config = ScheduleConfig.model_validate(_substitute(raw, placeholders))
    for entry in config.entries:
        left = _PLACEHOLDER.search(entry.location_path)
        if left:
            raise ValueError(f"unresolved placeholder {left.group(0)} in {name}")
    return config


def _substitute(value: Any, placeholders: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, replacement in placeholders.items():
            value = value.replace("{" + key + "}", replacement)
        return value
    if isinstance(value, list):
        return [_substitute(item, placeholders) for item in value]
    if isinstance(value, dict):
        return {k: _substitute(v, placeholders) for k, v in value.items()}
    return value
