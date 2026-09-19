from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Everything the app writes lives under one folder so it can be wiped or
# pointed elsewhere (tests use a temporary directory).
STORAGE_DIR = Path(os.environ.get("FRAUD_APP_STORAGE", ROOT / "storage")).resolve()
FRONTEND_DIST = ROOT / "frontend" / "dist"
SAMPLE_DATA_DIR = ROOT / "sample_data"

RANDOM_SEED = 42

# Attribute values shared by more customers than this are treated as generic
# (placeholders, office addresses, shared Wi-Fi) and not expanded into edges.
MAX_ATTRIBUTE_GROUP_SIZE = int(os.environ.get("FRAUD_APP_MAX_GROUP_SIZE", 50))

# Connected groups larger than this are split with Louvain community
# detection before being presented as ring candidates.
MAX_RING_SIZE = int(os.environ.get("FRAUD_APP_MAX_RING_SIZE", 30))

CV_FOLDS = 5
# Explanations list factors that move the risk score by at least this much.
MIN_REASON_CONTRIBUTION = 0.02
# Feedback labels from analysts count more than a single reference row when
# the model is retrained in transfer mode.
FEEDBACK_SAMPLE_WEIGHT = 5.0

# Upload limits.
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
PREVIEW_ROWS = 8

# Graph viewer limits.
MAX_GRAPH_NODES = 1500


def storage_paths(storage_dir: Path | None = None) -> dict[str, Path]:
    base = Path(storage_dir) if storage_dir is not None else STORAGE_DIR
    return {
        "base": base,
        "db": base / "app.db",
        "uploads": base / "uploads",
        "datasets": base / "datasets",
        "reference": base / "reference",
    }
