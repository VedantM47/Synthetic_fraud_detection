import argparse
from pathlib import Path

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


TABULAR_FEATURES = ["annual_income", "credit_score", "account_tenure_days"]
NETWORK_FEATURES = [
    "phone_shared_count",
    "email_shared_count",
    "address_shared_count",
    "device_shared_count",
    "network_degree",
    "shared_attribute_count",
]
TEMPORAL_FEATURES = [
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


def load_split(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path, float_precision="round_trip")


def merge_features(df: pd.DataFrame, feature_path: Path, columns: list[str]) -> pd.DataFrame:
    # round_trip parsing reads floats back bit-exactly; pandas' default parser
    # can be off by one ulp, which changes HistGradientBoosting results.
    feature_df = pd.read_csv(feature_path, float_precision="round_trip")
    merged = df.merge(feature_df[["customer_id", *columns]], on="customer_id", how="left")
    merged[columns] = merged[columns].fillna(0)
    return merged


def build_feature_frames(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    network_path: Path,
    temporal_path: Path,
) -> dict[str, tuple[pd.DataFrame, pd.DataFrame, list[str]]]:
    train_net = merge_features(train_df, network_path, NETWORK_FEATURES)
    test_net = merge_features(test_df, network_path, NETWORK_FEATURES)
    train_tmp = merge_features(train_df, temporal_path, TEMPORAL_FEATURES)
    test_tmp = merge_features(test_df, temporal_path, TEMPORAL_FEATURES)

    groups = {
        "tabular": TABULAR_FEATURES,
        "tabular_network": TABULAR_FEATURES + NETWORK_FEATURES,
        "tabular_temporal": TABULAR_FEATURES + TEMPORAL_FEATURES,
        "combined": TABULAR_FEATURES + NETWORK_FEATURES + TEMPORAL_FEATURES,
    }
    return {
        "tabular": (train_df[groups["tabular"]], test_df[groups["tabular"]], groups["tabular"]),
        "tabular_network": (
            train_net[groups["tabular_network"]],
            test_net[groups["tabular_network"]],
            groups["tabular_network"],
        ),
        "tabular_temporal": (
            train_tmp[groups["tabular_temporal"]],
            test_tmp[groups["tabular_temporal"]],
            groups["tabular_temporal"],
        ),
        "combined": (
            train_net.merge(train_tmp[["customer_id", *TEMPORAL_FEATURES]], on="customer_id")[
                groups["combined"]
            ],
            test_net.merge(test_tmp[["customer_id", *TEMPORAL_FEATURES]], on="customer_id")[
                groups["combined"]
            ],
            groups["combined"],
        ),
    }


def models() -> dict[str, object]:
    return {
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            random_state=42,
            class_weight="balanced",
        ),
    }


def evaluate(model, X_train, y_train, X_test, y_test) -> tuple[dict, object, object]:
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    probas = model.predict_proba(X_test)[:, 1]
    tn, fp, fn, tp = confusion_matrix(y_test, preds, labels=[0, 1]).ravel()
    return (
        {
            "accuracy": accuracy_score(y_test, preds),
            "precision": precision_score(y_test, preds, zero_division=0),
            "recall": recall_score(y_test, preds, zero_division=0),
            "f1": f1_score(y_test, preds, zero_division=0),
            "roc_auc": roc_auc_score(y_test, probas),
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
        },
        preds,
        probas,
    )


def feature_group(feature: str) -> str:
    if feature in NETWORK_FEATURES:
        return "network"
    if feature in TEMPORAL_FEATURES:
        return "temporal"
    return "tabular"


def save_importance(out_dir: Path, model_name: str, experiment: str, model, columns: list[str]) -> None:
    if not hasattr(model, "feature_importances_"):
        return
    frame = pd.DataFrame(
        {
            "model": model_name,
            "experiment": experiment,
            "feature": columns,
            "feature_group": [feature_group(column) for column in columns],
            "importance": model.feature_importances_,
        }
    )
    frame.to_csv(out_dir / f"{model_name}_{experiment}_feature_importance.csv", index=False)
    (
        frame.groupby(["model", "experiment", "feature_group"], as_index=False)["importance"]
        .sum()
        .to_csv(out_dir / f"{model_name}_{experiment}_group_importance.csv", index=False)
    )


def save_predictions(out_dir: Path, model_name: str, experiment: str, test_df: pd.DataFrame, preds, probas) -> None:
    out = test_df[["customer_id", "is_synthetic_fraud"]].copy()
    out["pred_label"] = preds
    out["pred_proba"] = probas
    out.to_csv(out_dir / f"{model_name}_{experiment}_predictions.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fraud model experiments by feature group.")
    parser.add_argument("--train", type=Path, default=Path(__file__).parents[2] / "data" / "processed" / "train.csv")
    parser.add_argument("--test", type=Path, default=Path(__file__).parents[2] / "data" / "processed" / "test.csv")
    parser.add_argument(
        "--features",
        type=Path,
        default=Path(__file__).parents[2] / "data" / "processed" / "customer_features.csv",
    )
    parser.add_argument(
        "--temporal-features",
        type=Path,
        default=Path(__file__).parents[2] / "data" / "processed" / "customer_temporal_features.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parents[2] / "outputs" / "models" / "rf_baseline",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    train_df = load_split(args.train)
    test_df = load_split(args.test)
    y_train = train_df["is_synthetic_fraud"]
    y_test = test_df["is_synthetic_fraud"]
    experiments = build_feature_frames(train_df, test_df, args.features, args.temporal_features)

    metric_rows = []
    for experiment, (X_train, X_test, columns) in experiments.items():
        for model_name, model in models().items():
            metrics, preds, probas = evaluate(model, X_train, y_train, X_test, y_test)
            metric_rows.append({"model": model_name, "experiment": experiment, **metrics})
            save_predictions(args.output_dir, model_name, experiment, test_df, preds, probas)
            save_importance(args.output_dir, model_name, experiment, model, columns)

    metrics_df = pd.DataFrame(metric_rows)
    metrics_df.to_csv(args.output_dir / "model_metrics.csv", index=False)
    with open(args.output_dir / "rf_metrics_report.txt", "w", encoding="utf-8") as handle:
        handle.write(metrics_df.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
        handle.write("\n")
    print(metrics_df.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(f"Saved model outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
