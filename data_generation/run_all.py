from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_generation import config
from data_generation.generate_customers import generate_legitimate_customers, make_faker, make_rng
from data_generation.generate_identity_attributes import generate_unique_attributes
from data_generation.generate_temporal_events import generate_temporal_events
from data_generation.inject_fraud_rings import generate_fraud_rings


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def write_csv(name: str, frame: pd.DataFrame) -> None:
    frame.to_csv(RAW_DIR / config.OUTPUT_FILES[name], index=False)


def add_fraud_legitimate_overlap(links: pd.DataFrame, customers: pd.DataFrame, rng) -> pd.DataFrame:
    fraud_ids = customers.loc[customers["is_synthetic_fraud"].eq(config.FRAUD_LABEL), "customer_id"].to_numpy()
    legit_ids = customers.loc[customers["is_synthetic_fraud"].eq(config.LEGITIMATE_LABEL), "customer_id"].to_numpy()
    overlap_count = int(len(fraud_ids) * config.FRAUD_LEGITIMATE_OVERLAP_FRACTION)
    if overlap_count == 0:
        return links

    fraud_sample = rng.choice(fraud_ids, size=overlap_count, replace=False)
    legit_sample = rng.choice(legit_ids, size=overlap_count, replace=False)
    for fraud_id, legit_id in zip(fraud_sample, legit_sample):
        attribute_type = str(rng.choice(config.FRAUD_LEGITIMATE_OVERLAP_TYPES))
        legit_attr = links.loc[
            links["customer_id"].eq(legit_id) & links["attribute_type"].eq(attribute_type),
            "attribute_id",
        ].iloc[0]
        links.loc[
            links["customer_id"].eq(fraud_id) & links["attribute_type"].eq(attribute_type),
            "attribute_id",
        ] = legit_attr
    return links


def ensure_minimum_ring_sharing(links: pd.DataFrame, ring_ground_truth: pd.DataFrame) -> pd.DataFrame:
    for _, group in ring_ground_truth.groupby("ring_id"):
        customer_ids = group["customer_id"].tolist()
        ring_links = links[links["customer_id"].isin(customer_ids)]
        shared = ring_links.groupby(["attribute_type", "attribute_id"]).size().gt(1).any()
        if shared or len(customer_ids) < 2:
            continue
        first, second = customer_ids[:2]
        shared_id = links.loc[
            links["customer_id"].eq(first) & links["attribute_type"].eq("address"),
            "attribute_id",
        ].iloc[0]
        links.loc[
            links["customer_id"].eq(second) & links["attribute_type"].eq("address"),
            "attribute_id",
        ] = shared_id
    return links


def generate_all() -> dict[str, pd.DataFrame]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rng = make_rng()
    fake = make_faker()

    legitimate_customers = generate_legitimate_customers(fake, rng)
    legitimate_tables = generate_unique_attributes(legitimate_customers, fake, rng)
    fraud_tables = generate_fraud_rings(fake, rng)

    customers = pd.concat([legitimate_customers, fraud_tables[0]], ignore_index=True)
    phones = pd.concat([legitimate_tables[0], fraud_tables[1]], ignore_index=True)
    emails = pd.concat([legitimate_tables[1], fraud_tables[2]], ignore_index=True)
    addresses = pd.concat([legitimate_tables[2], fraud_tables[3]], ignore_index=True)
    devices = pd.concat([legitimate_tables[3], fraud_tables[4]], ignore_index=True)
    links = pd.concat([legitimate_tables[4], fraud_tables[5]], ignore_index=True)
    ring_ground_truth = fraud_tables[6]

    customers = customers.sample(frac=1, random_state=config.RANDOM_SEED).reset_index(drop=True)
    links = add_fraud_legitimate_overlap(links, customers, rng)
    links = ensure_minimum_ring_sharing(links, ring_ground_truth)
    events = generate_temporal_events(customers, rng)

    output = {
        "customers": customers,
        "phones": phones,
        "emails": emails,
        "addresses": addresses,
        "devices": devices,
        "links": links,
        "events": events,
        "ring_ground_truth": ring_ground_truth,
    }
    for name, frame in output.items():
        write_csv(name, frame)
    return output


if __name__ == "__main__":
    generated = generate_all()
    for name, frame in generated.items():
        print(f"{config.OUTPUT_FILES[name]}: {len(frame)} rows")
