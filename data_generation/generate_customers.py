from __future__ import annotations

from datetime import timedelta
import numpy as np
import pandas as pd
from faker import Faker

from data_generation import config


def make_rng(seed: int = config.RANDOM_SEED) -> np.random.Generator:
    Faker.seed(seed)
    return np.random.default_rng(seed)


def make_faker(seed: int = config.RANDOM_SEED) -> Faker:
    fake = Faker("en_US")
    fake.seed_instance(seed)
    return fake


def random_date(rng: np.random.Generator, start, end):
    days = (end - start).days
    return start + timedelta(days=int(rng.integers(config.FIRST_EVENT_INDEX, days + 1)))


def synthetic_uuid(rng: np.random.Generator) -> str:
    hex_value = rng.bytes(config.UUID_BYTE_LENGTH).hex()
    groups = []
    cursor = config.FIRST_EVENT_INDEX
    for length in config.UUID_GROUP_LENGTHS:
        groups.append(hex_value[cursor : cursor + length])
        cursor += length
    return "-".join(groups)


def random_birth_date(rng: np.random.Generator):
    age = int(
        np.clip(
            rng.normal(config.AGE_MEAN, config.AGE_STD_DEV),
            config.MIN_AGE,
            config.MAX_AGE,
        )
    )
    days_offset = int(rng.integers(config.FIRST_EVENT_INDEX, config.DOB_JITTER_DAYS))
    return config.SIMULATION_END_DATE - timedelta(days=age * config.DAYS_PER_YEAR + days_offset)


def generate_ssn_like_id(rng: np.random.Generator) -> str:
    first = int(rng.integers(config.SYNTHETIC_SSN_PART_1_MIN, config.SYNTHETIC_SSN_PART_1_MAX + 1))
    second = int(rng.integers(config.SYNTHETIC_SSN_PART_2_MIN, config.SYNTHETIC_SSN_PART_2_MAX + 1))
    third = int(rng.integers(config.SYNTHETIC_SSN_PART_3_MIN, config.SYNTHETIC_SSN_PART_3_MAX + 1))
    return f"{config.SSN_PREFIX}-{first:03d}-{second:02d}-{third:04d}"


def generate_customer_profile(fake: Faker, rng: np.random.Generator, is_fraud: int, ring_id: str):
    open_date = random_date(rng, config.SIMULATION_START_DATE, config.SIMULATION_END_DATE)
    income = int(
        np.clip(
            rng.lognormal(config.INCOME_LOG_MEAN, config.INCOME_LOG_SIGMA),
            config.MIN_ANNUAL_INCOME,
            config.MAX_ANNUAL_INCOME,
        )
    )
    score = int(
        np.clip(
            rng.normal(config.CREDIT_SCORE_MEAN, config.CREDIT_SCORE_STD_DEV),
            config.MIN_CREDIT_SCORE,
            config.MAX_CREDIT_SCORE,
        )
    )
    return {
        "customer_id": synthetic_uuid(rng),
        "full_name": fake.name(),
        "date_of_birth": random_birth_date(rng).isoformat(),
        "ssn_like_id": generate_ssn_like_id(rng),
        "annual_income": income,
        "credit_score": score,
        "account_open_date": open_date.isoformat(),
        "account_tenure_days": (config.SIMULATION_END_DATE - open_date).days,
        "is_synthetic_fraud": is_fraud,
        "ring_id": ring_id,
    }


def generate_legitimate_customers(fake: Faker, rng: np.random.Generator) -> pd.DataFrame:
    rows = [
        generate_customer_profile(fake, rng, config.LEGITIMATE_LABEL, config.NO_RING_ID)
        for _ in range(config.N_LEGITIMATE_CUSTOMERS)
    ]
    return pd.DataFrame(rows)
