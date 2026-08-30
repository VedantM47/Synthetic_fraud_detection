from __future__ import annotations

from datetime import timedelta
import numpy as np
import pandas as pd

from data_generation import config
from data_generation.generate_customers import synthetic_uuid


def rounded_limit(value: int) -> int:
    return int(round(value / config.LIMIT_ROUNDING) * config.LIMIT_ROUNDING)


def account_dates(open_date: pd.Timestamp):
    dates = []
    event_date = open_date
    while event_date <= pd.Timestamp(config.SIMULATION_END_DATE):
        dates.append(event_date)
        event_date += timedelta(days=config.MONTH_DAYS)
    return dates


def event(rng: np.random.Generator, customer_id: str, date, event_type: str, limit: int, utilization: float) -> dict:
    return {
        "event_id": synthetic_uuid(rng),
        "customer_id": customer_id,
        "event_date": pd.Timestamp(date).date().isoformat(),
        "event_type": event_type,
        "credit_limit_at_time": limit,
        "utilization_pct": round(float(utilization), config.UTILIZATION_DECIMALS),
    }


def generate_legitimate_events(row: pd.Series, rng: np.random.Generator) -> list[dict]:
    customer_id = row["customer_id"]
    dates = account_dates(pd.Timestamp(row["account_open_date"]))
    limit = rounded_limit(int(rng.integers(config.BASE_CREDIT_LIMIT_MIN, config.BASE_CREDIT_LIMIT_MAX + 1)))
    utilization = float(rng.uniform(config.LEGIT_UTILIZATION_MIN, config.LEGIT_UTILIZATION_MAX))
    events = [event(rng, customer_id, dates[config.FIRST_EVENT_INDEX], "account_opened", limit, utilization)]

    for event_date in dates[1:]:
        if rng.random() < config.LEGIT_LIMIT_INCREASE_CHANCE:
            limit = rounded_limit(limit + int(rng.integers(config.LIMIT_INCREASE_MIN, config.LIMIT_INCREASE_MAX + 1)))
            events.append(event(rng, customer_id, event_date, "credit_limit_increase", limit, utilization))
        utilization = float(
            np.clip(
                utilization + rng.normal(config.FIRST_EVENT_INDEX, config.LEGIT_UTILIZATION_NOISE_STD),
                config.LEGIT_UTILIZATION_MIN,
                config.LEGIT_UTILIZATION_MAX,
            )
        )
        events.append(event(rng, customer_id, event_date + timedelta(days=int(rng.integers(config.EVENT_DAY_MIN, config.EVENT_DAY_WEEK_MAX + 1))), "purchase", limit, utilization))
        utilization = max(
            config.LEGIT_UTILIZATION_MIN,
            utilization - float(rng.uniform(config.LEGIT_PAYMENT_DROP_MIN, config.LEGIT_PAYMENT_DROP_MAX)),
        )
        events.append(event(rng, customer_id, event_date + timedelta(days=int(rng.integers(config.PAYMENT_DAY_MIN, config.PAYMENT_DAY_MAX + 1))), "payment", limit, utilization))
    return events


def generate_fraud_events(row: pd.Series, rng: np.random.Generator) -> list[dict]:
    customer_id = row["customer_id"]
    open_date = pd.Timestamp(row["account_open_date"])
    end_date = pd.Timestamp(config.SIMULATION_END_DATE)
    lifetime_days = max((end_date - open_date).days, config.MONTH_DAYS)
    bustout_start = open_date + timedelta(
        days=int(lifetime_days * rng.uniform(config.FRAUD_BUSTOUT_LIFETIME_MIN, config.FRAUD_BUSTOUT_LIFETIME_MAX))
    )
    normal_dates = [date for date in account_dates(open_date) if date < bustout_start]
    limit = rounded_limit(int(rng.integers(config.BASE_CREDIT_LIMIT_MIN, config.BASE_CREDIT_LIMIT_MAX + 1)))
    utilization = float(rng.uniform(config.FRAUD_NORMAL_UTILIZATION_MIN, config.FRAUD_NORMAL_UTILIZATION_MAX))
    events = [event(rng, customer_id, open_date, "account_opened", limit, utilization)]

    for event_date in normal_dates[1:]:
        if rng.random() < config.LEGIT_LIMIT_INCREASE_CHANCE:
            limit = rounded_limit(limit + int(rng.integers(config.LIMIT_INCREASE_MIN, config.LIMIT_INCREASE_MAX + 1)))
            events.append(event(rng, customer_id, event_date, "credit_limit_increase", limit, utilization))
        utilization = float(
            np.clip(
                utilization + rng.normal(config.FIRST_EVENT_INDEX, config.FRAUD_NORMAL_UTILIZATION_NOISE_STD),
                config.FRAUD_NORMAL_UTILIZATION_MIN,
                config.FRAUD_NORMAL_UTILIZATION_MAX,
            )
        )
        events.append(event(rng, customer_id, event_date + timedelta(days=int(rng.integers(config.EVENT_DAY_MIN, config.EVENT_DAY_WEEK_MAX + 1))), "purchase", limit, utilization))
        utilization = max(
            config.FRAUD_NORMAL_UTILIZATION_MIN,
            utilization - float(rng.uniform(config.LEGIT_PAYMENT_DROP_MIN, config.LEGIT_PAYMENT_DROP_MAX)),
        )
        events.append(event(rng, customer_id, event_date + timedelta(days=int(rng.integers(config.PAYMENT_DAY_MIN, config.PAYMENT_DAY_MAX + 1))), "payment", limit, utilization))

    purchase_count = int(
        rng.integers(config.FRAUD_BUSTOUT_PURCHASES_MIN, config.FRAUD_BUSTOUT_PURCHASES_MAX + 1)
    )
    for index in range(purchase_count):
        utilization = float(
            rng.uniform(config.FRAUD_BUSTOUT_UTILIZATION_MIN, config.FRAUD_BUSTOUT_UTILIZATION_MAX)
        )
        events.append(
            event(
                rng,
                customer_id,
                bustout_start
                + timedelta(days=index * int(rng.integers(config.FRAUD_BUSTOUT_EVENT_DAY_STEP_MIN, config.FRAUD_BUSTOUT_EVENT_DAY_STEP_MAX + 1))),
                "bust_out_spike",
                limit,
                utilization,
            )
        )
    events.append(
        event(
            rng,
            customer_id,
            bustout_start
            + timedelta(days=int(rng.integers(config.ACCOUNT_ABANDONMENT_DELAY_DAYS_MIN, config.ACCOUNT_ABANDONMENT_DELAY_DAYS_MAX + 1))),
            "account_closed_or_abandoned",
            limit,
            utilization,
        )
    )
    return events


def generate_temporal_events(customers: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for _, customer in customers.iterrows():
        if int(customer["is_synthetic_fraud"]) == config.FRAUD_LABEL:
            rows.extend(generate_fraud_events(customer, rng))
        else:
            rows.extend(generate_legitimate_events(customer, rng))
    return pd.DataFrame(rows).sort_values(["customer_id", "event_date"]).reset_index(drop=True)
