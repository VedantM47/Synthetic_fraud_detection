from __future__ import annotations

import numpy as np
import pandas as pd
from faker import Faker

from data_generation import config
from data_generation.generate_customers import synthetic_uuid


def new_attribute_id(attribute_type: str, rng: np.random.Generator) -> str:
    return f"{attribute_type}_{synthetic_uuid(rng).replace('-', '')[: config.ID_HEX_LENGTH]}"


def new_phone(fake: Faker, rng: np.random.Generator) -> dict:
    phone_number = fake.msisdn()
    return {
        "phone_id": new_attribute_id("phone", rng),
        "phone_number": (
            f"{config.PHONE_PREFIX}-"
            f"{phone_number[config.PHONE_MIDDLE_SLICE_START: config.PHONE_MIDDLE_SLICE_END]}-"
            f"{phone_number[config.PHONE_LAST_SLICE_START:]}"
        ),
    }


def new_email(customer_id: str, rng: np.random.Generator) -> dict:
    return {
        "email_id": new_attribute_id("email", rng),
        "email_address": f"{customer_id[: config.ID_HEX_LENGTH].lower()}@example.test",
    }


def new_address(fake: Faker, rng: np.random.Generator) -> dict:
    return {
        "address_id": new_attribute_id("address", rng),
        "street": fake.street_address().replace("\n", " "),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "zip": str(int(rng.integers(config.ZIP_MIN, config.ZIP_MAX + 1))),
    }


def new_device(rng: np.random.Generator) -> dict:
    return {
        "device_id": new_attribute_id("device", rng),
        "device_fingerprint": rng.bytes(config.DEVICE_BYTE_LENGTH).hex(),
    }


def create_attribute_bundle(fake: Faker, rng: np.random.Generator, customer_id: str) -> dict:
    return {
        "phone": new_phone(fake, rng),
        "email": new_email(customer_id, rng),
        "address": new_address(fake, rng),
        "device": new_device(rng),
    }


def link_customer(customer_id: str, bundle: dict) -> list[dict]:
    return [
        {
            "customer_id": customer_id,
            "attribute_type": attribute_type,
            "attribute_id": value[f"{attribute_type}_id"],
        }
        for attribute_type, value in bundle.items()
    ]


def share_attribute(links: pd.DataFrame, group, attribute_type: str) -> None:
    anchor = group[0]
    shared_id = links.loc[
        links["customer_id"].eq(anchor) & links["attribute_type"].eq(attribute_type),
        "attribute_id",
    ].iloc[0]
    links.loc[
        links["customer_id"].isin(group[1:]) & links["attribute_type"].eq(attribute_type),
        "attribute_id",
    ] = shared_id


def add_benign_shared_attributes(links: pd.DataFrame, customers: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    customer_ids = rng.permutation(customers["customer_id"].to_numpy())
    household_count = int(len(customers) * config.BENIGN_HOUSEHOLD_CUSTOMER_FRACTION)
    cursor = 0

    while cursor + config.BENIGN_HOUSEHOLD_MIN_SIZE <= household_count:
        remaining = household_count - cursor
        size = int(
            min(
                rng.integers(config.BENIGN_HOUSEHOLD_MIN_SIZE, config.BENIGN_HOUSEHOLD_MAX_SIZE + 1),
                remaining,
            )
        )
        if size < config.BENIGN_HOUSEHOLD_MIN_SIZE:
            break
        group = customer_ids[cursor : cursor + size]
        cursor += size
        share_attribute(links, group, "address")
        if rng.random() < config.BENIGN_HOUSEHOLD_SHARED_PHONE_PROB:
            share_attribute(links, group, "phone")
        if rng.random() < config.BENIGN_HOUSEHOLD_SHARED_DEVICE_PROB:
            share_attribute(links, group, "device")

    contact_count = int(len(customers) * config.BENIGN_CONTACT_CUSTOMER_FRACTION)
    contact_count -= contact_count % config.BENIGN_CONTACT_GROUP_SIZE
    for start in range(cursor, cursor + contact_count, config.BENIGN_CONTACT_GROUP_SIZE):
        group = customer_ids[start : start + config.BENIGN_CONTACT_GROUP_SIZE]
        if len(group) == config.BENIGN_CONTACT_GROUP_SIZE:
            share_attribute(links, group, "phone")
    return links


def generate_unique_attributes(customers: pd.DataFrame, fake: Faker, rng: np.random.Generator):
    tables = {attribute_type: [] for attribute_type in config.ATTRIBUTE_TYPES}
    links = []
    for customer_id in customers["customer_id"]:
        bundle = create_attribute_bundle(fake, rng, customer_id)
        for attribute_type, value in bundle.items():
            tables[attribute_type].append(value)
        links.extend(link_customer(customer_id, bundle))
    links_df = add_benign_shared_attributes(pd.DataFrame(links), customers, rng)
    return (
        pd.DataFrame(tables["phone"]),
        pd.DataFrame(tables["email"]),
        pd.DataFrame(tables["address"]),
        pd.DataFrame(tables["device"]),
        links_df,
    )
