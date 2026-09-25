"""Smoke test for the optional contrastive pretraining bolt-on (needs PyTorch)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("torch")

from src.models.contrastive_pretraining import normalized_adjacency, train_embeddings  # noqa: E402


def two_cliques(size: int = 6):
    """Two separate cliques plus isolated nodes, with features that differ by group."""
    rng = np.random.default_rng(0)
    source, target = [], []
    for offset in (0, size):
        for i in range(size):
            for j in range(i + 1, size):
                source.append(offset + i)
                target.append(offset + j)
    n = 2 * size + 4
    x = rng.normal(size=(n, 5)).astype(np.float32)
    x[size : 2 * size] += 3.0
    return x, np.array(source), np.array(target)


def test_normalized_adjacency_is_symmetric_with_self_loops():
    adjacency = normalized_adjacency(4, np.array([0, 1]), np.array([1, 2])).to_dense().numpy()
    np.testing.assert_allclose(adjacency, adjacency.T)
    assert (np.diag(adjacency) > 0).all()
    assert adjacency[3, 3] == pytest.approx(1.0)  # an isolated node keeps only its self-loop


def test_embeddings_are_deterministic_and_separate_the_two_groups():
    x, source, target = two_cliques()
    first = train_embeddings(x, source, target, seed=7, epochs=40, embedding_dim=8, hidden_dim=16, projection_dim=16, batch_size=64, log_every=0)
    second = train_embeddings(x, source, target, seed=7, epochs=40, embedding_dim=8, hidden_dim=16, projection_dim=16, batch_size=64, log_every=0)
    assert first.shape == (len(x), 8)
    np.testing.assert_allclose(first, second, rtol=1e-5, atol=1e-6)
    group_a, group_b = first[:6].mean(axis=0), first[6:12].mean(axis=0)
    within = np.linalg.norm(first[:6] - group_a, axis=1).mean()
    assert np.linalg.norm(group_a - group_b) > within
