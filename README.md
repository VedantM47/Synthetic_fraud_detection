# Synthetic Identity Fraud Detection

This project creates a deterministic synthetic identity fraud dataset and evaluates whether identity-graph and temporal behavior features add predictive value beyond plain customer attributes.

The goal is not to maximize a metric. The current experiment is designed to make fraud detection harder and more scientifically defensible by adding legitimate shared identity attributes, sparse fraud-ring behavior, mixed graph edges, and temporal noise.

## What The Pipeline Does

1. Generates legitimate customer profiles.
2. Injects synthetic fraud-ring customers.
3. Generates identity attributes: phone, email, address, and device.
4. Creates realistic legitimate sharing, such as households and shared contact phones.
5. Creates fraud-ring sharing with probabilistic, imperfect connectivity.
6. Generates temporal credit/account events.
7. Splits customers into train/test while keeping fraud rings together.
8. Builds a customer identity graph from shared attributes.
9. Generates graph red-flag features.
10. Generates customer-level temporal behavior features.
11. Trains Random Forest and HistGradientBoosting models.
12. Saves metrics, predictions, and feature importance outputs.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Run The Complete Pipeline

From the project root:

```bash
python -m data_generation.run_all
python -m src.data.split_data
python -m src.data.build_customer_graph
python -m src.data.generate_red_flag_features
python -m src.data.generate_temporal_features
python -m src.data.validate_graph
python -m src.models.random_forest_baseline
pytest -q
```

Generated data is written under `data/`. Model outputs are written under `outputs/models/rf_baseline/`.

## Generated Data

| File | Purpose |
|---|---|
| `data/raw/customers.csv` | Customer profiles, fraud label, and fraud ring ID for ground truth. |
| `data/raw/phones.csv` | Phone attributes. |
| `data/raw/emails.csv` | Email attributes. |
| `data/raw/addresses.csv` | Address attributes. |
| `data/raw/devices.csv` | Device attributes. |
| `data/raw/customer_attribute_links.csv` | Customer-to-attribute links used to build graph edges. |
| `data/raw/events.csv` | Temporal account events. |
| `data/raw/ring_ground_truth.csv` | Fraud-ring membership for validation/debugging. |
| `data/processed/train.csv` | Ring-aware training split. |
| `data/processed/test.csv` | Ring-aware test split. |
| `data/processed/customer_edges.csv` | Customer graph edges from shared identity attributes. |
| `data/processed/customer_features.csv` | Per-customer graph features. |
| `data/processed/customer_temporal_features.csv` | Per-customer temporal behavior features. |

## Fraud Ring Simulation

Fraud-ring customers are generated with the same tabular distributions as legitimate customers, so income and credit score should not trivially reveal the label.

Fraud rings share identity attributes more often than legitimate customers, but not perfectly:

- each ring selects one to three candidate shared attribute types
- individual ring members share those attributes probabilistically
- every ring keeps at least one shared pair for graph validation
- some fraud customers share an attribute with a legitimate customer

This keeps the fraud signal present without making every ring a perfect clique.

## Legitimate Sharing

Legitimate customers can now share identity attributes for synthetic reasons:

- household members share an address
- some households share a phone
- a small number share a device
- contact pairs can share a phone

These are not random edges. They are generated as plausible benign relationships.

## Identity Graph

`src.data.build_customer_graph` creates an undirected customer graph. Two customers are connected when they share at least one identity attribute.

Edge columns:

- `shared_phone`
- `shared_email`
- `shared_address`
- `shared_device`
- `shared_attribute_count`

`src.data.generate_red_flag_features` aggregates edges into customer-level network features:

- `phone_shared_count`
- `email_shared_count`
- `address_shared_count`
- `device_shared_count`
- `network_degree`
- `shared_attribute_count`

## Temporal Features

`src.data.generate_temporal_features` aggregates `events.csv` into customer-level behavior features:

- event counts
- purchase/payment/limit-increase counts
- distinct active dates
- event span and event frequency
- maximum events in one day
- maximum events in a 7-day window
- minimum and mean days between events
- mean, max, and range of utilization
- maximum credit limit

The generator no longer makes bust-out behavior guaranteed for every fraud customer. Some legitimate customers also have high-utilization bursts, so temporal behavior overlaps across classes.

## Models

The experiment runner evaluates:

- Random Forest
- HistGradientBoostingClassifier

Feature groups:

- `tabular`: income, credit score, account tenure
- `tabular_network`: tabular + graph features
- `tabular_temporal`: tabular + temporal features
- `combined`: tabular + graph + temporal

Metrics saved for every run:

- accuracy
- precision
- recall
- F1
- ROC-AUC
- confusion matrix counts

Random Forest feature importances and aggregate feature-group importances are also saved.

## Current Results

Latest clean run:

```text
pytest -q
2 passed in 70.50s
```

| Model | Feature Set | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---:|---:|---:|---:|---:|
| Random Forest | Tabular | 0.8682 | 0.1029 | 0.0389 | 0.0565 | 0.4911 |
| HistGradientBoosting | Tabular | 0.7095 | 0.0922 | 0.2111 | 0.1284 | 0.4746 |
| Random Forest | Tabular + Network | 0.9623 | 0.8509 | 0.7611 | 0.8035 | 0.9153 |
| HistGradientBoosting | Tabular + Network | 0.9600 | 0.8263 | 0.7667 | 0.7954 | 0.9184 |
| Random Forest | Tabular + Temporal | 0.9482 | 0.8929 | 0.5556 | 0.6849 | 0.7888 |
| HistGradientBoosting | Tabular + Temporal | 0.9398 | 0.7483 | 0.6111 | 0.6728 | 0.7888 |
| Random Forest | Combined | 0.9707 | 0.9051 | 0.7944 | 0.8462 | 0.9396 |
| HistGradientBoosting | Combined | 0.9769 | 0.9212 | 0.8444 | 0.8812 | 0.9492 |

The tabular-only Random Forest shows why accuracy is misleading: it gets about 90% accuracy while finding no fraud. Network features provide the strongest incremental lift, temporal features provide a weaker but real signal, and combined features perform best without returning to the earlier near-perfect graph result.

## Leakage Notes

- `is_synthetic_fraud`, `ring_id`, and `group_id` are not used as model features.
- Train/test splitting keeps all members of a fraud ring in one split.
- Tests verify no customer overlap and no fraud-ring overlap.
- Network and temporal feature files do not include the fraud label.
- The graph is currently built from the full identity universe. This assumes the identity graph is available at scoring time. A stricter future experiment should use time-aware graph snapshots.

## Development Notes

Run tests:

```bash
pytest -q
```

Inspect saved metrics:

```bash
type outputs\models\rf_baseline\rf_metrics_report.txt
```

The main status report is in `PROJECT_STATUS.md`.
