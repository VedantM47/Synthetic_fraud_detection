"""Model training, scoring, attributions and evaluation metrics.

Two modes:

* ``supervised``: the dataset has enough fraud labels. Every labeled customer
  gets an out-of-fold score from a ring-aware cross-validation model, so no
  customer is scored by a model that saw its label. The research experiment
  table (4 feature sets x 2 models on a ring-aware 80/20 split) is also
  reproduced.
* ``transfer``: no (or too few) labels. A model is trained on the synthetic
  reference dataset using only the features the upload can provide, plus
  any analyst feedback labels from the upload, and applied to the upload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    accuracy_score,
)
from sklearn.model_selection import StratifiedGroupKFold

from backend import settings
from src.data.split_data import split_by_group
from src.models.random_forest_baseline import evaluate, models

Progress = Callable[[float, str], None]

MIN_POSITIVE_LABELS = 10
SCORING_MODEL_NAME = "hist_gradient_boosting"


class PipelineError(ValueError):
    """The dataset cannot be analysed as configured."""


def scoring_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(random_state=settings.RANDOM_SEED, class_weight="balanced")


@dataclass
class ScoringResult:
    mode: str
    features: list[str]
    scores: np.ndarray
    contributions: np.ndarray
    baseline: dict[str, float]
    baseline_scores: np.ndarray  # score of the typical customer, per scoring model
    threshold: float
    evaluation: dict | None = None
    # Which customers (boolean mask) and labels the evaluation used, so the
    # previous model version can be scored on exactly the same customers.
    evaluation_mask: np.ndarray | None = None
    evaluation_labels: np.ndarray | None = None
    experiments: list[dict] = field(default_factory=list)
    experiment_split: dict | None = None
    reference: dict | None = None
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def _downsample(points: list[list[float]], limit: int = 200) -> list[list[float]]:
    if len(points) <= limit:
        return points
    index = np.linspace(0, len(points) - 1, limit).round().astype(int)
    return [points[i] for i in sorted(set(index.tolist()))]


def best_f1_threshold(y_true: np.ndarray, proba: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return 0.5
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
    best = int(np.argmax(f1[:-1])) if len(thresholds) else 0
    return float(thresholds[best]) if len(thresholds) else 0.5


def classification_metrics(y_true: np.ndarray, proba: np.ndarray, threshold: float) -> dict:
    y_true = np.asarray(y_true).astype(int)
    proba = np.asarray(proba, dtype=float)
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    both_classes = len(np.unique(y_true)) == 2
    metrics = {
        "n": int(len(y_true)),
        "n_positive": int(y_true.sum()),
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, proba)) if both_classes else None,
        "pr_auc": float(average_precision_score(y_true, proba)) if both_classes else None,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }
    order = np.argsort(-proba, kind="mergesort")
    positives = max(int(y_true.sum()), 1)
    at_k = []
    for k in [25, 50, 100, 200, 500, 1000]:
        if k > len(y_true):
            break
        hits = int(y_true[order[:k]].sum())
        at_k.append({"k": k, "precision": hits / k, "recall": hits / positives})
    metrics["at_k"] = at_k
    if both_classes:
        fpr, tpr, _ = roc_curve(y_true, proba)
        metrics["roc_curve"] = _downsample([[float(a), float(b)] for a, b in zip(fpr, tpr)])
        precision, recall, _ = precision_recall_curve(y_true, proba)
        pr_points = [[float(r), float(p)] for r, p in zip(recall, precision)][::-1]
        metrics["pr_curve"] = _downsample(pr_points)
    else:
        metrics["roc_curve"] = []
        metrics["pr_curve"] = []
    return metrics


# --------------------------------------------------------------------------
# Attributions
# --------------------------------------------------------------------------


def shapley_contributions(
    model, X: pd.DataFrame, baseline: pd.Series, n_permutations: int | None = None
) -> tuple[np.ndarray, np.ndarray, float]:
    """Baseline Shapley values estimated by permutation sampling.

    For each sampled feature order, the customer's features are switched one
    at a time from their actual value to the baseline (a typical legitimate
    customer) and every step's score change is credited to the feature that
    moved. Averaging over orders (each paired with its reverse) shares credit
    fairly between redundant features, e.g. a shared phone and a shared
    device that both indicate the same ring. For every customer the
    contributions sum exactly to ``p(customer) - p(baseline)``.

    Returns ``(scores, contributions, baseline_score)``.
    """
    X = X.reset_index(drop=True)
    n, d = X.shape
    scores = model.predict_proba(X)[:, 1]
    baseline_row = pd.DataFrame([baseline[X.columns].to_numpy()], columns=X.columns)
    baseline_score = float(model.predict_proba(baseline_row)[:, 1][0])
    contributions = np.zeros((n, d), dtype=float)
    if n == 0 or d == 0:
        return scores, contributions, baseline_score
    if n_permutations is None:
        n_permutations = 12 if n <= 50_000 else 4
    rng = np.random.default_rng(settings.RANDOM_SEED)
    orders = []
    for _ in range(max(1, n_permutations // 2)):
        order = rng.permutation(d)
        orders.extend([order, order[::-1]])
    values = X.to_numpy(dtype=float)
    base_values = baseline[X.columns].to_numpy(dtype=float)
    already_baseline = (values == base_values).all(axis=0)
    for order in orders:
        current = values.copy()
        previous = scores
        for j in order:
            if already_baseline[j]:
                continue  # switching it changes nothing, so it earns no credit
            current[:, j] = base_values[j]
            step = model.predict_proba(pd.DataFrame(current, columns=X.columns))[:, 1]
            contributions[:, j] += previous - step
            previous = step
    contributions /= len(orders)
    return scores, contributions, baseline_score


def feature_importance(contributions: np.ndarray, features: list[str], groups: dict[str, str], labels: dict[str, str]):
    if contributions.size == 0:
        return [], []
    mean_abs = np.abs(contributions).mean(axis=0)
    rows = [
        {
            "feature": feature,
            "label": labels.get(feature, feature),
            "group": groups.get(feature, "tabular"),
            "importance": float(value),
        }
        for feature, value in zip(features, mean_abs)
    ]
    rows.sort(key=lambda row: row["importance"], reverse=True)
    group_totals: dict[str, float] = {}
    for row in rows:
        group_totals[row["group"]] = group_totals.get(row["group"], 0.0) + row["importance"]
    group_rows = [{"group": group, "importance": value} for group, value in group_totals.items()]
    group_rows.sort(key=lambda row: row["importance"], reverse=True)
    return rows, group_rows


# --------------------------------------------------------------------------
# Supervised mode
# --------------------------------------------------------------------------


def non_constant(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if frame[column].nunique(dropna=False) > 1]


def supervised_possible(labels: pd.Series, groups: pd.Series) -> tuple[bool, str]:
    labeled = labels.notna()
    y = labels[labeled]
    n_pos = int(y.sum())
    if n_pos < MIN_POSITIVE_LABELS:
        return False, f"only {n_pos} fraud labels (at least {MIN_POSITIVE_LABELS} are needed)"
    if int((y == 0).sum()) < MIN_POSITIVE_LABELS:
        return False, "too few legitimate labels"
    positive_groups = groups[labeled][y == 1].nunique()
    if positive_groups < 2:
        return False, "all fraud labels sit in a single connected group"
    return True, ""


def experiment_feature_sets(tabular: list[str], network: list[str], temporal: list[str]) -> list[tuple[str, list[str]]]:
    if tabular:
        candidates = [
            ("tabular", tabular),
            ("tabular_network", tabular + network),
            ("tabular_temporal", tabular + temporal),
            ("combined", tabular + network + temporal),
        ]
    else:
        candidates = [("network", network), ("temporal", temporal), ("combined", network + temporal)]
    seen = {tuple(candidates[-1][1])}
    result = []
    for name, features in candidates[:-1]:
        key = tuple(features)
        if features and key not in seen:
            seen.add(key)
            result.append((name, features))
    if candidates[-1][1]:
        result.append(candidates[-1])
    return result


def run_experiments(
    X_all: pd.DataFrame,
    y: pd.Series,
    group_ids: pd.Series,
    feature_sets: list[tuple[str, list[str]]],
    progress: Progress,
) -> tuple[list[dict], dict | None, list[str]]:
    """Research experiment table on a ring-aware 80/20 split."""
    notes: list[str] = []
    split_frame = pd.DataFrame({"group_id": group_ids.to_numpy()}, index=X_all.index)
    train_frame, test_frame = split_by_group(split_frame, train_frac=0.8, seed=settings.RANDOM_SEED)
    y_train, y_test = y.loc[train_frame.index], y.loc[test_frame.index]
    if y_train.nunique() < 2 or y_test.nunique() < 2:
        notes.append("The 80/20 experiment split did not contain both classes, so experiments were skipped.")
        return [], None, notes
    rows = []
    total = len(feature_sets) * 2
    done = 0
    for experiment, features in feature_sets:
        for model_name, model in models().items():
            metrics, _, probas = evaluate(
                model,
                X_all.loc[train_frame.index, features],
                y_train,
                X_all.loc[test_frame.index, features],
                y_test,
            )
            row = {"model": model_name, "experiment": experiment, "n_features": len(features)}
            row.update({key: (int(value) if key in {"tn", "fp", "fn", "tp"} else float(value)) for key, value in metrics.items()})
            row["pr_auc"] = float(average_precision_score(y_test, probas))
            rows.append(row)
            done += 1
            progress(done / total, f"Experiment {done}/{total}: {model_name} on {experiment} features")
    split = {
        "n_train": int(len(train_frame)),
        "n_test": int(len(test_frame)),
        "n_train_positive": int(y_train.sum()),
        "n_test_positive": int(y_test.sum()),
    }
    return rows, split, notes


def run_supervised(
    frame: pd.DataFrame,
    labels: pd.Series,
    group_ids: pd.Series,
    tabular: list[str],
    network: list[str],
    temporal: list[str],
    progress: Progress,
    run_experiment_table: bool = True,
) -> ScoringResult:
    labeled = labels.notna().to_numpy()
    features = non_constant(frame.loc[labeled], tabular + network + temporal)
    if not features:
        raise PipelineError("No usable features: every candidate feature is constant.")
    tabular_used = [f for f in tabular if f in features]
    network_used = [f for f in network if f in features]
    temporal_used = [f for f in temporal if f in features]

    X = frame[features]
    X_lab = X.loc[labeled]
    y_lab = labels[labeled].astype(int)
    g_lab = group_ids[labeled]

    experiments: list[dict] = []
    split = None
    notes: list[str] = []
    if run_experiment_table:
        sets = experiment_feature_sets(tabular_used, network_used, temporal_used)
        experiments, split, notes = run_experiments(
            X_lab, y_lab, g_lab, sets, lambda f, m: progress(0.55 * f, m)
        )

    positive_groups = g_lab[y_lab == 1].nunique()
    negative_groups = g_lab[y_lab == 0].nunique()
    n_splits = int(min(settings.CV_FOLDS, positive_groups, negative_groups))
    baseline = X_lab[y_lab.to_numpy() == 0].median()

    oof = np.zeros(len(X_lab))
    contributions = np.zeros(X.shape, dtype=float)
    scores = np.zeros(len(X))
    baseline_scores = np.zeros(len(X))
    labeled_positions = np.flatnonzero(labeled)
    cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=settings.RANDOM_SEED)
    for fold, (train_index, test_index) in enumerate(cv.split(X_lab, y_lab, g_lab), start=1):
        model = scoring_model().fit(X_lab.iloc[train_index], y_lab.iloc[train_index])
        proba, contrib, baseline_score = shapley_contributions(model, X_lab.iloc[test_index], baseline)
        oof[test_index] = proba
        contributions[labeled_positions[test_index]] = contrib
        baseline_scores[labeled_positions[test_index]] = baseline_score
        progress(0.55 + 0.35 * fold / n_splits, f"Cross-validated scoring and explanations: fold {fold}/{n_splits}")
    scores[labeled_positions] = oof

    unlabeled_positions = np.flatnonzero(~labeled)
    if len(unlabeled_positions):
        final = scoring_model().fit(X_lab, y_lab)
        proba, contrib, baseline_score = shapley_contributions(final, X.iloc[unlabeled_positions], baseline)
        scores[unlabeled_positions] = proba
        contributions[unlabeled_positions] = contrib
        baseline_scores[unlabeled_positions] = baseline_score
        notes.append(
            f"{len(unlabeled_positions)} unlabeled customers were scored by a model trained on all labeled customers."
        )
    progress(0.95, "Choosing the alert threshold")

    threshold = best_f1_threshold(y_lab.to_numpy(), oof)
    evaluation = classification_metrics(y_lab.to_numpy(), oof, threshold)
    evaluation["scope"] = f"Out-of-fold predictions ({n_splits}-fold cross-validation, connected customers kept together)"
    return ScoringResult(
        mode="supervised",
        features=features,
        scores=scores,
        contributions=contributions,
        baseline={key: float(value) for key, value in baseline.items()},
        baseline_scores=baseline_scores,
        threshold=threshold,
        evaluation=evaluation,
        evaluation_mask=labeled.copy(),
        evaluation_labels=y_lab.to_numpy(),
        experiments=experiments,
        experiment_split=split,
        notes=notes,
    )


# --------------------------------------------------------------------------
# Transfer mode
# --------------------------------------------------------------------------


def run_transfer(
    X_upload: pd.DataFrame,
    reference_X: pd.DataFrame,
    reference_y: pd.Series,
    reference_threshold: float,
    reference_summary: dict,
    feedback_X: pd.DataFrame | None,
    feedback_y: pd.Series | None,
    progress: Progress,
) -> ScoringResult:
    features = list(X_upload.columns)
    X_train = reference_X[features]
    y_train = reference_y.astype(int)
    weights = np.ones(len(X_train))
    notes = []
    if feedback_X is not None and len(feedback_X):
        X_train = pd.concat([X_train, feedback_X[features]], ignore_index=True)
        y_train = pd.concat([y_train.reset_index(drop=True), feedback_y.astype(int).reset_index(drop=True)], ignore_index=True)
        weights = np.concatenate([weights, np.full(len(feedback_X), settings.FEEDBACK_SAMPLE_WEIGHT)])
        notes.append(
            f"Retrained with {len(feedback_X)} analyst feedback labels "
            f"(each weighted {settings.FEEDBACK_SAMPLE_WEIGHT:g}x a reference example)."
        )
    progress(0.3, "Training the transfer model")
    model = scoring_model().fit(X_train, y_train.to_numpy(), sample_weight=weights)
    baseline = reference_X[features][reference_y.to_numpy() == 0].median()
    progress(0.6, "Scoring customers and computing explanations")
    scores, contributions, baseline_score = shapley_contributions(model, X_upload, baseline)
    progress(1.0, "Scored all customers")
    return ScoringResult(
        mode="transfer",
        features=features,
        scores=scores,
        contributions=contributions,
        baseline={key: float(value) for key, value in baseline.items()},
        baseline_scores=np.full(len(scores), baseline_score),
        threshold=reference_threshold,
        reference=reference_summary,
        notes=notes,
    )


def risk_levels(scores: np.ndarray, threshold: float) -> np.ndarray:
    return np.where(scores >= threshold, "high", np.where(scores >= threshold / 2, "medium", "low"))
