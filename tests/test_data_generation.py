from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_generation import config
from data_generation.run_all import generate_all


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
        assert typed["attribute_id"].is_unique

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

