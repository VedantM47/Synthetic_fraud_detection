import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def compute_temporal_features(events: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    events["event_date"] = pd.to_datetime(events["event_date"])
    rows = []
    for customer_id, group in events.sort_values("event_date").groupby("customer_id"):
        dates = group["event_date"]
        date_values = dates.to_numpy(dtype="datetime64[ns]")
        day_counts = dates.dt.date.value_counts()
        gaps = dates.diff().dt.days.dropna()
        window_counts = [
            int(((date_values >= date) & (date_values <= date + np.timedelta64(6, "D"))).sum())
            for date in date_values
        ]
        span_days = max(int((dates.max() - dates.min()).days), 1)
        rows.append(
            {
                "customer_id": customer_id,
                "total_event_count": len(group),
                "purchase_count": int(group["event_type"].eq("purchase").sum()),
                "payment_count": int(group["event_type"].eq("payment").sum()),
                "limit_increase_count": int(group["event_type"].eq("credit_limit_increase").sum()),
                "distinct_event_dates": int(dates.dt.date.nunique()),
                "event_span_days": span_days,
                "events_per_30_days": len(group) / span_days * 30,
                "max_events_single_day": int(day_counts.max()),
                "max_events_7d": max(window_counts) if window_counts else 0,
                "min_days_between_events": int(gaps.min()) if len(gaps) else span_days,
                "mean_days_between_events": float(gaps.mean()) if len(gaps) else float(span_days),
                "mean_utilization_pct": float(group["utilization_pct"].mean()),
                "max_utilization_pct": float(group["utilization_pct"].max()),
                "utilization_range": float(group["utilization_pct"].max() - group["utilization_pct"].min()),
                "max_credit_limit": int(group["credit_limit_at_time"].max()),
            }
        )
    return pd.DataFrame(rows)


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
