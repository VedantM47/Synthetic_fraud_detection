import argparse
import itertools
from pathlib import Path
import pandas as pd


def load_attribute_links(csv_path: Path) -> pd.DataFrame:
    """Load customer_attribute_links CSV.

    Expected columns: ``customer_id``, ``attribute_type``, ``attribute_id``.
    """
    return pd.read_csv(csv_path)


def build_edge_records(df: pd.DataFrame) -> pd.DataFrame:
    """Create edge records with shared attribute flags.

    Returns a DataFrame with columns:
        source_customer_id
        target_customer_id
        shared_phone
        shared_email
        shared_address
        shared_device
        shared_attribute_count
    """
    # Initialize a dict to accumulate flags per unordered pair
    edge_dict = {}

    # Process each attribute type separately
    attr_types = ["phone", "email", "address", "device"]
    for attr in attr_types:
        # Subset rows for this attribute type
        sub = df[df["attribute_type"] == attr]
        # Group by attribute_id to get customers sharing the same value
        for _, group in sub.groupby("attribute_id"):
            customers = group["customer_id"].unique()
            if len(customers) < 2:
                continue  # No edge to create
            # Generate all unordered pairs (combinations) of customers
            for a, b in itertools.combinations(sorted(customers), 2):
                key = (a, b)
                if key not in edge_dict:
                    edge_dict[key] = {
                        "shared_phone": 0,
                        "shared_email": 0,
                        "shared_address": 0,
                        "shared_device": 0,
                    }
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
    return pd.DataFrame(rows)


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

