"""Route a battery sample to the right shared or chemistry-specific model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    key: str
    battery_types: list[str]
    kind: str
    target: str
    feature_contract: str
    artifact_path: str
    status: str
    base_model_key: str | None = None

    @classmethod
    def from_config(cls, key: str, raw: dict[str, Any]) -> "ModelSpec":
        return cls(
            key=key,
            battery_types=list(raw.get("battery_types", [])),
            kind=str(raw["kind"]),
            target=str(raw["target"]),
            feature_contract=str(raw["feature_contract"]),
            artifact_path=str(raw["artifact_path"]),
            status=str(raw.get("status", "unknown")),
            base_model_key=raw.get("base_model_key"),
        )

    def supports(self, battery_type: str) -> bool:
        normalized = battery_type.lower()
        return "*" in self.battery_types or normalized in {
            value.lower() for value in self.battery_types
        }


class ModelRegistry:
    def __init__(self, default_model_key: str, models: dict[str, ModelSpec]) -> None:
        if default_model_key not in models:
            raise ValueError(f"Default model {default_model_key!r} is not registered.")
        self.default_model_key = default_model_key
        self.models = models

    @classmethod
    def load(cls, path: Path) -> "ModelRegistry":
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        models = {
            key: ModelSpec.from_config(key, value)
            for key, value in raw.get("models", {}).items()
        }
        return cls(default_model_key=str(raw["default_model_key"]), models=models)

    def resolve(self, battery_type: str) -> ModelSpec:
        normalized = battery_type.lower()
        candidates = [
            spec
            for spec in self.models.values()
            if spec.supports(normalized) and "*" not in spec.battery_types
        ]
        if candidates:
            return sorted(candidates, key=lambda spec: spec.status != "prototype")[0]
        return self.models[self.default_model_key]

    def fallback_chain(self, battery_type: str) -> list[ModelSpec]:
        primary = self.resolve(battery_type)
        chain = [primary]
        current = primary
        while current.base_model_key:
            current = self.models[current.base_model_key]
            chain.append(current)
        if chain[-1].key != self.default_model_key:
            chain.append(self.models[self.default_model_key])
        return chain
