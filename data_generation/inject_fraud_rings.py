from __future__ import annotations

import numpy as np
import pandas as pd
from faker import Faker

from data_generation import config
from data_generation.generate_customers import generate_customer_profile
from data_generation.generate_identity_attributes import (
    create_attribute_bundle,
    link_customer,
)


def sample_ring_sizes(rng: np.random.Generator) -> list[int]:
    sizes = np.array(list(config.RING_SIZE_DISTRIBUTION.keys()))
    probabilities = np.array(list(config.RING_SIZE_DISTRIBUTION.values()), dtype=float)
    probabilities = probabilities / probabilities.sum()
    result = []
    remaining = config.N_FRAUD_RING_CUSTOMERS
    while remaining:
        allowed = sizes[sizes <= remaining]
        allowed_probabilities = probabilities[: len(allowed)]
        allowed_probabilities = allowed_probabilities / allowed_probabilities.sum()
        size = int(rng.choice(allowed, p=allowed_probabilities))
        if remaining - size == 1:
            size += 1
        result.append(size)
        remaining -= size
    return result


def generate_fraud_rings(fake: Faker, rng: np.random.Generator):
    fraud_customers = []
    tables = {attribute_type: [] for attribute_type in config.ATTRIBUTE_TYPES}
    links = []
    ground_truth = []

    for ring_number, ring_size in enumerate(sample_ring_sizes(rng), start=config.RING_NUMBER_START):
        ring_id = f"{config.RING_ID_PREFIX}_{ring_number:0{config.RING_ID_WIDTH}d}"
        shared_types = rng.choice(
            config.ATTRIBUTE_TYPES,
            size=int(
                rng.integers(
                    config.MIN_SHARED_ATTRIBUTES_PER_RING,
                    config.MAX_SHARED_ATTRIBUTES_PER_RING + 1,
                )
            ),
            replace=False,
        )
        ring_customers = [
            generate_customer_profile(fake, rng, config.FRAUD_LABEL, ring_id)
            for _ in range(ring_size)
        ]
        shared_bundle = create_attribute_bundle(fake, rng, ring_customers[0]["customer_id"])
        sharing_probability = float(
            rng.uniform(
                config.FRAUD_MEMBER_SHARED_ATTRIBUTE_MIN_PROB,
                config.FRAUD_MEMBER_SHARED_ATTRIBUTE_MAX_PROB,
            )
        )
        anchor_shared_type = str(rng.choice(shared_types))

        for index, customer in enumerate(ring_customers):
            bundle = create_attribute_bundle(fake, rng, customer["customer_id"])
            for attribute_type in shared_types:
                if index < 2 and attribute_type == anchor_shared_type:
                    bundle[attribute_type] = shared_bundle[attribute_type]
                elif index == 0 or rng.random() < sharing_probability:
                    bundle[attribute_type] = shared_bundle[attribute_type]
            for attribute_type, value in bundle.items():
                if value not in tables[attribute_type]:
                    tables[attribute_type].append(value)
            links.extend(link_customer(customer["customer_id"], bundle))
            fraud_customers.append(customer)
            ground_truth.append({"ring_id": ring_id, "customer_id": customer["customer_id"]})

    return (
        pd.DataFrame(fraud_customers),
        pd.DataFrame(tables["phone"]),
        pd.DataFrame(tables["email"]),
        pd.DataFrame(tables["address"]),
        pd.DataFrame(tables["device"]),
        pd.DataFrame(links),
        pd.DataFrame(ground_truth),
    )
