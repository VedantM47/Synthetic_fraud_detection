"""Stretch goal: self-supervised contrastive pretraining on the identity graph.

A GRACE-style graph contrastive learner (Zhu et al., 2020, "Deep Graph
Contrastive Representation Learning"):

1. Two random *views* of the customer identity graph are made by dropping
   edges and masking feature columns.
2. A 2-layer GCN encoder embeds every customer in both views; a small
   projection head maps embeddings into the space where the loss is applied.
3. The NT-Xent loss pulls the two views of the same customer together and
   pushes different customers apart.

No fraud labels are used, so the embeddings are label-free features of the
same kind as the network red flags (both are computed on the full identity
graph). They summarise what a customer's *neighbourhood* looks like, e.g. a
customer whose linked accounts show bust-out behaviour.

The embeddings are bolted on to the existing feature sets and evaluated with
the same ring-aware train/test split as ``random_forest_baseline``. PyTorch
is an optional dependency (``pip install -r requirements-contrastive.txt``).

Run from the project root after the data pipeline:

    python -m src.models.contrastive_pretraining
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler

from src.models.random_forest_baseline import (
    NETWORK_FEATURES,
    TABULAR_FEATURES,
    TEMPORAL_FEATURES,
    evaluate,
    load_split,
    merge_features,
    models,
)

try:  # PyTorch is optional: the rest of the project does not need it.
    import torch
    import torch.nn.functional as F
except ImportError:  # pragma: no cover - exercised only without torch
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]

INPUT_FEATURES = TABULAR_FEATURES + NETWORK_FEATURES + TEMPORAL_FEATURES


def require_torch() -> None:
    if torch is None:
        raise SystemExit(
            "PyTorch is required for contrastive pretraining. Install it with\n"
            "  pip install -r requirements-contrastive.txt"
        )


def prepare_inputs(frame: pd.DataFrame) -> np.ndarray:
    """log1p then standardise (all inputs are non-negative and skewed)."""
    values = np.log1p(frame[INPUT_FEATURES].clip(lower=0).to_numpy(dtype=float))
    return StandardScaler().fit_transform(values).astype(np.float32)


def normalized_adjacency(n_nodes: int, source: np.ndarray, target: np.ndarray, keep: np.ndarray | None = None):
    """Symmetric normalised adjacency with self-loops, D^-1/2 (A + I) D^-1/2."""
    if keep is not None:
        source, target = source[keep], target[keep]
    loops = np.arange(n_nodes)
    rows = np.concatenate([source, target, loops])
    cols = np.concatenate([target, source, loops])
    degree = np.bincount(rows, minlength=n_nodes).astype(np.float32)
    inv_sqrt = 1.0 / np.sqrt(degree)
    weights = inv_sqrt[rows] * inv_sqrt[cols]
    indices = torch.from_numpy(np.vstack([rows, cols]).astype(np.int64))
    values = torch.from_numpy(weights.astype(np.float32))
    # Indices are valid by construction, so the (slow) invariant checks are skipped.
    return torch.sparse_coo_tensor(indices, values, (n_nodes, n_nodes), check_invariants=False).coalesce()


def build_model(input_dim: int, hidden_dim: int, embedding_dim: int, projection_dim: int):
    class GCNEncoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.layer1 = torch.nn.Linear(input_dim, hidden_dim)
            self.layer2 = torch.nn.Linear(hidden_dim, embedding_dim)

        def forward(self, x, adjacency):
            hidden = F.relu(torch.sparse.mm(adjacency, self.layer1(x)))
            return torch.sparse.mm(adjacency, self.layer2(hidden))

    encoder = GCNEncoder()
    projector = torch.nn.Sequential(
        torch.nn.Linear(embedding_dim, projection_dim),
        torch.nn.ELU(),
        torch.nn.Linear(projection_dim, embedding_dim),
    )
    return encoder, projector


def nt_xent(z1, z2, temperature: float):
    """GRACE loss: positives are the same node in the other view; negatives
    are all other nodes in both views."""
    z1 = F.normalize(z1, dim=1)
    z2 = F.normalize(z2, dim=1)

    def one_side(a, b):
        between = torch.exp(a @ b.t() / temperature)
        within = torch.exp(a @ a.t() / temperature)
        positive = between.diag()
        denominator = between.sum(1) + within.sum(1) - within.diag()
        return -torch.log(positive / denominator)

    return 0.5 * (one_side(z1, z2) + one_side(z2, z1)).mean()


def train_embeddings(
    x: np.ndarray,
    source: np.ndarray,
    target: np.ndarray,
    seed: int = 42,
    epochs: int = 200,
    hidden_dim: int = 64,
    embedding_dim: int = 32,
    projection_dim: int = 64,
    learning_rate: float = 1e-3,
    temperature: float = 0.5,
    edge_drop: tuple[float, float] = (0.3, 0.4),
    feature_drop: tuple[float, float] = (0.2, 0.3),
    batch_size: int = 2048,
    log_every: int = 50,
) -> np.ndarray:
    """Train the contrastive encoder and return one embedding per node."""
    require_torch()
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    n_nodes, input_dim = x.shape
    features = torch.from_numpy(x)
    encoder, projector = build_model(input_dim, hidden_dim, embedding_dim, projection_dim)
    optimizer = torch.optim.Adam(list(encoder.parameters()) + list(projector.parameters()), lr=learning_rate, weight_decay=1e-5)

    def view(edge_rate: float, feature_rate: float):
        keep = rng.random(len(source)) >= edge_rate
        mask = torch.from_numpy((rng.random(input_dim) >= feature_rate).astype(np.float32))
        return features * mask, normalized_adjacency(n_nodes, source, target, keep)

    for epoch in range(1, epochs + 1):
        encoder.train()
        projector.train()
        optimizer.zero_grad()
        x1, a1 = view(edge_drop[0], feature_drop[0])
        x2, a2 = view(edge_drop[1], feature_drop[1])
        batch = torch.from_numpy(rng.choice(n_nodes, size=min(batch_size, n_nodes), replace=False))
        z1 = projector(encoder(x1, a1)[batch])
        z2 = projector(encoder(x2, a2)[batch])
        loss = nt_xent(z1, z2, temperature)
        loss.backward()
        optimizer.step()
        if log_every and (epoch == 1 or epoch % log_every == 0):
            print(f"  epoch {epoch:4d}  contrastive loss {loss.item():.4f}")

    encoder.eval()
    with torch.no_grad():
        embeddings = encoder(features, normalized_adjacency(n_nodes, source, target))
    return embeddings.numpy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Graph contrastive pretraining bolt-on experiment.")
    processed = Path(__file__).parents[2] / "data" / "processed"
    parser.add_argument("--train", type=Path, default=processed / "train.csv")
    parser.add_argument("--test", type=Path, default=processed / "test.csv")
    parser.add_argument("--features", type=Path, default=processed / "customer_features.csv")
    parser.add_argument("--temporal-features", type=Path, default=processed / "customer_temporal_features.csv")
    parser.add_argument("--edges", type=Path, default=processed / "customer_edges.csv")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parents[2] / "outputs" / "models" / "contrastive")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--epochs", type=int, default=200)
    args = parser.parse_args()
    require_torch()
    torch.set_num_threads(max(1, torch.get_num_threads()))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    train_df = load_split(args.train)
    test_df = load_split(args.test)
    everyone = pd.concat([train_df, test_df], ignore_index=True)[["customer_id"]]
    everyone = merge_features(everyone, args.features, NETWORK_FEATURES)
    everyone = merge_features(everyone, args.temporal_features, TEMPORAL_FEATURES)
    everyone = everyone.merge(
        pd.concat([train_df, test_df])[["customer_id", *TABULAR_FEATURES]], on="customer_id", how="left"
    )
    index = {customer: i for i, customer in enumerate(everyone["customer_id"])}
    edges = pd.read_csv(args.edges, usecols=["source_customer_id", "target_customer_id"])
    source = edges["source_customer_id"].map(index).to_numpy(dtype=np.int64)
    target = edges["target_customer_id"].map(index).to_numpy(dtype=np.int64)
    x = prepare_inputs(everyone)
    print(f"Graph: {len(everyone):,} customers, {len(edges):,} edges, {x.shape[1]} input features")

    base_train = merge_features(merge_features(train_df, args.features, NETWORK_FEATURES), args.temporal_features, TEMPORAL_FEATURES)
    base_test = merge_features(merge_features(test_df, args.features, NETWORK_FEATURES), args.temporal_features, TEMPORAL_FEATURES)
    combined = TABULAR_FEATURES + NETWORK_FEATURES + TEMPORAL_FEATURES
    y_train = train_df["is_synthetic_fraud"]
    y_test = test_df["is_synthetic_fraud"]

    rows = []
    for model_name, model in models().items():
        metrics, _, probas = evaluate(model, base_train[combined], y_train, base_test[combined], y_test)
        rows.append({"seed": None, "model": model_name, "experiment": "combined", **metrics, "pr_auc": average_precision_score(y_test, probas)})

    for seed in args.seeds:
        start = time.time()
        print(f"Seed {seed}: training the contrastive encoder")
        embeddings = train_embeddings(x, source, target, seed=seed, epochs=args.epochs)
        print(f"  trained in {time.time() - start:.1f}s")
        columns = [f"gcl_{i:02d}" for i in range(embeddings.shape[1])]
        frame = pd.DataFrame(embeddings, columns=columns)
        frame.insert(0, "customer_id", everyone["customer_id"].to_numpy())
        frame.to_csv(args.output_dir / f"contrastive_embeddings_seed{seed}.csv", index=False)
        train_x = base_train.merge(frame, on="customer_id", how="left")
        test_x = base_test.merge(frame, on="customer_id", how="left")

        probe = LogisticRegression(max_iter=2000, class_weight="balanced")
        metrics, _, probas = evaluate(probe, train_x[columns], y_train, test_x[columns], y_test)
        rows.append({"seed": seed, "model": "logistic_probe", "experiment": "contrastive_only", **metrics, "pr_auc": average_precision_score(y_test, probas)})
        for experiment, feature_list in [
            ("contrastive_only", columns),
            ("combined_contrastive", combined + columns),
        ]:
            for model_name, model in models().items():
                metrics, _, probas = evaluate(model, train_x[feature_list], y_train, test_x[feature_list], y_test)
                rows.append({"seed": seed, "model": model_name, "experiment": experiment, **metrics, "pr_auc": average_precision_score(y_test, probas)})

    results = pd.DataFrame(rows)
    results.to_csv(args.output_dir / "contrastive_metrics.csv", index=False)
    summary = (
        results.groupby(["model", "experiment"], sort=False)[["precision", "recall", "f1", "roc_auc", "pr_auc"]]
        .agg(["mean", "std"])
        .round(4)
    )
    text = summary.to_string()
    with open(args.output_dir / "contrastive_report.txt", "w", encoding="utf-8") as handle:
        handle.write(f"Seeds: {args.seeds}; epochs: {args.epochs}\n\n{text}\n")
    print(text)
    print(f"Saved contrastive outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
