import argparse
import itertools
from pathlib import Path
import pandas as pd


def load_attribute_links(csv_path: Path) -> pd.DataFrame:
    """Load customer_attribute_links CSV.

    Expected columns: ``customer_id``, ``attribute_type``, ``attribute_id``.
    """
    return pd.read_csv(csv_path)


CORE_ATTRIBUTE_TYPES = ["phone", "email", "address", "device"]


def edge_attribute_types(df: pd.DataFrame) -> list[str]:
    """Return the core attribute types followed by any extra types in ``df``.

    Extra types (for example ``ip`` or ``national_id`` from an uploaded
    dataset) are appended in sorted order so the output is deterministic.
    """
    present = set(df["attribute_type"].dropna().astype(str).unique()) if len(df) else set()
    return CORE_ATTRIBUTE_TYPES + sorted(present - set(CORE_ATTRIBUTE_TYPES))


def build_edge_records(
    df: pd.DataFrame,
    attribute_types: list[str] | None = None,
    max_group_size: int | None = None,
) -> pd.DataFrame:
    """Create edge records with shared attribute flags.

    Returns a DataFrame with columns:
        source_customer_id
        target_customer_id
        shared_phone
        shared_email
        shared_address
        shared_device
        shared_<extra type> (one per extra attribute type, if any)
        shared_attribute_count

    ``max_group_size`` skips attribute values shared by more customers than
    the limit. Values such as placeholder phone numbers or an office address
    would otherwise create a clique of every account that uses them.
    """
    attr_types = attribute_types if attribute_types is not None else edge_attribute_types(df)
    flag_names = [f"shared_{attr}" for attr in attr_types]
    # Initialize a dict to accumulate flags per unordered pair
    edge_dict = {}

    # Process each attribute type separately
    for attr in attr_types:
        # Subset rows for this attribute type
        sub = df[df["attribute_type"] == attr]
        # Group by attribute_id to get customers sharing the same value
        for _, group in sub.groupby("attribute_id"):
            customers = group["customer_id"].unique()
            if len(customers) < 2:
                continue  # No edge to create
            if max_group_size is not None and len(customers) > max_group_size:
                continue  # Generic/hub value, not an identity link
            # Generate all unordered pairs (combinations) of customers
            for a, b in itertools.combinations(sorted(customers), 2):
                key = (a, b)
                if key not in edge_dict:
                    edge_dict[key] = dict.fromkeys(flag_names, 0)
                # Set the appropriate flag
                flag_name = f"shared_{attr}"
                edge_dict[key][flag_name] = 1

    # Convert dict to DataFrame
    rows = []
    for (src, tgt), flags in edge_dict.items():
        shared_count = sum(flags.values())
        rows.append(
            {
                "source_customer_id": src,
                "target_customer_id": tgt,
                **flags,
                "shared_attribute_count": shared_count,
            }
        )
    columns = ["source_customer_id", "target_customer_id", *flag_names, "shared_attribute_count"]
    return pd.DataFrame(rows, columns=columns)


def save_edges(df: pd.DataFrame, out_path: Path) -> None:
    """Save edge DataFrame to CSV.

    The output directory is created if it does not exist.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Saved edges to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build customer network edges from attribute links.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parents[2] / "data" / "raw" / "customer_attribute_links.csv",
        help="Path to customer_attribute_links CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parents[2] / "data" / "processed" / "customer_edges.csv",
        help="Path where the edge list CSV will be written.",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    links_df = load_attribute_links(args.input)
    edges_df = build_edge_records(links_df)
    save_edges(edges_df, args.output)


if __name__ == "__main__":
    main()

