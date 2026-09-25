# Project Status

## Weeks 6–8: Finish Frontend, Integrate, Explain & Polish — DONE

| Planned item | Status | Where |
|---|---|---|
| Interactive graph viewer | Done | `frontend/src/components/GraphView.tsx`, Network page: packed view of every suspected ring, filters by score, link type and review status, colour by model risk or known labels, click / double-click navigation |
| Customer detail page (risk score + connections) | Done | Customer page: score against the threshold, plain-English explanation, factor chart, 1–2 hop connection graph, linked accounts with the exact shared values, identity details, activity timeline, feature values |
| Fraud-ring review screen, feeding back into the model | Done | Ring review page: confirm / dismiss with notes and per-member selection, audit history, auto-advance; decisions become labels; **Retrain with feedback** creates a new model version with like-for-like before/after metrics |
| Live progress updates while a job runs | Done | Per-stage progress persisted by `backend/jobs.py`, streamed over SSE (`/api/jobs/{id}/stream`) with a polling fallback |
| End-to-end wiring: upload → graph → training → database → frontend | Done | `backend/pipeline/runner.py`, SQLite in `backend/db.py`, FastAPI in `backend/main.py`, React app served by the backend |
| Plain-English explanation per risk score | Done | `backend/pipeline/explain.py`: baseline Shapley attributions turned into sentences such as "flagged because it shares an email address with 6 other accounts" |
| Works on the user's own dataset | Done | Column-role detection and normalisation (`backend/pipeline/ingest.py`), labels optional (a reference model is used without them), sample files in another format in `sample_data/` |
| End-to-end testing and bug fixing | Done | `tests/test_app.py` (API end to end), `tests/test_contrastive.py`; 18 tests pass. Every page was also driven in a real browser. |
| README and demo | Done | `README.md` (setup, usage, architecture, results, 7-minute demo script), `python -m backend.cli demo` to preload data |
| Stretch: contrastive pretraining bolt-on | Done (optional) | `src/models/contrastive_pretraining.py`: GRACE-style GCN, results below |
| Temporal modelling | Deferred as planned | Written up as scoped future work in the README |

### Bugs found and fixed while integrating

- **HistGradientBoosting results depended on CSV parsing noise.** `random_forest_baseline` read feature CSVs with pandas' default float parser, which changes thousands of values by one ulp. Random Forest hides this because it casts to float32; HistGradientBoosting did not. The runner now reads with `float_precision="round_trip"`. Two HistGradientBoosting rows changed (table below), and the research runner and the app now agree exactly.
- **Temporal features took 16 s for 8,800 customers.** They are now vectorised (0.6 s) and bit-identical to the old per-customer loop; so is the network feature computation.
- **Data generation had no size or seed controls** and always wrote to `data/raw`. `generate_all()` now takes `seed`, `n_legitimate`, `n_fraud`, `out_dir` and `progress`, and the defaults reproduce the canonical data byte for byte.
- **Explanation quality.** Single-feature occlusion saturates for customers with redundant red flags: resetting one shared attribute leaves the score at 100. Replaced with baseline Shapley sampling, whose contributions add up exactly to the score. The written reasons are always the largest contributions.
- **Unfair version comparisons.** After a retrain, reviewed customers are excluded from evaluation, which removes the easiest positives. Each version is now also compared with the previous version's scores on the same customers.

### Weeks 6–8 metrics

App, synthetic demo (seed 42), 5-fold ring-aware out-of-fold scores: ROC-AUC 0.957, PR-AUC 0.915. At the F1-optimal threshold, precision is 94.2% (678 of 720 alerts) and recall 84.8%. There are 196 suspected rings among 943 linked groups: 94.4% of them are mostly fraud, and they contain 84.1% of fraud customers and recover 88.9% of the 216 true rings.

Own-data sample (`sample_data/`, different population and format, labels hidden): ROC-AUC 0.948 and PR-AUC 0.896 from the reference model; 32 suspected rings, 87.5% mostly fraud, 82.9% of true rings recovered. Without any labels or events, 33 suspected rings are still found.

Contrastive pretraining (3 seeds): label-free embeddings alone reach ROC-AUC 0.930–0.931. Combined with the hand-engineered features, HistGradientBoosting gets ROC-AUC 0.950 ± 0.003 (vs 0.946) and precision 0.950 (vs 0.895), but F1 0.865 (vs 0.872) and PR-AUC 0.898 (vs 0.907). This is not a clear win, so it stays an optional experiment.

## Current Scope

This project builds a deterministic synthetic identity fraud detection pipeline with:

- synthetic customer and identity attribute generation
- temporal account event generation
- fraud-ring injection
- ring-aware train/test splitting
- customer identity graph construction
- graph red-flag feature generation
- customer-level temporal feature generation
- Random Forest and HistGradientBoosting experiments
- leakage checks, graph validation, tests, and saved model outputs

## Week 3 Changes

- Legitimate customers now share attributes through explicit synthetic explanations:
  - households share addresses
  - some households share phones
  - a small number share devices
  - contact pairs may share a phone
- Fraud rings are no longer perfectly dense:
  - ring members share selected attributes probabilistically
  - every ring keeps at least one minimal shared-attribute pair for ground-truth sanity
  - some fraud customers overlap with legitimate customer attributes
- Temporal behavior is now modeled as observed behavior, not a guaranteed label proxy:
  - only a configured fraction of fraud customers exhibit bust-out behavior
  - some legitimate customers have high-utilization bursts
  - fraud utilization and burst timing overlap with legitimate behavior
- Added `customer_temporal_features.csv`.
- Expanded model experiments to compare:
  - tabular only
  - tabular + network
  - tabular + temporal
  - tabular + network + temporal
- Added HistGradientBoostingClassifier without adding dependencies.
- Added feature importance and aggregate group importance for Random Forest.
- Strengthened tests for leakage, reproducibility, expected feature columns, sensible ranges, and model output files.

## Final Week 3 Metrics

Test set: 1,776 customers, including 180 fraud customers.

| Model | Feature Set | Accuracy | Precision | Recall | F1 | ROC-AUC | TN | FP | FN | TP |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Random Forest | Tabular | 0.8682 | 0.1029 | 0.0389 | 0.0565 | 0.4911 | 1535 | 61 | 173 | 7 |
| HistGradientBoosting | Tabular | 0.7095 | 0.0922 | 0.2111 | 0.1284 | 0.4746 | 1222 | 374 | 142 | 38 |
| Random Forest | Tabular + Network | 0.9623 | 0.8509 | 0.7611 | 0.8035 | 0.9153 | 1572 | 24 | 43 | 137 |
| HistGradientBoosting | Tabular + Network | 0.9600 | 0.8263 | 0.7667 | 0.7954 | 0.9184 | 1567 | 29 | 42 | 138 |
| Random Forest | Tabular + Temporal | 0.9482 | 0.8929 | 0.5556 | 0.6849 | 0.7888 | 1584 | 12 | 80 | 100 |
| HistGradientBoosting | Tabular + Temporal | 0.9403 | 0.7500 | 0.6167 | 0.6768 | 0.7853 | 1559 | 37 | 69 | 111 |
| Random Forest | Combined | 0.9707 | 0.9051 | 0.7944 | 0.8462 | 0.9396 | 1581 | 15 | 37 | 143 |
| HistGradientBoosting | Combined | 0.9747 | 0.8947 | 0.8500 | 0.8718 | 0.9457 | 1578 | 18 | 27 | 153 |

The two HistGradientBoosting rows marked Tabular + Temporal and Combined were corrected in Weeks 6–8. The originally reported values (Tabular + Temporal: F1 0.6728, ROC-AUC 0.7888; Combined: F1 0.8812, ROC-AUC 0.9492) came from lossy CSV float parsing; see "Bugs found and fixed" above. The conclusions are unchanged.

Accuracy is not sufficient for this imbalanced problem. The tabular Random Forest gets high accuracy by almost never finding fraud. Recall, F1, ROC-AUC, and confusion matrices are the main signals.

## Graph Statistics

- Legitimate-legitimate edges: 2,139
- Fraud-fraud edges: 1,094
- Legitimate-fraud mixed edges: 84
- Fraud-ring possible pairs: 1,436
- Fraud-ring connected pairs: 1,094
- Overall fraud-ring pair connectivity: 0.762
- Train/test customer overlap: 0
- Train/test fraud-ring overlap: 0

Network feature means:

| Label | Network Degree | Shared Attribute Count | Phone Shared | Email Shared | Address Shared | Device Shared |
|---|---:|---:|---:|---:|---:|---:|
| Legitimate | 2.053 | 3.049 | 0.962 | 0.000 | 1.879 | 0.208 |
| Fraud | 3.095 | 4.542 | 1.225 | 1.038 | 1.189 | 1.090 |

Fraud remains more connected on average, but legitimate customers now overlap with fraud-like graph characteristics.

## Temporal Feature Definitions

Generated in `data/processed/customer_temporal_features.csv`:

- `total_event_count`: number of events for the customer
- `purchase_count`: purchase events
- `payment_count`: payment events
- `limit_increase_count`: credit limit increase events
- `distinct_event_dates`: number of active dates
- `event_span_days`: days between first and last event
- `events_per_30_days`: event frequency normalized to 30 days
- `max_events_single_day`: busiest event date
- `max_events_7d`: largest rolling 7-day event count
- `min_days_between_events`: shortest event gap
- `mean_days_between_events`: average event gap
- `mean_utilization_pct`: average utilization
- `max_utilization_pct`: maximum utilization
- `utilization_range`: max minus min utilization
- `max_credit_limit`: largest observed credit limit

Temporal means:

| Label | Total Events | Events / 30 Days | Max Events 7d | Max Utilization | Utilization Range |
|---|---:|---:|---:|---:|---:|
| Legitimate | 20.443 | 3.786 | 2.306 | 0.493 | 0.377 |
| Fraud | 18.696 | 3.181 | 2.282 | 0.657 | 0.525 |

## Leakage Review

- Fraud labels are stored in `customers.csv` as `is_synthetic_fraud`.
- Ring IDs are retained for split validation and ground truth, but are not used as model features.
- Network features do not include `is_synthetic_fraud`, `ring_id`, or `group_id`.
- Temporal features do not include `is_synthetic_fraud`, `ring_id`, or `group_id`.
- Train/test splitting is ring-aware.
- No customer appears in both train and test.
- No fraud ring appears in both train and test.
- Graph construction uses the full identity graph available at scoring time. This is a transductive experiment assumption, not direct label leakage. Week 4 should add a stricter time-aware graph snapshot.

## Why Performance Changed

The original graph-enhanced ROC-AUC near 0.9998 came from synthetic structure that made fraud rings too obvious: fraud customers had dense shared-attribute connectivity, while legitimate sharing was limited and regular. Week 3 added realistic legitimate sharing, mixed fraud-legitimate edges, probabilistic fraud-ring sharing, and non-guaranteed temporal bust-out behavior.

The network model still performs well because fraud customers remain more likely to share suspicious combinations of identity attributes. It is no longer near-perfect because legitimate households and contact-sharing create overlapping graph patterns, and some fraud rings are intentionally sparse.

## Validation

Latest full clean run (Weeks 6–8, research pipeline + app end to end + contrastive):

```text
pytest -q
18 passed
```

`npm run typecheck` in `frontend/` passes with strict TypeScript. Every page was also exercised in headless Chrome with no console errors: upload → mapping → live progress → dashboards → ring confirm/dismiss → retrain → version history, in light and dark mode.

The model runner writes:

- `outputs/models/rf_baseline/model_metrics.csv`
- per-model prediction CSVs
- Random Forest feature importance CSVs
- Random Forest feature-group importance CSVs
- `outputs/models/rf_baseline/rf_metrics_report.txt`

## Known Limitations

- The graph is still built from the full identity universe rather than a strict prediction-time snapshot.
- Fraud-ring generation is still synthetic and rule-driven.
- Temporal events are customer-level aggregates, not application-time features.
- HistGradientBoosting does not provide native feature importances in this implementation.
- The notebook is still a basic exploration notebook and has not been upgraded into a full report.
- The web app is single-user: no login, and one background worker runs jobs one at a time.
- Unlabeled uploads are scored by a model trained on synthetic data. It transfers well to data shaped like the generator's, but real data with very different sharing patterns will need analyst feedback (or labels) before the scores can be trusted.
- Attribute values shared by more than 50 customers are ignored as generic; a genuine super-hub ring would be reported in the data-quality notes, not as a ring.
- Linked groups larger than 30 are split with Louvain communities, which can cut a large ring into pieces.

## Week 4 Recommendations

(PR-AUC, recall/precision at top K, F1-based threshold selection and a customer-level review workflow were added in Weeks 6–8. Time-aware snapshots remain deferred; see "Future work" in the README.)

- Add time-aware graph snapshots so features are computed only from information available before a scoring date.
- Add an application-level prediction target instead of a customer-level end-state label.
- Add calibration and threshold selection based on fraud-investigation capacity.
- Add precision-recall AUC and lift/recall-at-k reporting.
- Add richer benign entities such as employers, shared IP ranges, student housing, family names, and business addresses.
