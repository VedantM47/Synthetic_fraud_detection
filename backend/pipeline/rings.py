"""Fraud-ring candidate detection and ring-level scoring.

Ring candidates are purely structural: connected groups of customers linked
by shared identity attributes (large groups are split with Louvain community
detection). Because they do not depend on the model, ring IDs stay stable
when the model is retrained with analyst feedback; only their risk changes.
A candidate is a *suspected ring* when at least two members are high risk or
the average member risk is above the alert threshold.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from backend import settings


def ring_candidates(edges: pd.DataFrame, max_ring_size: int) -> list[list[str]]:
    graph = nx.Graph()
    for source, target, weight in zip(
        edges["source_customer_id"], edges["target_customer_id"], edges["shared_attribute_count"]
    ):
        graph.add_edge(source, target, weight=float(weight))
    groups: list[list[str]] = []
    for component in nx.connected_components(graph):
        if len(component) <= max_ring_size:
            groups.append(sorted(component))
            continue
        subgraph = graph.subgraph(component)
        communities = nx.community.louvain_communities(subgraph, weight="weight", seed=settings.RANDOM_SEED)
        groups.extend(sorted(community) for community in communities if len(community) >= 2)
    groups.sort(key=lambda members: (-len(members), members[0]))
    return groups


def ring_id(index: int) -> str:
    return f"R-{index:04d}"


def edge_types(edges: pd.DataFrame) -> list[list[str]]:
    flag_columns = [column for column in edges.columns if column.startswith("shared_") and column != "shared_attribute_count"]
    if edges.empty:
        return []
    flags = edges[flag_columns].to_numpy().astype(bool)
    names = [column.removeprefix("shared_") for column in flag_columns]
    return [[names[j] for j in np.flatnonzero(row)] for row in flags]


def summarize_rings(
    groups: list[list[str]],
    edges: pd.DataFrame,
    links: pd.DataFrame,
    customers: pd.DataFrame,
    scores: pd.Series,
    threshold: float,
) -> list[dict]:
    """Build one summary dict per ring candidate (``scores`` indexed by customer_id)."""
    membership = {customer: ring_id(index) for index, members in enumerate(groups, start=1) for customer in members}
    types_per_edge = edge_types(edges)
    internal: dict[str, dict] = {}
    for (source, target), kinds in zip(
        zip(edges["source_customer_id"], edges["target_customer_id"]), types_per_edge
    ):
        rid = membership.get(source)
        if rid is None or rid != membership.get(target):
            continue
        entry = internal.setdefault(rid, {"n_edges": 0, "types": {}})
        entry["n_edges"] += 1
        for kind in kinds:
            entry["types"][kind] = entry["types"].get(kind, 0) + 1

    ring_links = links.assign(ring_id=links["customer_id"].map(membership)).dropna(subset=["ring_id"])
    evidence: dict[str, list[dict]] = {}
    if len(ring_links):
        shared = (
            ring_links.groupby(["ring_id", "attribute_type", "attribute_id"])
            .agg(value=("attribute_value", "first"), members=("customer_id", "nunique"))
            .reset_index()
        )
        shared = shared[shared["members"] >= 2].sort_values(["ring_id", "members"], ascending=[True, False])
        for rid, rows in shared.groupby("ring_id", sort=False):
            evidence[rid] = [
                {"attribute_type": row.attribute_type, "value": row.value, "members": int(row.members)}
                for row in rows.head(12).itertuples()
            ]

    ids = customers["customer_id"].to_numpy()
    score_of = scores.to_dict()
    label_of = dict(zip(ids, customers["label"].to_numpy(dtype=float)))
    truth_of = dict(zip(ids, customers["truth_ring"].astype(str)))
    opened = pd.to_datetime(customers["open_date"].replace("", np.nan), errors="coerce")
    open_of = dict(zip(ids, opened))
    has_labels = customers["label"].notna().any()
    has_truth = customers["truth_ring"].astype(str).ne("").any()
    rings = []
    for index, members in enumerate(groups, start=1):
        rid = ring_id(index)
        member_scores = np.array([score_of[member] for member in members], dtype=float)
        order = np.argsort(-member_scores, kind="mergesort")
        ordered_members = [members[i] for i in order]
        n = len(members)
        stats = internal.get(rid, {"n_edges": 0, "types": {}})
        n_high = int((member_scores >= threshold).sum())
        mean_risk = float(member_scores.mean())
        open_dates = [open_of[member] for member in members if pd.notna(open_of[member])]
        truth = None
        if has_labels or has_truth:
            labels = np.array([label_of[member] for member in members])
            truth_counts: dict[str, int] = {}
            for member in members:
                if truth_of[member]:
                    truth_counts[truth_of[member]] = truth_counts.get(truth_of[member], 0) + 1
            dominant = max(truth_counts.items(), key=lambda item: (item[1], item[0])) if truth_counts else None
            truth = {
                "n_labeled": int((~np.isnan(labels)).sum()),
                "n_fraud": int((labels == 1).sum()),
                "dominant_truth_ring": dominant[0] if dominant else None,
                "dominant_count": dominant[1] if dominant else 0,
            }
        rings.append(
            {
                "ring_id": rid,
                "members": ordered_members,
                "size": n,
                "n_edges": stats["n_edges"],
                "density": stats["n_edges"] / (n * (n - 1) / 2) if n > 1 else 0.0,
                "shared_types": dict(sorted(stats["types"].items(), key=lambda item: -item[1])),
                "evidence": evidence.get(rid, []),
                "score": mean_risk,
                "max_risk": float(member_scores.max()),
                "n_high": n_high,
                "suspected": bool(n_high >= 2 or mean_risk >= threshold),
                "open_span_days": int((max(open_dates) - min(open_dates)).days) if len(open_dates) >= 2 else None,
                "truth": truth,
            }
        )
    return rings


def ring_detection_quality(rings: list[dict], customers: pd.DataFrame) -> dict:
    """How well suspected rings line up with known labels / known rings."""
    suspected = [ring for ring in rings if ring["suspected"]]
    result = {"n_candidates": len(rings), "n_suspected": len(suspected), "truth": None}
    labels = customers.set_index("customer_id")["label"]
    if labels.notna().sum() == 0:
        return result
    label_of = labels.to_dict()
    majority_fraud = [
        ring
        for ring in suspected
        if sum(1 for member in ring["members"] if label_of[member] == 1) > len(ring["members"]) / 2
    ]
    fraud_ids = set(labels[labels == 1].index)
    in_suspected = {customer for ring in suspected for customer in ring["members"]}
    truth = {
        "precision": len(majority_fraud) / len(suspected) if suspected else None,
        "member_recall": len(fraud_ids & in_suspected) / len(fraud_ids) if fraud_ids else None,
        "n_fraud_customers": len(fraud_ids),
        "ring_recall": None,
        "n_true_rings": None,
    }
    truth_rings = customers[customers["truth_ring"].astype(str) != ""].groupby("truth_ring")["customer_id"].apply(set)
    truth_rings = truth_rings[truth_rings.apply(len) >= 2]
    if len(truth_rings):
        suspected_sets = [set(ring["members"]) for ring in suspected]
        found = sum(
            1 for members in truth_rings if any(len(members & candidate) >= 2 for candidate in suspected_sets)
        )
        truth["ring_recall"] = found / len(truth_rings)
        truth["n_true_rings"] = int(len(truth_rings))
    result["truth"] = truth
    return result
