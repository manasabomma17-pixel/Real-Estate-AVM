from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DatasetConfig:
    version: str
    primary_market: str
    secondary_market: str
    date_range: list[str]


@dataclass
class SplitConfig:
    type: str
    test_size: float


@dataclass
class ModelConfig:
    type: str
    hyperparameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationConfig:
    metrics: list[str]
    compute_prediction_intervals: bool = False


@dataclass
class ExperimentConfig:
    experiment_name: str
    random_seed: int
    feature_set: str
    dataset: DatasetConfig
    split: SplitConfig
    model: ModelConfig
    evaluation: EvaluationConfig


def load_config(path: str | Path) -> ExperimentConfig:
    path = Path(path)
    with path.open("r") as f:
        raw = yaml.safe_load(f)

    return ExperimentConfig(
        experiment_name=raw["experiment_name"],
        random_seed=raw["random_seed"],
        feature_set=raw["feature_set"],
        dataset=DatasetConfig(**raw["dataset"]),
        split=SplitConfig(**raw["split"]),
        model=ModelConfig(**raw["model"]),
        evaluation=EvaluationConfig(**raw["evaluation"]),
    )
