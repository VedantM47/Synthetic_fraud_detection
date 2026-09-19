"""End-to-end analysis job: data -> graph -> features -> model -> rings -> DB."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from backend import settings
from backend.db import Database, dumps, utcnow
from backend.pipeline.explain import explain_customer, explain_ring
from backend.pipeline.features import (
    FeatureTable,
    GraphResult,
    assemble_features,
    build_graph,
    core_types_present,
    count_feature,
)
from backend.pipeline.ingest import CanonicalData, build_from_upload, canonical_from_generated
from backend.pipeline.modeling import (
    PipelineError,
    ScoringResult,
    classification_metrics,
    feature_importance,
    risk_levels,
    run_supervised,
    run_transfer,
    supervised_possible,
)
from backend.pipeline.reference import get_reference
from backend.pipeline.rings import ring_candidates, ring_detection_quality, summarize_rings
from data_generation.run_all import generate_all
from src.data.build_customer_graph import CORE_ATTRIBUTE_TYPES

STAGES = {
    "generate": ("Generate synthetic data", 0.15),
    "load": ("Load and validate data", 0.05),
    "graph": ("Build identity graph", 0.10),
    "features": ("Compute network and behaviour features", 0.10),
    "model": ("Train and score the risk model", 0.35),
    "rings": ("Detect fraud rings", 0.05),
    "explain": ("Write plain-English explanations", 0.10),
    "save": ("Save results to the database", 0.10),
}
JOB_STAGES = {
    "synthetic": ["generate", "load", "graph", "features", "model", "rings", "explain", "save"],
    "analyze": ["load", "graph", "features", "model", "rings", "explain", "save"],
    "retrain": ["load", "graph", "features", "model", "rings", "explain", "save"],
}


class JobReporter(Protocol):
    def stage(self, key: str): ...

    def progress(self, fraction: float, message: str) -> None: ...


def stage_plan(kind: str) -> list[dict]:
    keys = JOB_STAGES[kind]
    total = sum(STAGES[key][1] for key in keys)
    return [
        {"key": key, "label": STAGES[key][0], "weight": STAGES[key][1] / total, "status": "pending", "progress": 0.0, "message": ""}
        for key in keys
    ]


def dataset_dir(paths: dict[str, Path], dataset_id: str) -> Path:
    return paths["datasets"] / dataset_id


def component_groups(customer_ids: pd.Series, edges: pd.DataFrame) -> pd.Series:
    """Connected-component id per customer (own id when unlinked)."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        root = node
        while parent.get(root, root) != root:
            root = parent[root]
        while parent.get(node, node) != root:
            parent[node], node = root, parent[node]
        return root

    for source, target in zip(edges["source_customer_id"], edges["target_customer_id"]):
        a, b = find(source), find(target)
        if a != b:
            parent[max(a, b)] = min(a, b)
    return pd.Series([f"component:{find(customer)}" for customer in customer_ids], index=customer_ids.index)


def split_groups(data: CanonicalData, edges: pd.DataFrame) -> pd.Series:
    customers = data.customers
    truth = customers["truth_ring"].astype(str)
    if truth.ne("").any():
        # Same grouping as the research split: known rings stay together.
        return truth.where(truth != "", customers["customer_id"])
    return component_groups(customers["customer_id"], edges)


def _transfer_inputs(
    data: CanonicalData, table: FeatureTable, reporter: JobReporter, reference_dir: Path
):
    """Upload features and matching reference training data for transfer mode.

    Per-type counts use the core attribute types present in the upload.
    The upload's ``network_degree`` counts links through any identifier it
    has; the reference counts links through the same core types (or all of
    them when the upload only has non-core identifiers such as IP address).
    """
    linked_types = sorted(set(data.links["attribute_type"])) if len(data.links) else []
    count_types = core_types_present(linked_types)
    reference_degree_types = count_types or list(CORE_ATTRIBUTE_TYPES)
    temporal = table.temporal
    network_columns = [count_feature(kind) for kind in count_types]
    if linked_types:
        network_columns += ["network_degree", "shared_attribute_count"]
    features = network_columns + temporal
    if not features:
        raise PipelineError(
            "There is nothing the reference model can use: map at least one identity column "
            "(phone, email, address, device, ...) or upload an events file. "
            "To train on your own numeric columns instead, include a fraud label column."
        )
    # table.frame network columns are computed over every identity type.
    X_upload = table.frame[features].reset_index(drop=True)

    reference = get_reference(reference_dir, lambda message: reporter.progress(0.05, message))
    reporter.progress(0.1, "Building reference features for the same attribute types")
    reference_X = reference.features(count_types, reference_degree_types, temporal)[features]
    key = (tuple(count_types), tuple(reference_degree_types), tuple(temporal))
    reporter.progress(0.15, "Calibrating the alert threshold on the reference data")
    calibration = reference.calibration(key, reference_X)
    reference_customers = reference.data.customers
    n_rings = int(reference_customers["truth_ring"].replace("", np.nan).nunique())
    summary = {
        "source": f"Synthetic reference dataset ({len(reference_customers):,} customers, {n_rings} known rings)",
        "n_train": int(len(reference_X)),
        "features": features,
        "attribute_types": count_types,
        "reference_roc_auc": calibration["roc_auc"],
    }
    return X_upload, reference_X, reference.labels, calibration["threshold"], summary


def _evaluation_on_labels(
    labels: pd.Series, scores: np.ndarray, threshold: float, exclude: set[str], ids: pd.Series
) -> tuple[dict | None, np.ndarray | None, np.ndarray | None]:
    """Metrics against labels the model never trained on.

    Customers an analyst reviewed are excluded: after a retrain their labels
    were training data, so including them would overstate performance.
    """
    mask = labels.notna().to_numpy() & ~ids.isin(exclude).to_numpy()
    y = labels[mask].astype(int).to_numpy()
    if len(y) == 0 or len(np.unique(y)) < 2:
        return None, None, None
    metrics = classification_metrics(y, scores[mask], threshold)
    metrics["scope"] = "Your labels, hidden from the model" + (
        f" ({len(exclude)} analyst-reviewed customers excluded)" if exclude else ""
    )
    return metrics, mask, y


def score_dataset(
    data: CanonicalData,
    graph: GraphResult,
    table: FeatureTable,
    feedback: dict[str, int],
    reporter: JobReporter,
    reference_dir: Path,
) -> ScoringResult:
    customers = data.customers
    labels = customers["label"]
    notes: list[str] = []
    if data.label_mode == "train" and labels.notna().any():
        effective = labels.copy()
        override = customers["customer_id"].map(feedback)
        effective[override.notna()] = override[override.notna()].astype(float)
        groups = split_groups(data, graph.edges)
        possible, reason = supervised_possible(effective, groups)
        if possible:
            result = run_supervised(
                table.frame,
                effective,
                groups,
                table.tabular,
                table.network,
                table.temporal,
                reporter.progress,
            )
            if feedback:
                result.notes.append(f"{len(feedback)} analyst decisions were used as labels.")
            return result
        notes.append(f"Could not train on your labels ({reason}); used the reference model and evaluated against them.")

    X_upload, reference_X, reference_y, threshold, summary = _transfer_inputs(data, table, reporter, reference_dir)
    feedback_ids = [customer for customer in customers["customer_id"] if customer in feedback]
    feedback_X = feedback_y = None
    if feedback_ids:
        positions = customers.index[customers["customer_id"].isin(feedback_ids)]
        feedback_X = X_upload.loc[positions].reset_index(drop=True)
        feedback_y = customers.loc[positions, "customer_id"].map(feedback).reset_index(drop=True)
    result = run_transfer(
        X_upload,
        reference_X,
        reference_y,
        threshold,
        summary,
        feedback_X,
        feedback_y,
        lambda fraction, message: reporter.progress(0.2 + 0.8 * fraction, message),
    )
    result.notes = notes + result.notes
    if labels.notna().any():
        result.evaluation, result.evaluation_mask, result.evaluation_labels = _evaluation_on_labels(
            labels, result.scores, result.threshold, set(feedback_ids), customers["customer_id"]
        )
    return result


def _previous_version_metrics(
    db: Database, dataset_id: str, previous_version: int, previous_customers: dict, ids: pd.Series, result: ScoringResult
) -> dict | None:
    """Score the previous model version on exactly the customers just evaluated."""
    if result.evaluation is None or result.evaluation_mask is None or not previous_customers or previous_version < 1:
        return None
    run = db.one(
        "SELECT threshold FROM model_runs WHERE dataset_id = ? AND version = ?", (dataset_id, previous_version)
    )
    evaluated_ids = ids[result.evaluation_mask]
    if run is None or not all(customer in previous_customers for customer in evaluated_ids):
        return None
    previous_scores = np.array([previous_customers[customer][1] for customer in evaluated_ids], dtype=float)
    metrics = classification_metrics(result.evaluation_labels, previous_scores, run["threshold"])
    return {
        "version": previous_version,
        **{key: metrics[key] for key in ["roc_auc", "pr_auc", "precision", "recall", "f1", "tp", "fp", "fn", "tn"]},
    }


def _previous_state(db: Database, dataset_id: str) -> tuple[dict[str, tuple[str, float]], dict[str, bool]]:
    customers = db.all("SELECT customer_id, risk_level, risk FROM customers WHERE dataset_id = ?", (dataset_id,))
    rings = db.all("SELECT ring_id, suspected FROM rings WHERE dataset_id = ?", (dataset_id,))
    return (
        {row["customer_id"]: (row["risk_level"], row["risk"]) for row in customers},
        {row["ring_id"]: bool(row["suspected"]) for row in rings},
    )


def _changes(previous_customers, previous_rings, ids, levels, scores, rings, previous_version) -> dict | None:
    if not previous_customers:
        return None
    level_changes = newly_high = no_longer_high = 0
    deltas = []
    for customer, level, score in zip(ids, levels, scores):
        if customer not in previous_customers:
            continue
        old_level, old_score = previous_customers[customer]
        deltas.append(abs(score - old_score))
        if old_level != level:
            level_changes += 1
        if level == "high" and old_level != "high":
            newly_high += 1
        if old_level == "high" and level != "high":
            no_longer_high += 1
    new_suspected = sum(1 for ring in rings if ring["suspected"] and not previous_rings.get(ring["ring_id"], False))
    cleared = sum(1 for ring in rings if not ring["suspected"] and previous_rings.get(ring["ring_id"], False))
    return {
        "previous_version": previous_version,
        "level_changes": level_changes,
        "newly_high": newly_high,
        "no_longer_high": no_longer_high,
        "mean_abs_score_change": float(np.mean(deltas)) if deltas else 0.0,
        "rings_newly_suspected": new_suspected,
        "rings_cleared": cleared,
    }


def _risk_histogram(scores: np.ndarray, labels: pd.Series, bins: int = 20) -> list[dict]:
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(scores, edges[1:-1]), 0, bins - 1)
    has_labels = labels.notna().any()
    rows = []
    for b in range(bins):
        in_bin = index == b
        row = {"start": float(edges[b]), "end": float(edges[b + 1]), "count": int(in_bin.sum())}
        if has_labels:
            row["fraud"] = int((labels.to_numpy()[in_bin] == 1).sum())
            row["legit"] = int((labels.to_numpy()[in_bin] == 0).sum())
        rows.append(row)
    return rows


def _graph_stats(graph: GraphResult, customers: pd.DataFrame) -> dict:
    edges = graph.edges
    stats = {
        "n_nodes": int(len(customers)),
        "n_edges": int(len(edges)),
        "edges_by_type": {
            kind: int(edges[f"shared_{kind}"].sum())
            for kind in graph.attribute_types
            if f"shared_{kind}" in edges.columns and int(edges[f"shared_{kind}"].sum()) > 0
        },
        "linked_customers": int(
            pd.concat([edges["source_customer_id"], edges["target_customer_id"]]).nunique() if len(edges) else 0
        ),
        "hub_values_skipped": graph.hub_values,
        "label_mix": None,
    }
    labels = customers.set_index("customer_id")["label"]
    if labels.notna().any() and len(edges):
        a = edges["source_customer_id"].map(labels).to_numpy()
        b = edges["target_customer_id"].map(labels).to_numpy()
        known = ~(np.isnan(a) | np.isnan(b))
        stats["label_mix"] = {
            "legit_legit": int(((a == 0) & (b == 0) & known).sum()),
            "fraud_fraud": int(((a == 1) & (b == 1) & known).sum()),
            "mixed": int(((a != b) & known).sum()),
        }
    return stats


def run_analysis(
    reporter: JobReporter,
    db: Database,
    paths: dict[str, Path],
    dataset_id: str,
    kind: str,
    params: dict,
) -> dict:
    dataset = db.get_dataset(dataset_id)
    if dataset is None:
        raise PipelineError("Dataset not found.")
    folder = dataset_dir(paths, dataset_id)
    folder.mkdir(parents=True, exist_ok=True)
    canonical_path = folder / "canonical.pkl"
    previous_version = int(dataset["active_version"] or 0)

    # 1. Data --------------------------------------------------------------
    data: CanonicalData
    if kind == "synthetic":
        with reporter.stage("generate"):
            reporter.progress(0.1, f"Generating {params['n_legitimate']:,} legitimate and {params['n_fraud']:,} fraud-ring customers")
            generated = generate_all(
                seed=int(params["seed"]),
                n_legitimate=int(params["n_legitimate"]),
                n_fraud=int(params["n_fraud"]),
                out_dir=folder / "raw",
                progress=reporter.progress,
            )
            reporter.progress(1.0, "Synthetic data generated")
    with reporter.stage("load"):
        if kind == "synthetic":
            data = canonical_from_generated(generated)
        elif kind == "analyze":
            reporter.progress(0.2, "Reading uploaded files")
            files = {key: Path(value) for key, value in (dataset["files"] or {}).items() if value}
            data = build_from_upload(files, dataset["mapping"] or {})
        else:
            if not canonical_path.is_file():
                raise PipelineError("The original data for this dataset is missing; please upload it again.")
            with open(canonical_path, "rb") as handle:
                data = pickle.load(handle)
        if kind != "retrain":
            with open(canonical_path, "wb") as handle:
                pickle.dump(data, handle)
        feedback = db.feedback_labels(dataset_id)
        feedback = {customer: label for customer, label in feedback.items() if customer in set(data.customers["customer_id"])}
        reporter.progress(
            1.0,
            f"{len(data.customers):,} customers, {len(data.links):,} identity links, "
            f"{0 if data.events is None else len(data.events):,} events, {len(feedback)} analyst labels",
        )

    # 2. Graph -------------------------------------------------------------
    with reporter.stage("graph"):
        reporter.progress(0.1, "Linking customers that share identity attributes")
        graph = build_graph(data, settings.MAX_ATTRIBUTE_GROUP_SIZE)
        message = f"{len(graph.edges):,} links between customers"
        if graph.hub_values:
            message += f"; {len(graph.hub_values)} very common values ignored"
        reporter.progress(1.0, message)

    # 3. Features ----------------------------------------------------------
    with reporter.stage("features"):
        reporter.progress(0.2, "Computing network red flags and behaviour features")
        table = assemble_features(data, graph)
        reporter.progress(
            1.0,
            f"{len(table.tabular)} profile, {len(table.network)} network and {len(table.temporal)} behaviour features",
        )

    # 4. Model -------------------------------------------------------------
    with reporter.stage("model"):
        result = score_dataset(data, graph, table, feedback, reporter, Path(paths["reference"]))
        reporter.progress(1.0, f"Scored {len(result.scores):,} customers ({result.mode} model)")

    customers = data.customers
    ids = customers["customer_id"]
    scores = np.asarray(result.scores, dtype=float)
    levels = risk_levels(scores, result.threshold)
    score_series = pd.Series(scores, index=ids.to_numpy())

    # 5. Rings -------------------------------------------------------------
    with reporter.stage("rings"):
        reporter.progress(0.2, "Finding connected groups of linked accounts")
        groups = ring_candidates(graph.edges, settings.MAX_RING_SIZE)
        rings = summarize_rings(groups, graph.edges, data.links, customers, score_series, result.threshold)
        for ring in rings:
            ring["explanation"] = explain_ring(ring)
        quality = ring_detection_quality(rings, customers)
        reporter.progress(1.0, f"{quality['n_suspected']} suspected rings among {quality['n_candidates']} connected groups")

    # 6. Explanations --------------------------------------------------------
    with reporter.stage("explain"):
        position = {customer: i for i, customer in enumerate(ids)}
        high = scores >= result.threshold
        high_neighbors = np.zeros(len(ids), dtype=int)
        if len(graph.edges):
            source_index = graph.edges["source_customer_id"].map(position).to_numpy()
            target_index = graph.edges["target_customer_id"].map(position).to_numpy()
            np.add.at(high_neighbors, source_index, high[target_index].astype(int))
            np.add.at(high_neighbors, target_index, high[source_index].astype(int))
        ring_of = {customer: ring for ring in rings for customer in ring["members"]}
        count_columns = {kind: count_feature(kind) for kind in graph.attribute_types}
        frame = table.frame
        degree = frame["network_degree"].to_numpy()
        feature_groups = {f: "tabular" for f in table.tabular}
        feature_groups.update({f: "network" for f in table.network})
        feature_groups.update({f: "temporal" for f in table.temporal})
        for f in result.features:
            feature_groups.setdefault(f, "network" if f.endswith("_shared_count") or f in {"network_degree", "shared_attribute_count"} else "temporal")
        model_values = frame[result.features].to_numpy(dtype=float)
        count_values = frame[list(count_columns.values())].to_numpy(dtype=float)
        count_kinds = list(count_columns)
        display_columns = list(dict.fromkeys(table.all_features + list(count_columns.values()) + result.features))
        display_columns = [column for column in display_columns if column in frame.columns]
        explanations = []
        total = len(ids)
        for i in range(total):
            customer = ids.iat[i]
            values = dict(zip(result.features, model_values[i].tolist()))
            shared_counts = {
                kind: int(count) for kind, count in zip(count_kinds, count_values[i].tolist()) if count > 0
            }
            explanation = explain_customer(
                risk=float(scores[i]),
                level=str(levels[i]),
                features=result.features,
                values=values,
                contributions=result.contributions[i].tolist(),
                labels=table.labels,
                shared_counts=shared_counts,
                degree=int(degree[i]),
                high_neighbors=int(high_neighbors[i]),
                ring=ring_of.get(customer),
                analyst_label=feedback.get(customer),
                baseline_score=float(result.baseline_scores[i]),
            )
            explanation["contributions"] = sorted(
                [
                    {
                        "feature": feature,
                        "label": table.labels.get(feature, feature),
                        "group": feature_groups.get(feature, "tabular"),
                        "value": values[feature],
                        "impact": round(float(result.contributions[i, j]) * 100, 2),
                    }
                    for j, feature in enumerate(result.features)
                ],
                key=lambda row: -abs(row["impact"]),
            )
            explanations.append(explanation)
            if i % 2000 == 0:
                reporter.progress(i / total, f"Explained {i:,} of {total:,} customers")
        reporter.progress(1.0, f"Explained {total:,} customers")

    # 7. Save --------------------------------------------------------------
    with reporter.stage("save"):
        previous_customers, previous_rings = _previous_state(db, dataset_id)
        version = previous_version + 1
        order = np.argsort(-scores, kind="mergesort")
        rank = np.empty(len(scores), dtype=int)
        rank[order] = np.arange(1, len(scores) + 1)

        links_by_customer: dict[str, list[dict]] = {}
        if len(data.links):
            sizes = data.links["attribute_id"].map(graph.group_sizes).fillna(1).astype(int)
            for customer, kind, attribute_id, value, size in zip(
                data.links["customer_id"],
                data.links["attribute_type"],
                data.links["attribute_id"],
                data.links["attribute_value"],
                sizes,
            ):
                links_by_customer.setdefault(customer, []).append(
                    {
                        "type": kind,
                        "key": attribute_id,
                        "value": value,
                        "shared_with": int(size) - 1,
                        "ignored": bool(size > settings.MAX_ATTRIBUTE_GROUP_SIZE),
                    }
                )
        display_values = frame[display_columns].to_numpy(dtype=float)
        customer_rows = []
        for i in range(len(ids)):
            customer = ids.iat[i]
            label = customers["label"].iat[i]
            ring = ring_of.get(customer)
            customer_rows.append(
                (
                    dataset_id,
                    customer,
                    str(customers["name"].iat[i]),
                    None if pd.isna(label) else int(label),
                    str(customers["truth_ring"].iat[i]) or None,
                    str(customers["open_date"].iat[i]) or None,
                    float(scores[i]),
                    str(levels[i]),
                    int(rank[i]),
                    ring["ring_id"] if ring else None,
                    int(degree[i]),
                    int(high_neighbors[i]),
                    explanations[i]["top_reason"],
                    dumps(dict(zip(display_columns, display_values[i].tolist()))),
                    dumps(explanations[i]),
                    dumps(links_by_customer.get(customer, [])),
                )
            )
        reporter.progress(0.3, "Saving customers")

        importance, group_importance = feature_importance(result.contributions, result.features, feature_groups, table.labels)
        if result.evaluation is not None:
            result.evaluation["previous_version"] = _previous_version_metrics(
                db, dataset_id, previous_version, previous_customers, ids, result
            )
        metrics = {
            "mode": result.mode,
            "model": "HistGradientBoostingClassifier (class-balanced)",
            "features": result.features,
            "feature_labels": {
                feature: table.labels.get(feature, feature) for feature in dict.fromkeys(display_columns + result.features)
            },
            "threshold": result.threshold,
            "evaluation": result.evaluation,
            "experiments": result.experiments,
            "experiment_split": result.experiment_split,
            "feature_importance": importance,
            "group_importance": group_importance,
            "risk_histogram": _risk_histogram(scores, customers["label"]),
            "level_counts": {level: int((levels == level).sum()) for level in ["high", "medium", "low"]},
            "ring_detection": quality,
            "graph": _graph_stats(graph, customers),
            "reference": result.reference,
            "notes": data.warnings + result.notes,
            "feedback": {
                "n_labels": len(feedback),
                "fraud": sum(1 for value in feedback.values() if value == 1),
                "legit": sum(1 for value in feedback.values() if value == 0),
            },
            "changes": _changes(previous_customers, previous_rings, ids, levels, scores, rings, previous_version),
        }

        with db.write() as connection:
            connection.execute("DELETE FROM customers WHERE dataset_id = ?", (dataset_id,))
            connection.executemany(
                "INSERT INTO customers (dataset_id, customer_id, name, label, truth_ring, open_date, risk, risk_level, "
                "rank, ring_id, degree, high_neighbors, top_reason, features_json, explanation_json, attributes_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                customer_rows,
            )
            connection.execute("DELETE FROM edges WHERE dataset_id = ?", (dataset_id,))
            edge_types = [
                ",".join(kind for kind in graph.attribute_types if row[f"shared_{kind}"])
                for row in graph.edges.to_dict(orient="records")
            ]
            connection.executemany(
                "INSERT INTO edges (dataset_id, source, target, types, weight) VALUES (?, ?, ?, ?, ?)",
                [
                    (dataset_id, source, target, kinds, int(weight))
                    for source, target, kinds, weight in zip(
                        graph.edges["source_customer_id"],
                        graph.edges["target_customer_id"],
                        edge_types,
                        graph.edges["shared_attribute_count"],
                    )
                ],
            )
            connection.execute("DELETE FROM rings WHERE dataset_id = ?", (dataset_id,))
            connection.executemany(
                "INSERT INTO rings (dataset_id, ring_id, size, n_edges, density, score, max_risk, n_high, suspected, "
                "shared_types_json, evidence_json, explanation, truth_json, members_json, open_span_days) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        dataset_id,
                        ring["ring_id"],
                        ring["size"],
                        ring["n_edges"],
                        ring["density"],
                        ring["score"],
                        ring["max_risk"],
                        ring["n_high"],
                        int(ring["suspected"]),
                        dumps(ring["shared_types"]),
                        dumps(ring["evidence"]),
                        ring["explanation"],
                        dumps(ring["truth"]),
                        dumps(ring["members"]),
                        ring["open_span_days"],
                    )
                    for ring in rings
                ],
            )
            if kind != "retrain" and data.events is not None:
                connection.execute("DELETE FROM events WHERE dataset_id = ?", (dataset_id,))
                events = data.events
                connection.executemany(
                    "INSERT INTO events (dataset_id, customer_id, event_date, event_type, credit_limit, utilization) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (
                            dataset_id,
                            customer,
                            pd.Timestamp(date).date().isoformat(),
                            event_type,
                            float(limit) if "credit_limit_at_time" in data.event_columns else None,
                            float(utilization) if "utilization_pct" in data.event_columns else None,
                        )
                        for customer, date, event_type, limit, utilization in zip(
                            events["customer_id"],
                            events["event_date"],
                            events["event_type"],
                            events["credit_limit_at_time"],
                            events["utilization_pct"],
                        )
                    ],
                )
            connection.execute(
                "INSERT OR REPLACE INTO model_runs (dataset_id, version, job_id, created_at, mode, threshold, "
                "n_feedback, metrics_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (dataset_id, version, params.get("job_id"), utcnow(), result.mode, result.threshold, len(feedback), dumps(metrics)),
            )
            summary = {
                "n_customers": int(len(customers)),
                "n_links": int(len(data.links)),
                "n_edges": int(len(graph.edges)),
                "n_events": 0 if data.events is None else int(len(data.events)),
                "attribute_types": data.attribute_types,
                "has_labels": data.has_labels,
                "n_labeled": int(customers["label"].notna().sum()),
                "n_fraud_labels": int((customers["label"] == 1).sum()),
                "label_mode": data.label_mode,
                "mode": result.mode,
                "tabular_features": table.tabular,
                "warnings": data.warnings,
            }
            connection.execute(
                "UPDATE datasets SET status = 'ready', error = NULL, active_version = ?, summary_json = ? WHERE id = ?",
                (version, dumps(summary), dataset_id),
            )
        reporter.progress(1.0, f"Saved model version {version}")
    return {"dataset_id": dataset_id, "version": version, "mode": result.mode}
