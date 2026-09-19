"""Synthetic reference dataset used to score uploads that have no labels.

The reference is the canonical synthetic dataset (seed 42, 8,800 customers).
Its network features are recomputed with exactly the attribute types the
upload provides, so the transfer model learns from the same feature
definitions it is later applied to.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

from backend import settings
from backend.pipeline.features import GraphResult, build_graph, network_features, temporal_features
from backend.pipeline.ingest import CanonicalData, canonical_from_generated
from backend.pipeline.modeling import best_f1_threshold, scoring_model
from data_generation import config as generation_config
from data_generation.run_all import generate_all

_LOCK = threading.Lock()
_CACHE: dict[str, object] = {}

VALUE_TABLES = {
    "phones": "phones.csv",
    "emails": "emails.csv",
    "addresses": "addresses.csv",
    "devices": "devices.csv",
}


def _load_generated(reference_dir: Path, progress: Callable[[str], None]) -> dict[str, pd.DataFrame]:
    files = generation_config.OUTPUT_FILES
    if not all((reference_dir / name).is_file() for name in files.values()):
        progress("Generating the synthetic reference dataset (first run only)")
        return generate_all(out_dir=reference_dir)
    return {key: pd.read_csv(reference_dir / name, dtype=str, keep_default_na=False) for key, name in files.items()}


def _typed(generated: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Restore numeric dtypes after reading the CSVs as strings."""
    customers = generated["customers"].copy()
    for column in ["annual_income", "credit_score", "account_tenure_days", "is_synthetic_fraud"]:
        customers[column] = pd.to_numeric(customers[column])
    customers["ring_id"] = customers["ring_id"].replace("", np.nan)
    events = generated["events"].copy()
    events["utilization_pct"] = pd.to_numeric(events["utilization_pct"])
    events["credit_limit_at_time"] = pd.to_numeric(events["credit_limit_at_time"])
    return {**generated, "customers": customers, "events": events}


class Reference:
    def __init__(self, data: CanonicalData, graph: GraphResult, temporal: pd.DataFrame):
        self.data = data
        self.graph = graph
        self.temporal = temporal
        self.labels = data.customers["label"].astype(int)
        self.groups = data.customers["truth_ring"].where(data.customers["truth_ring"] != "", data.customers["customer_id"])
        self._models: dict[tuple, dict] = {}

    def features(self, count_types: list[str], degree_types: list[str], temporal_columns: list[str]) -> pd.DataFrame:
        network = network_features(self.data.customers["customer_id"], self.graph.edges, degree_types=degree_types)
        columns = [f"{kind}_shared_count" for kind in count_types] + ["network_degree", "shared_attribute_count"]
        frame = network[["customer_id", *columns]].merge(
            self.temporal[["customer_id", *temporal_columns]], on="customer_id", how="left"
        )
        return frame.drop(columns=["customer_id"]).reset_index(drop=True)

    def calibration(self, key: tuple, X: pd.DataFrame) -> dict:
        """Out-of-fold threshold and ROC-AUC on the reference for this feature set."""
        with _LOCK:
            if key in self._models:
                return self._models[key]
        y = self.labels.to_numpy()
        oof = np.zeros(len(X))
        cv = StratifiedGroupKFold(n_splits=settings.CV_FOLDS, shuffle=True, random_state=settings.RANDOM_SEED)
        for train_index, test_index in cv.split(X, y, self.groups):
            model = scoring_model().fit(X.iloc[train_index], y[train_index])
            oof[test_index] = model.predict_proba(X.iloc[test_index])[:, 1]
        result = {"threshold": best_f1_threshold(y, oof), "roc_auc": float(roc_auc_score(y, oof))}
        with _LOCK:
            self._models[key] = result
        return result


def get_reference(reference_dir: Path, progress: Callable[[str], None] = lambda message: None) -> Reference:
    key = str(Path(reference_dir).resolve())
    with _LOCK:
        cached = _CACHE.get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    progress("Loading the synthetic reference dataset")
    generated = _typed(_load_generated(Path(reference_dir), progress))
    data = canonical_from_generated(generated)
    graph = build_graph(data, max_group_size=settings.MAX_ATTRIBUTE_GROUP_SIZE)
    temporal, _ = temporal_features(data)
    reference = Reference(data, graph, temporal)
    with _LOCK:
        _CACHE[key] = reference
    return reference
