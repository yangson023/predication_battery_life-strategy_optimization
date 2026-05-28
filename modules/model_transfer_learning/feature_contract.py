"""Common feature contract for shared and chemistry-specific battery models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd


COMMON_CYCLE_FEATURES = [
    "discharge_cycle",
    "available_discharge_history_cycles",
    "capacity_ah",
    "soh_capacity_ratio",
    "capacity_loss_ratio",
    "capacity_change_previous_ah",
    "soh_change_previous",
    "capacity_rolling_mean_5_ah",
    "capacity_rolling_std_5_ah",
    "capacity_slope_5_ah_per_cycle",
    "soh_slope_5_per_cycle",
    "capacity_rolling_mean_10_ah",
    "capacity_rolling_std_10_ah",
    "capacity_slope_10_ah_per_cycle",
    "soh_slope_10_per_cycle",
    "discharge_duration_s",
    "discharge_voltage_measured_v_min",
    "discharge_voltage_measured_v_max",
    "discharge_voltage_measured_v_mean",
    "discharge_current_measured_a_mean",
    "discharge_temperature_measured_c_max",
    "discharge_temperature_measured_c_mean",
    "latest_charge_duration_s",
    "latest_charge_voltage_measured_v_mean",
    "latest_charge_current_measured_a_mean",
    "latest_charge_temperature_measured_c_mean",
    "latest_impedance_re_ohm",
    "latest_impedance_rct_ohm",
    "cycles_since_latest_charge",
    "cycles_since_latest_impedance",
]

REQUIRED_METADATA_COLUMNS = [
    "dataset",
    "battery_type",
    "cell_id",
    "cycle_index",
]


@dataclass(frozen=True)
class FeatureContract:
    name: str
    feature_columns: list[str]
    required_metadata_columns: list[str] = field(
        default_factory=lambda: REQUIRED_METADATA_COLUMNS.copy()
    )

    @property
    def required_columns(self) -> list[str]:
        return self.required_metadata_columns + self.feature_columns

    def missing_columns(self, columns: Iterable[str]) -> list[str]:
        existing = set(columns)
        return [column for column in self.required_columns if column not in existing]

    def validate(self, frame: pd.DataFrame) -> None:
        missing = self.missing_columns(frame.columns)
        if missing:
            raise ValueError(
                f"Feature contract {self.name!r} is missing columns: {missing}"
            )

    def select_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        self.validate(frame)
        return frame.loc[:, self.feature_columns].copy()


COMMON_CYCLE_V1 = FeatureContract(
    name="common_cycle_v1",
    feature_columns=COMMON_CYCLE_FEATURES,
)
