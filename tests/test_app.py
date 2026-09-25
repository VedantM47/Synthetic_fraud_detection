"""End-to-end tests for the web backend: upload -> graph -> model -> DB -> API.

The synthetic reference dataset (used to score unlabeled uploads) is generated
once per test session into a temporary folder and shared by every app.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.db import Database  # noqa: E402
from backend.main import create_app  # noqa: E402
from backend.pipeline.explain import explain_customer  # noqa: E402
from backend.pipeline.ingest import (  # noqa: E402
    IngestError,
    build_from_upload,
    normalize_identity,
    preview_file,
    suggest_customer_roles,
)
from backend.pipeline.modeling import shapley_contributions  # noqa: E402
from src.data.generate_temporal_features import compute_temporal_features  # noqa: E402

SAMPLES = ROOT / "sample_data"


@pytest.fixture(scope="session")
def reference_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("reference")


@pytest.fixture()
def client(tmp_path, reference_dir):
    app = create_app(tmp_path / "storage")
    app.state.paths["reference"] = reference_dir
    with TestClient(app) as test_client:
        test_client.app_state = app.state  # type: ignore[attr-defined]
        yield test_client


def wait(client, job_id: str) -> dict:
    job = client.app_state.jobs.wait(job_id, timeout=600)
    assert job["status"] == "completed", job["error"]
    return job


def upload(client, customers: Path, events: Path | None = None) -> dict:
    files = {"customers": (customers.name, customers.read_bytes(), "text/csv")}
    if events is not None:
        files["events"] = (events.name, events.read_bytes(), "text/csv")
    response = client.post("/api/uploads", files=files)
    assert response.status_code == 200, response.text
    return response.json()


def create(client, preview: dict, name: str, label_mode: str = "train", roles: dict | None = None) -> dict:
    mapping = {"customers": {"roles": roles or preview["files"]["customers"]["suggested_roles"], "label_mode": label_mode}}
    if "events" in preview["files"]:
        mapping["events"] = preview["files"]["events"]["suggested_fields"]
    response = client.post("/api/datasets", json={"upload_id": preview["upload_id"], "name": name, "mapping": mapping})
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Unit-level checks
# ---------------------------------------------------------------------------


def test_identity_normalisation_matches_messy_formats():
    assert normalize_identity("phone", "(555) 123-4567") == normalize_identity("phone", "+1 555.123.4567")
    assert normalize_identity("phone", "N/A") is None
    assert normalize_identity("phone", "000-000-0000") is None
    assert normalize_identity("email", " Foo@Example.COM ") == "foo@example.com"
    assert normalize_identity("email", "not-an-email") is None
    assert normalize_identity("address", "12 Main Street") == normalize_identity("address", "12 MAIN ST.")
    assert normalize_identity("national_id", "123-45-6789") == "123456789"


def test_column_roles_are_detected_for_a_foreign_schema():
    roles = suggest_customer_roles(pd.read_csv(SAMPLES / "bank_customers_labeled.csv", dtype=str, keep_default_na=False))
    assert roles["Customer ID"] == "customer_id"
    assert roles["Mobile Number"] == "phone"
    assert roles["Email"] == "email"
    assert {roles[column] for column in ["Street Address", "City", "State", "ZIP"]} == {"address"}
    assert roles["Device ID"] == "device"
    assert roles["Is Fraud"] == "label"
    assert roles["Ring Ref"] == "ring"
    assert roles["Account Opened"] == "open_date"
    assert roles["Annual Income"] == "feature"


def test_city_alone_is_not_used_as_an_identity_link(tmp_path):
    frame = pd.DataFrame({"id": ["a", "b"], "city": ["Paris", "Paris"], "phone": ["5551234567", "5559876543"]})
    path = tmp_path / "c.csv"
    frame.to_csv(path, index=False)
    roles = preview_file(path, "customers")["suggested_roles"]
    assert roles["city"] == "ignore"
    assert roles["phone"] == "phone"


def test_upload_canonicalisation_merges_duplicates_and_parses_labels(tmp_path):
    frame = pd.DataFrame(
        {
            "Client ID": ["c1", "c1", "c2", "c3"],
            "Phone": ["(555) 111-2222", "555-333-4444", "555.111.2222", "n/a"],
            "Fraud?": ["Yes", "Yes", "no", "maybe"],
            "Income": ["$50,000", "", "40000", "30000"],
        }
    )
    path = tmp_path / "customers.csv"
    frame.to_csv(path, index=False)
    roles = {"Client ID": "customer_id", "Phone": "phone", "Fraud?": "label", "Income": "feature"}
    data = build_from_upload({"customers": path}, {"customers": {"roles": roles, "label_mode": "train"}})
    assert list(data.customers["customer_id"]) == ["c1", "c2", "c3"]
    assert list(data.customers["label"].fillna(-1)) == [1.0, 0.0, -1.0]
    assert list(data.customers["income"]) == [50000.0, 40000.0, 30000.0]
    links = data.links.sort_values(["customer_id", "attribute_id"])
    assert len(links) == 3  # two phones for c1, one for c2, the placeholder is dropped
    shared = links.groupby("attribute_id")["customer_id"].nunique()
    assert shared.max() == 2  # c1 and c2 share the (555) 111-2222 number
    assert any("repeated" in warning for warning in data.warnings)


def test_bad_mapping_is_rejected(tmp_path):
    path = tmp_path / "customers.csv"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(path, index=False)
    with pytest.raises(IngestError):
        build_from_upload({"customers": path}, {"customers": {"roles": {"missing": "phone"}}})
    with pytest.raises(IngestError):
        build_from_upload({"customers": path}, {"customers": {"roles": {"a": "customer_id", "b": "customer_id"}}})


def test_shapley_contributions_add_up_to_the_score():
    from sklearn.ensemble import HistGradientBoostingClassifier

    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(400, 4)), columns=["a", "b", "c", "d"])
    y = ((X["a"] + X["b"] > 0.5) | (X["c"] > 1.2)).astype(int)
    model = HistGradientBoostingClassifier(random_state=0).fit(X, y)
    baseline = X[y == 0].median()
    scores, contributions, baseline_score = shapley_contributions(model, X.head(50), baseline)
    np.testing.assert_allclose(contributions.sum(axis=1) + baseline_score, scores, atol=1e-9)
    # "d" is pure noise, so it should matter far less than "a".
    assert np.abs(contributions[:, 3]).mean() < np.abs(contributions[:, 0]).mean()


def test_explanation_names_the_largest_factor():
    explanation = explain_customer(
        risk=0.97,
        level="high",
        features=["network_degree", "phone_shared_count", "account_tenure_days"],
        values={"network_degree": 5, "phone_shared_count": 4, "account_tenure_days": 30},
        contributions=[0.5, 0.3, -0.05],
        labels={},
        shared_counts={"phone": 4},
        degree=5,
        high_neighbors=3,
        ring=None,
        analyst_label=None,
        baseline_score=0.2,
    )
    assert explanation["summary"].startswith("High risk (97/100): flagged because it is linked to 5 other accounts")
    assert "shares a phone number with 4 other accounts" in explanation["summary"]
    assert explanation["mitigating"][0]["text"] == "Has an account that is 30 days old"
    assert "3 of its 5 linked accounts are rated high risk." in explanation["context"]


def test_vectorised_temporal_features_match_a_per_customer_loop():
    events = pd.DataFrame(
        {
            "customer_id": ["a", "a", "a", "b", "b", "c"],
            "event_date": ["2025-01-01", "2025-01-03", "2025-01-20", "2025-02-01", "2025-02-01", "2025-03-05"],
            "event_type": ["purchase", "payment", "purchase", "purchase", "credit_limit_increase", "payment"],
            "utilization_pct": [0.1, 0.2, 0.9, 0.5, 0.4, 0.3],
            "credit_limit_at_time": [1000, 1000, 1500, 2000, 2500, 800],
        }
    )
    features = compute_temporal_features(events).set_index("customer_id")
    assert features.loc["a", "total_event_count"] == 3
    assert features.loc["a", "max_events_7d"] == 2
    assert features.loc["a", "min_days_between_events"] == 2
    assert features.loc["a", "mean_days_between_events"] == pytest.approx(9.5)
    assert features.loc["b", "max_events_single_day"] == 2
    assert features.loc["b", "event_span_days"] == 1  # same-day events use a span of at least 1
    assert features.loc["c", "min_days_between_events"] == 1  # single event falls back to the span
    assert features.loc["a", "utilization_range"] == pytest.approx(0.8)


def test_interrupted_jobs_are_marked_failed_on_restart(tmp_path):
    db = Database(tmp_path / "app.db")
    db.create_dataset("d1", "x", "upload", None, None)
    db.create_job("j1", "d1", "analyze", [], {})
    db.update_job("j1", status="running")
    db.fail_interrupted_jobs()
    assert db.get_job("j1")["status"] == "failed"
    assert db.get_dataset("d1")["status"] == "failed"


# ---------------------------------------------------------------------------
# End-to-end through the API
# ---------------------------------------------------------------------------


def test_unlabeled_upload_finds_rings_and_learns_from_feedback(client):
    preview = upload(client, SAMPLES / "bank_customers_unlabeled.csv")
    assert preview["files"]["customers"]["n_rows"] == 1650
    created = create(client, preview, "Unlabeled bank export")
    job = wait(client, created["job_id"])
    assert [stage["status"] for stage in job["stages"]] == ["done"] * len(job["stages"])
    dataset_id = created["dataset_id"]

    overview = client.get(f"/api/datasets/{dataset_id}/overview").json()
    assert overview["model"]["mode"] == "transfer"
    assert overview["ring_detection"]["n_suspected"] >= 10
    assert overview["graph"]["hub_values_skipped"][0]["customers"] == 60  # the shared office address

    rings = client.get(f"/api/datasets/{dataset_id}/rings", params={"scope": "suspected"}).json()
    assert rings["counts"]["pending"] == rings["total"]
    top = rings["items"][0]
    detail = client.get(f"/api/datasets/{dataset_id}/rings/{top['ring_id']}").json()
    assert detail["evidence"], "a suspected ring should show the identity values its members share"
    assert {node["id"] for node in detail["graph"]["nodes"]} >= set(member["customer_id"] for member in detail["members"])

    member = detail["members"][0]["customer_id"]
    customer = client.get(f"/api/datasets/{dataset_id}/customers/{member}").json()
    assert customer["explanation"]["summary"].startswith("High risk")
    assert customer["connections"], "ring members are linked to other accounts"
    total = customer["explanation"]["baseline_score"] + sum(c["impact"] for c in customer["explanation"]["contributions"])
    assert total == pytest.approx(customer["risk"] * 100, abs=0.5)

    # Analyst confirms one ring and dismisses another, then retrains.
    confirm = client.post(f"/api/datasets/{dataset_id}/rings/{top['ring_id']}/review", json={"decision": "confirm", "note": "same device"})
    assert confirm.status_code == 200 and confirm.json()["status"] == "confirmed"
    other = rings["items"][1]["ring_id"]
    assert client.post(f"/api/datasets/{dataset_id}/rings/{other}/review", json={"decision": "dismiss"}).json()["status"] == "dismissed"
    feedback = client.get(f"/api/datasets/{dataset_id}").json()["feedback"]
    assert feedback["retrain_recommended"] and feedback["n_labels"] >= 4

    job = wait(client, client.post(f"/api/datasets/{dataset_id}/retrain").json()["job_id"])
    assert job["result"]["version"] == 2
    metrics = client.get(f"/api/datasets/{dataset_id}/metrics").json()
    assert [row["version"] for row in metrics["history"]] == [1, 2]
    assert metrics["history"][1]["n_feedback"] == feedback["n_labels"]
    assert metrics["history"][1]["changes"] is not None
    # Ring IDs are structural, so the reviewed rings keep their IDs and status.
    after = client.get(f"/api/datasets/{dataset_id}/rings", params={"scope": "all", "status": "confirmed"}).json()
    assert top["ring_id"] in [ring["ring_id"] for ring in after["items"]]
    confirmed_member = client.get(f"/api/datasets/{dataset_id}/customers/{member}").json()
    assert confirmed_member["analyst_label"] == 1

    # Live progress stream replays the finished job.
    with client.stream("GET", f"/api/jobs/{job['id']}/stream") as stream:
        frames = [line for line in stream.iter_lines() if line.startswith("data:")]
    assert json.loads(frames[-1][5:])["status"] == "completed"

    export = client.get(f"/api/datasets/{dataset_id}/export/customers.csv")
    assert export.status_code == 200 and export.text.startswith("customer_id,name,risk_score")


def test_labeled_upload_with_hidden_labels_is_evaluated_honestly(client):
    preview = upload(client, SAMPLES / "bank_customers_labeled.csv", SAMPLES / "bank_account_events.csv")
    created = create(client, preview, "Labeled bank export", label_mode="evaluate")
    wait(client, created["job_id"])
    metrics = client.get(f"/api/datasets/{created['dataset_id']}/metrics").json()["current"]
    assert metrics["mode"] == "transfer"
    assert metrics["experiments"] == []  # labels were hidden, so no supervised experiments
    evaluation = metrics["evaluation"]
    assert evaluation["n"] == 1650 and evaluation["n_positive"] == 150
    assert evaluation["roc_auc"] > 0.85
    assert metrics["ring_detection"]["truth"]["ring_recall"] > 0.6
    assert any("percentages" in note for note in metrics["notes"])


def test_labeled_upload_trains_on_its_own_labels(client):
    preview = upload(client, SAMPLES / "bank_customers_labeled.csv", SAMPLES / "bank_account_events.csv")
    created = create(client, preview, "Labeled bank export", label_mode="train")
    wait(client, created["job_id"])
    metrics = client.get(f"/api/datasets/{created['dataset_id']}/metrics").json()["current"]
    assert metrics["mode"] == "supervised"
    assert "Out-of-fold" in metrics["evaluation"]["scope"]
    experiments = {(row["model"], row["experiment"]): row for row in metrics["experiments"]}
    assert len(experiments) == 8
    assert experiments[("hist_gradient_boosting", "combined")]["roc_auc"] > experiments[("hist_gradient_boosting", "tabular")]["roc_auc"]


def test_synthetic_job_reproduces_the_research_experiments(client):
    response = client.post("/api/datasets/synthetic", json={"seed": 42, "n_legitimate": 8000, "n_fraud": 800})
    assert response.status_code == 201
    wait(client, response.json()["job_id"])
    metrics = client.get(f"/api/datasets/{response.json()['dataset_id']}/metrics").json()["current"]
    rows = {(row["model"], row["experiment"]): row for row in metrics["experiments"]}
    # Same numbers as `python -m src.models.random_forest_baseline` (see PROJECT_STATUS.md).
    assert rows[("random_forest", "combined")]["tp"] == 143 and rows[("random_forest", "combined")]["fp"] == 15
    assert rows[("hist_gradient_boosting", "combined")]["tp"] == 153
    assert rows[("hist_gradient_boosting", "combined")]["roc_auc"] == pytest.approx(0.9457, abs=5e-5)
    assert rows[("random_forest", "tabular")]["roc_auc"] == pytest.approx(0.4911, abs=5e-5)
    assert metrics["ring_detection"]["truth"]["precision"] > 0.9


def test_api_validation_errors(client):
    assert client.get("/api/datasets/nope").status_code == 404
    assert client.get("/api/nope").status_code == 404
    bad = client.post("/api/datasets/synthetic", json={"seed": 1, "n_legitimate": 300, "n_fraud": 500})
    assert bad.status_code == 400
    preview = upload(client, SAMPLES / "bank_customers_unlabeled.csv")
    roles = {column: "ignore" for column in preview["files"]["customers"]["suggested_roles"]}
    roles["Customer ID"] = "customer_id"
    response = client.post(
        "/api/datasets",
        json={"upload_id": preview["upload_id"], "name": "x", "mapping": {"customers": {"roles": roles}}},
    )
    assert response.status_code == 400 and "Nothing to analyse" in response.json()["detail"]
    excel = client.post("/api/uploads", files={"customers": ("book.xlsx", b"PK\x03\x04", "application/octet-stream")})
    assert excel.status_code == 400
