"""Identity graph construction and model feature assembly."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.pipeline.ingest import ATTRIBUTE_TYPE_LABELS, CanonicalData
from src.data.build_customer_graph import CORE_ATTRIBUTE_TYPES, build_edge_records, edge_attribute_types
from src.data.generate_red_flag_features import compute_features
from src.data.generate_temporal_features import TEMPORAL_FEATURE_COLUMNS, compute_temporal_features

TEMPORAL_ALWAYS = [
    "total_event_count",
    "distinct_event_dates",
    "event_span_days",
    "events_per_30_days",
    "max_events_single_day",
    "max_events_7d",
    "min_days_between_events",
    "mean_days_between_events",
]
TEMPORAL_REQUIRES = {
    "event_type": ["purchase_count", "payment_count", "limit_increase_count"],
    "utilization_pct": ["mean_utilization_pct", "max_utilization_pct", "utilization_range"],
    "credit_limit_at_time": ["max_credit_limit"],
}

FEATURE_LABELS = {
    "network_degree": "Linked accounts",
    "shared_attribute_count": "Shared identity links",
    "total_event_count": "Account events",
    "purchase_count": "Purchases",
    "payment_count": "Payments",
    "limit_increase_count": "Credit-limit increases",
    "distinct_event_dates": "Active days",
    "event_span_days": "Activity span (days)",
    "events_per_30_days": "Events per 30 days",
    "max_events_single_day": "Most events in one day",
    "max_events_7d": "Most events in 7 days",
    "min_days_between_events": "Shortest gap between events (days)",
    "mean_days_between_events": "Average gap between events (days)",
    "mean_utilization_pct": "Average utilization",
    "max_utilization_pct": "Peak utilization",
    "utilization_range": "Utilization swing",
    "max_credit_limit": "Highest credit limit",
}


def count_feature(attribute_type: str) -> str:
    return f"{attribute_type}_shared_count"


def feature_label(feature: str, extra: dict[str, str] | None = None) -> str:
    if extra and feature in extra:
        return extra[feature]
    if feature in FEATURE_LABELS:
        return FEATURE_LABELS[feature]
    if feature.endswith("_shared_count"):
        kind = feature.removesuffix("_shared_count")
        return f"Accounts sharing {ATTRIBUTE_TYPE_LABELS.get(kind, kind.replace('_', ' '))}"
    return feature.replace("_", " ").capitalize()


@dataclass
class GraphResult:
    edges: pd.DataFrame
    attribute_types: list[str]
    hub_values: list[dict]
    group_sizes: pd.Series  # customers per attribute_id


def build_graph(data: CanonicalData, max_group_size: int) -> GraphResult:
    links = data.links
    group_sizes = links.groupby("attribute_id")["customer_id"].nunique() if len(links) else pd.Series(dtype=int)
    hubs = group_sizes[group_sizes > max_group_size].sort_values(ascending=False)
    hub_values = []
    if len(hubs):
        first_rows = links.drop_duplicates("attribute_id").set_index("attribute_id")
        for attribute_id, size in hubs.head(10).items():
            hub_values.append(
                {
                    "attribute_type": str(first_rows.at[attribute_id, "attribute_type"]),
                    "value": str(first_rows.at[attribute_id, "attribute_value"]),
                    "customers": int(size),
                }
            )
    edge_links = links[["customer_id", "attribute_type", "attribute_id"]]
    types = edge_attribute_types(edge_links)
    edges = build_edge_records(edge_links, attribute_types=types, max_group_size=max_group_size)
    return GraphResult(edges=edges, attribute_types=types, hub_values=hub_values, group_sizes=group_sizes)


def restrict_edges(edges: pd.DataFrame, degree_types: list[str]) -> pd.DataFrame:
    """Keep edges that share at least one of ``degree_types`` and recount them."""
    flags = [f"shared_{kind}" for kind in degree_types if f"shared_{kind}" in edges.columns]
    if not flags:
        return edges.iloc[0:0]
    kept = edges[edges[flags].sum(axis=1) > 0].copy()
    kept["shared_attribute_count"] = kept[flags].sum(axis=1)
    return kept


def network_features(
    customer_ids: pd.Series,
    edges: pd.DataFrame,
    degree_types: list[str] | None = None,
) -> pd.DataFrame:
    """Per-customer network features for every customer (zeros when unlinked).

    Per-type counts always use all edges. ``network_degree`` and
    ``shared_attribute_count`` can be limited to ``degree_types`` so a
    transfer model sees the same definition as its training data.
    """
    base = compute_features(edges)
    frame = pd.DataFrame({"customer_id": customer_ids.to_numpy()})
    frame = frame.merge(base, on="customer_id", how="left")
    if degree_types is not None:
        restricted = compute_features(restrict_edges(edges, degree_types))
        frame = frame.drop(columns=["network_degree", "shared_attribute_count"]).merge(
            restricted[["customer_id", "network_degree", "shared_attribute_count"]], on="customer_id", how="left"
        )
    value_columns = [column for column in frame.columns if column != "customer_id"]
    frame[value_columns] = frame[value_columns].fillna(0).astype(float)
    return frame


def temporal_features(data: CanonicalData) -> tuple[pd.DataFrame, list[str]]:
    """Temporal features for every customer plus the list that is meaningful."""
    frame = pd.DataFrame({"customer_id": data.customers["customer_id"].to_numpy()})
    if data.events is None or data.events.empty:
        for column in TEMPORAL_FEATURE_COLUMNS:
            frame[column] = 0.0
        return frame, []
    computed = compute_temporal_features(data.events)
    frame = frame.merge(computed, on="customer_id", how="left")
    frame[TEMPORAL_FEATURE_COLUMNS] = frame[TEMPORAL_FEATURE_COLUMNS].fillna(0).astype(float)
    available = list(TEMPORAL_ALWAYS)
    for column, dependent in TEMPORAL_REQUIRES.items():
        if column in data.event_columns:
            available.extend(dependent)
    ordered = [column for column in TEMPORAL_FEATURE_COLUMNS if column in available]
    return frame, ordered


@dataclass
class FeatureTable:
    frame: pd.DataFrame  # one row per customer, same order as data.customers
    tabular: list[str]
    network: list[str]
    temporal: list[str]
    labels: dict[str, str]

    @property
    def all_features(self) -> list[str]:
        return self.tabular + self.network + self.temporal


def assemble_features(data: CanonicalData, graph: GraphResult) -> FeatureTable:
    """Full feature table with every network count type (supervised use)."""
    customer_ids = data.customers["customer_id"]
    network = network_features(customer_ids, graph.edges)
    temporal, temporal_available = temporal_features(data)
    frame = data.customers[["customer_id", *data.tabular_features]].merge(network, on="customer_id", how="left")
    frame = frame.merge(temporal, on="customer_id", how="left")

    count_columns = [count_feature(kind) for kind in graph.attribute_types]
    shared_types = [
        kind
        for kind in graph.attribute_types
        if count_feature(kind) in frame.columns and frame[count_feature(kind)].gt(0).any()
    ]
    # Core types keep the research order; types with no sharing carry no signal.
    network_columns = [count_feature(kind) for kind in graph.attribute_types if kind in shared_types]
    network_columns += ["network_degree", "shared_attribute_count"]
    for column in count_columns:
        if column not in frame.columns:
            frame[column] = 0.0

    labels = {feature: feature_label(feature, data.feature_labels) for feature in frame.columns}
    return FeatureTable(
        frame=frame.reset_index(drop=True),
        tabular=list(data.tabular_features),
        network=network_columns if shared_types else [],
        temporal=temporal_available,
        labels=labels,
    )


def core_types_present(attribute_types: list[str]) -> list[str]:
    return [kind for kind in CORE_ATTRIBUTE_TYPES if kind in attribute_types]
