# Project Status

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
| HistGradientBoosting | Tabular + Temporal | 0.9398 | 0.7483 | 0.6111 | 0.6728 | 0.7888 | 1559 | 37 | 70 | 110 |
| Random Forest | Combined | 0.9707 | 0.9051 | 0.7944 | 0.8462 | 0.9396 | 1581 | 15 | 37 | 143 |
| HistGradientBoosting | Combined | 0.9769 | 0.9212 | 0.8444 | 0.8812 | 0.9492 | 1583 | 13 | 28 | 152 |

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

Latest full clean run:

```text
pytest -q
2 passed in 70.50s
```

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

## Week 4 Recommendations

- Add time-aware graph snapshots so features are computed only from information available before a scoring date.
- Add an application-level prediction target instead of a customer-level end-state label.
- Add calibration and threshold selection based on fraud-investigation capacity.
- Add precision-recall AUC and lift/recall-at-k reporting.
- Add richer benign entities such as employers, shared IP ranges, student housing, family names, and business addresses.
