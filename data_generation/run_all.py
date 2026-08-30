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

