import argparse
import os
import random
import sys
from pathlib import Path

import pandas as pd


def load_customers(csv_path: Path) -> pd.DataFrame:
    """Load the customers CSV.

    Args:
        csv_path: Path to the raw customers CSV.

    Returns:
        DataFrame with original columns.
    """
    return pd.read_csv(csv_path)


def create_group_column(df: pd.DataFrame) -> pd.DataFrame:
    """Create a grouping column that respects fraud rings.

    Fraud customers belong to a ring identified by ``ring_id``. Legitimate
    customers have an empty ``ring_id`` (NaN).  For legitimate customers we
    treat each ``customer_id`` as its own group so they can be distributed
    independently across splits.
    """
    # ``ring_id`` is a string; treat empty strings as NaN as well.
    df["ring_id"] = df["ring_id"].replace("", pd.NA)
    df["group_id"] = df["ring_id"].fillna(df["customer_id"])
    return df


def split_by_group(df: pd.DataFrame, train_frac: float = 0.8, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the dataframe into train / test respecting groups.

    The split is performed on the ``group_id`` column which guarantees that
    all customers belonging to the same fraud ring stay together.
    """
    random.seed(seed)
    unique_groups = df["group_id"].unique().tolist()
    random.shuffle(unique_groups)
    split_idx = int(len(unique_groups) * train_frac)
    train_groups = set(unique_groups[:split_idx])
    test_groups = set(unique_groups[split_idx:])

    train_df = df[df["group_id"].isin(train_groups)].copy()
    test_df = df[df["group_id"].isin(test_groups)].copy()
    return train_df, test_df


def validate_split(train_df: pd.DataFrame, test_df: pd.DataFrame) -> None:
    """Validate that no fraud ring appears in both splits.

    Prints a concise report. Raises ``ValueError`` if validation fails.
    """
    total_customers = len(train_df) + len(test_df)
    train_customers = len(train_df)
    test_customers = len(test_df)

    train_fraud = train_df[train_df["is_synthetic_fraud"] == 1]
    test_fraud = test_df[test_df["is_synthetic_fraud"] == 1]
    train_fraud_cnt = len(train_fraud)
    test_fraud_cnt = len(test_fraud)

    # Unique fraud rings (non‑NA ring_id) present in each split
    train_rings = set(train_fraud["ring_id"].dropna().unique())
    test_rings = set(test_fraud["ring_id"].dropna().unique())
    overlapping = train_rings.intersection(test_rings)

    print(f"""\
Total customers: {total_customers}

Train customers: {train_customers}
Test customers: {test_customers}

Train fraud: {train_fraud_cnt}
Test fraud: {test_fraud_cnt}

Train fraud rings: {len(train_rings)}
Test fraud rings: {len(test_rings)}

Rings appearing in both: {len(overlapping)}
""")
    if overlapping:
        raise ValueError(f"Ring‑aware split failed: {len(overlapping)} rings appear in both splits.")


def save_split(train_df: pd.DataFrame, test_df: pd.DataFrame, out_dir: Path) -> None:
    """Save ``train.csv`` and ``test.csv`` to ``out_dir``.

    The function creates ``out_dir`` if it does not exist.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    train_path = out_dir / "train.csv"
    test_path = out_dir / "test.csv"
    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)
    print(f"Saved train set to {train_path}")
    print(f"Saved test set to {test_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ring‑aware train/test split for fraud detection data.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parents[2] / "data" / "raw" / "customers.csv",
        help="Path to the raw customers CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parents[2] / "data" / "processed",
        help="Directory where train.csv and test.csv will be written.",
    )
    parser.add_argument(
        "--train-frac",
        type=float,
        default=0.8,
        help="Fraction of groups to allocate to the training split.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        sys.exit(f"Input file not found: {args.input}")

    df = load_customers(args.input)
    df = create_group_column(df)
    train_df, test_df = split_by_group(df, train_frac=args.train_frac, seed=args.seed)
    validate_split(train_df, test_df)
    save_split(train_df, test_df, args.output)


if __name__ == "__main__":
    main()

