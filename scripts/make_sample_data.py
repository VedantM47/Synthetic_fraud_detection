"""Create the "bring your own data" sample files in ``sample_data/``.

The samples come from a *different* synthetic population (seed 7, 1,650
customers) than the reference dataset the app trains on, and are flattened
into a bank-style export with its own column names and real-world mess:

* phone numbers in mixed formats and some ``N/A`` placeholders
* the address split into street / city / state / ZIP columns, mixed case
* incomes written like ``$45,000``, dates like ``14 Mar 2025``
* ``Yes`` / ``No`` fraud labels and a ``Ring Ref`` column for evaluation
* an office address shared by 60 legitimate employees (a "hub" value)
* events with their own type names and utilization in percent

Run from the project root:  python -m scripts.make_sample_data
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from data_generation.run_all import generate_all

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sample_data"
SEED = 7
N_LEGITIMATE = 1500
N_FRAUD = 150
OFFICE_EMPLOYEES = 60

PHONE_STYLES = [
    lambda d: f"({d[0:3]}) {d[3:6]}-{d[6:10]}",
    lambda d: f"{d[0:3]}.{d[3:6]}.{d[6:10]}",
    lambda d: f"+1 {d[0:3]} {d[3:6]} {d[6:10]}",
    lambda d: f"{d[0:3]}-{d[3:6]}-{d[6:10]}",
]
EVENT_NAMES = {
    "account_opened": "Account Opened",
    "purchase": "Purchase",
    "payment": "Payment",
    "credit_limit_increase": "Limit Increase",
    "bust_out_spike": "Large Purchase",
    "account_closed_or_abandoned": "Account Closed",
}


def main() -> None:
    rng = np.random.default_rng(SEED)
    data = generate_all(seed=SEED, n_legitimate=N_LEGITIMATE, n_fraud=N_FRAUD, write=False)
    customers = data["customers"]
    links = data["links"].pivot(index="customer_id", columns="attribute_type", values="attribute_id")
    phones = data["phones"].set_index("phone_id")["phone_number"]
    emails = data["emails"].set_index("email_id")["email_address"]
    addresses = data["addresses"].set_index("address_id")
    devices = data["devices"].set_index("device_id")["device_fingerprint"]

    rows = []
    for customer in customers.itertuples(index=False):
        attributes = links.loc[customer.customer_id]
        digits = phones[attributes["phone"]].replace("-", "")
        phone = PHONE_STYLES[int(rng.integers(len(PHONE_STYLES)))](digits)
        if rng.random() < 0.02:
            phone = "N/A"
        email = emails[attributes["email"]]
        if rng.random() < 0.15:
            email = email.upper()
        address = addresses.loc[attributes["address"]]
        street = address["street"].upper() if rng.random() < 0.1 else address["street"]
        income = int(customer.annual_income)
        rows.append(
            {
                "Customer ID": f"CUST-{customer.customer_id[:8].upper()}",
                "Full Name": customer.full_name,
                "Mobile Number": phone,
                "Email": email,
                "Street Address": street,
                "City": address["city"],
                "State": address["state"],
                "ZIP": str(address["zip"]),
                "Device ID": devices[attributes["device"]][:16],
                "Annual Income": f"${income:,}" if rng.random() < 0.2 else str(income),
                "Credit Score": int(customer.credit_score),
                "Account Opened": pd.Timestamp(customer.account_open_date).strftime("%d %b %Y"),
                "Is Fraud": "Yes" if customer.is_synthetic_fraud == 1 else "No",
                "Ring Ref": customer.ring_id if isinstance(customer.ring_id, str) else "",
            }
        )
    frame = pd.DataFrame(rows)

    legit_positions = np.flatnonzero(frame["Is Fraud"].eq("No").to_numpy())
    office = rng.choice(legit_positions, size=OFFICE_EMPLOYEES, replace=False)
    frame.loc[office, ["Street Address", "City", "State", "ZIP"]] = ["1 Corporate Plaza", "Springfield", "IL", "62701"]

    ids = dict(zip(customers["customer_id"], frame["Customer ID"]))
    events = data["events"]
    utilization = (events["utilization_pct"] * 100).round(1)
    events_frame = pd.DataFrame(
        {
            "Customer ID": events["customer_id"].map(ids),
            "Date": events["event_date"],
            "Type": events["event_type"].map(EVENT_NAMES),
            "Utilization %": utilization,
            "Credit Limit": events["credit_limit_at_time"],
        }
    )

    OUT.mkdir(exist_ok=True)
    frame.to_csv(OUT / "bank_customers_labeled.csv", index=False)
    frame.drop(columns=["Is Fraud", "Ring Ref"]).to_csv(OUT / "bank_customers_unlabeled.csv", index=False)
    events_frame.to_csv(OUT / "bank_account_events.csv", index=False)
    index = {
        "bank_customers_labeled.csv": (
            f"{len(frame):,} customers in a bank-style export with a Yes/No 'Is Fraud' column and a "
            "'Ring Ref' column. Upload it to train on your labels, or choose 'evaluate only' to test the "
            "reference model against them."
        ),
        "bank_customers_unlabeled.csv": (
            "The same customers without any labels: the app scores them with the reference model and "
            "still surfaces the fraud rings."
        ),
        "bank_account_events.csv": (
            f"{len(events_frame):,} account events for the customers above (optional events file)."
        ),
    }
    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(frame)} customers and {len(events_frame)} events to {OUT}")
    print(f"Fraud customers: {(frame['Is Fraud'] == 'Yes').sum()} in {frame['Ring Ref'].replace('', np.nan).nunique()} rings")


if __name__ == "__main__":
    main()
