from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_generation import config
from data_generation.run_all import generate_all
from src.data.build_customer_graph import build_edge_records
from src.data.generate_red_flag_features import compute_features as compute_network_features
from src.data.generate_temporal_features import compute_temporal_features
from src.data.split_data import create_group_column, split_by_group


def test_generated_data_validation():
    data = generate_all()
    customers = data["customers"]
    links = data["links"]

    assert len(customers) == config.TOTAL_CUSTOMERS
    assert customers["is_synthetic_fraud"].eq(config.LEGITIMATE_LABEL).sum() == config.N_LEGITIMATE_CUSTOMERS
    assert customers["is_synthetic_fraud"].eq(config.FRAUD_LABEL).sum() == config.N_FRAUD_RING_CUSTOMERS
    assert customers["customer_id"].is_unique

    legitimate_ids = set(
        customers.loc[customers["is_synthetic_fraud"].eq(config.LEGITIMATE_LABEL), "customer_id"]
    )
    legitimate_links = links[links["customer_id"].isin(legitimate_ids)]
    for attribute_type in config.ATTRIBUTE_TYPES:
        typed = legitimate_links[legitimate_links["attribute_type"].eq(attribute_type)]
        assert typed["customer_id"].value_counts().eq(1).all()

    legitimate_shared_counts = legitimate_links.groupby(["attribute_type", "attribute_id"])["customer_id"].nunique()
    assert legitimate_shared_counts.gt(1).any()

    fraud = customers[customers["is_synthetic_fraud"].eq(config.FRAUD_LABEL)]
    ring_sizes = fraud.groupby("ring_id").size()
    assert ring_sizes.between(config.MIN_RING_SIZE, config.MAX_RING_SIZE).all()
    assert ring_sizes.sum() == config.N_FRAUD_RING_CUSTOMERS

    for ring_id, group in fraud.groupby("ring_id"):
        ring_links = links[links["customer_id"].isin(group["customer_id"])]
        shared_counts = ring_links.groupby(["attribute_type", "attribute_id"]).size()
        assert shared_counts.gt(1).any(), ring_id

    legitimate = customers[customers["is_synthetic_fraud"].eq(config.LEGITIMATE_LABEL)]
    for column, bins, max_mean_diff in [
        ("annual_income", config.INCOME_HISTOGRAM_BINS, config.MAX_MEAN_RELATIVE_DIFFERENCE),
        ("credit_score", config.CREDIT_SCORE_HISTOGRAM_BINS, config.MAX_MEAN_RELATIVE_DIFFERENCE),
    ]:
        legit_values = legitimate[column].to_numpy()
        fraud_values = fraud[column].to_numpy()
        mean_diff = abs(legit_values.mean() - fraud_values.mean()) / legit_values.mean()
        assert mean_diff < max_mean_diff
        edges = np.histogram_bin_edges(np.concatenate([legit_values, fraud_values]), bins=bins)
        legit_hist = np.histogram(legit_values, bins=edges, density=True)[0]
        fraud_hist = np.histogram(fraud_values, bins=edges, density=True)[0]
        total_variation = np.abs(legit_hist - fraud_hist).sum() / len(legit_hist)
        assert total_variation < config.MAX_HISTOGRAM_TOTAL_VARIATION

    all_attribute_ids = set()
    for name, id_column in [
        ("phones", "phone_id"),
        ("emails", "email_id"),
        ("addresses", "address_id"),
        ("devices", "device_id"),
    ]:
        all_attribute_ids.update(data[name][id_column])
    assert set(links["customer_id"]).issubset(set(customers["customer_id"]))
    assert set(links["attribute_id"]).issubset(all_attribute_ids)

    assert set(data["ring_ground_truth"]["customer_id"]) == set(fraud["customer_id"])
    assert set(data["events"]["customer_id"]) == set(customers["customer_id"])


def test_week3_pipeline_leakage_reproducibility_and_outputs(tmp_path):
    first = generate_all()
    second = generate_all()
    pd.testing.assert_frame_equal(first["customers"], second["customers"])
    pd.testing.assert_frame_equal(first["links"], second["links"])
    pd.testing.assert_frame_equal(first["events"], second["events"])

    customers = create_group_column(first["customers"].copy())
    train, test = split_by_group(customers, seed=config.RANDOM_SEED)
    assert set(train["customer_id"]).isdisjoint(set(test["customer_id"]))
    train_rings = set(train.loc[train["is_synthetic_fraud"].eq(1), "ring_id"].dropna())
    test_rings = set(test.loc[test["is_synthetic_fraud"].eq(1), "ring_id"].dropna())
    assert train_rings.isdisjoint(test_rings)

    edges = build_edge_records(first["links"])
    network_features = compute_network_features(edges)
    temporal_features = compute_temporal_features(first["events"])

    forbidden = {"is_synthetic_fraud", "ring_id", "group_id"}
    assert forbidden.isdisjoint(network_features.columns)
    assert forbidden.isdisjoint(temporal_features.columns)
    assert len(temporal_features) == len(customers)
    assert network_features["network_degree"].ge(0).all()
    assert network_features["shared_attribute_count"].ge(0).all()
    assert temporal_features["total_event_count"].ge(1).all()
    assert temporal_features["max_utilization_pct"].between(0, 1).all()

    train_path = tmp_path / "train.csv"
    test_path = tmp_path / "test.csv"
    network_path = tmp_path / "network.csv"
    temporal_path = tmp_path / "temporal.csv"
    out_dir = tmp_path / "outputs"
    train.to_csv(train_path, index=False)
    test.to_csv(test_path, index=False)
    network_features.to_csv(network_path, index=False)
    temporal_features.to_csv(temporal_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.models.random_forest_baseline",
            "--train",
            str(train_path),
            "--test",
            str(test_path),
            "--features",
            str(network_path),
            "--temporal-features",
            str(temporal_path),
            "--output-dir",
            str(out_dir),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    metrics = pd.read_csv(out_dir / "model_metrics.csv")
    assert {"accuracy", "precision", "recall", "f1", "roc_auc", "tn", "fp", "fn", "tp"}.issubset(metrics.columns)
    assert len(metrics) == 8
    assert list(out_dir.glob("*_predictions.csv"))
    assert (out_dir / "rf_metrics_report.txt").is_file()
