import argparse
from pathlib import Path

import numpy as np
import pandas as pd


TEMPORAL_FEATURE_COLUMNS = [
    "total_event_count",
    "purchase_count",
    "payment_count",
    "limit_increase_count",
    "distinct_event_dates",
    "event_span_days",
    "events_per_30_days",
    "max_events_single_day",
    "max_events_7d",
    "min_days_between_events",
    "mean_days_between_events",
    "mean_utilization_pct",
    "max_utilization_pct",
    "utilization_range",
    "max_credit_limit",
]
WINDOW_DAYS = 7


def compute_temporal_features(events: pd.DataFrame) -> pd.DataFrame:
    """Aggregate account events into one row of behaviour features per customer.

    Expected columns: ``customer_id``, ``event_date``, ``event_type``,
    ``utilization_pct`` and ``credit_limit_at_time``. Dates are compared at
    day granularity. Rows are returned sorted by ``customer_id``.

    The computation is vectorised across customers so it scales to large
    uploaded event logs.
    """
    if events.empty:
        return pd.DataFrame(columns=["customer_id", *TEMPORAL_FEATURE_COLUMNS])

    timestamp = pd.to_datetime(events["event_date"])
    frame = pd.DataFrame(
        {
            "customer_id": events["customer_id"].to_numpy(),
            "timestamp": timestamp.to_numpy(),
            "day": (timestamp.dt.normalize() - pd.Timestamp("1970-01-01")).dt.days.astype("int64").to_numpy(),
            "event_type": events["event_type"].to_numpy(),
            "utilization_pct": events["utilization_pct"].to_numpy(dtype=float),
            "credit_limit_at_time": events["credit_limit_at_time"].to_numpy(),
        }
    )
    # Chronological first, then a stable sort by customer: every customer's
    # events are contiguous and in time order (ties keep the chronological
    # sort's order, so float sums match a per-customer loop exactly).
    frame = frame.sort_values("timestamp").sort_values("customer_id", kind="mergesort").reset_index(drop=True)
    grouped = frame.groupby("customer_id", sort=True)
    features = pd.DataFrame(index=grouped.size().index)

    total = grouped.size()
    span = (grouped["day"].max() - grouped["day"].min()).clip(lower=1)
    features["total_event_count"] = total
    for column, event_type in [
        ("purchase_count", "purchase"),
        ("payment_count", "payment"),
        ("limit_increase_count", "credit_limit_increase"),
    ]:
        features[column] = frame["event_type"].eq(event_type).groupby(frame["customer_id"]).sum()

    per_day = frame.groupby(["customer_id", "day"], sort=True).size()
    features["distinct_event_dates"] = per_day.groupby(level=0).size()
    features["event_span_days"] = span
    features["events_per_30_days"] = total / span * 30
    features["max_events_single_day"] = per_day.groupby(level=0).max()

    # Events in the window [day, day + 6] starting at each event, using one
    # sorted key per (customer, day) so a single searchsorted covers everyone.
    customer_code = grouped.ngroup().to_numpy(dtype="int64")
    relative_day = frame["day"].to_numpy() - frame["day"].min()
    stride = int(relative_day.max()) + WINDOW_DAYS + 1
    keys = customer_code * stride + relative_day
    window_counts = np.searchsorted(keys, keys + WINDOW_DAYS - 1, side="right") - np.searchsorted(
        keys, keys, side="left"
    )
    features["max_events_7d"] = pd.Series(window_counts).groupby(frame["customer_id"]).max()

    same_customer = frame["customer_id"].eq(frame["customer_id"].shift())
    gaps = frame["day"].diff()[same_customer].astype(float)
    gap_owner = frame.loc[same_customer, "customer_id"]
    features["min_days_between_events"] = gaps.groupby(gap_owner).min().reindex(features.index).fillna(span)
    features["mean_days_between_events"] = gaps.groupby(gap_owner).mean().reindex(features.index).fillna(span)

    utilization = grouped["utilization_pct"]
    # np.sum per contiguous block uses the same pairwise summation as
    # Series.mean, keeping results bit-identical to the original per-customer
    # implementation (grouped means use a different summation order).
    boundaries = np.flatnonzero(~same_customer.to_numpy())[1:]
    blocks = np.split(frame["utilization_pct"].to_numpy(), boundaries)
    features["mean_utilization_pct"] = [block.sum() / len(block) for block in blocks]
    features["max_utilization_pct"] = utilization.max()
    features["utilization_range"] = utilization.max() - utilization.min()
    features["max_credit_limit"] = grouped["credit_limit_at_time"].max()

    integer_columns = [
        "total_event_count",
        "purchase_count",
        "payment_count",
        "limit_increase_count",
        "distinct_event_dates",
        "event_span_days",
        "max_events_single_day",
        "max_events_7d",
        "min_days_between_events",
        "max_credit_limit",
    ]
    features[integer_columns] = features[integer_columns].astype("int64")
    float_columns = [column for column in TEMPORAL_FEATURE_COLUMNS if column not in integer_columns]
    features[float_columns] = features[float_columns].astype(float)
    features.index.name = "customer_id"
    return features.reset_index()[["customer_id", *TEMPORAL_FEATURE_COLUMNS]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate customer-level temporal behavior features.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parents[2] / "data" / "raw" / "events.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parents[2] / "data" / "processed" / "customer_temporal_features.csv",
    )
    args = parser.parse_args()
    features = compute_temporal_features(pd.read_csv(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output, index=False)
    print(f"Saved temporal features to {args.output}")


if __name__ == "__main__":
    main()
