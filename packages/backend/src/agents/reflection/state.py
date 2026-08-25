from dataclasses import dataclass


@dataclass(frozen=True)
class ReflectionConfig:
    threshold: int = 150


class Reflection:
    def __init__(self, config: ReflectionConfig | None = None):
        self.config: ReflectionConfig = config or ReflectionConfig()
        self._accumulated_importance: int = 0

    @property
    def accumulated_importance(self) -> int:
        return self._accumulated_importance

    def record_observation_importance(self, importance: int) -> None:
        self._accumulated_importance += importance

    def clear_importance(self) -> None:
        self._accumulated_importance = 0

    def restore_importance(self, importance: int) -> None:
        if importance < 0:
            raise ValueError("accumulated importance must not be negative")
        self._accumulated_importance = importance

    def should_reflect(self) -> bool:
        return self._accumulated_importance >= self.config.threshold
