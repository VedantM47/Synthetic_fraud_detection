# Graph-Based Synthetic Identity Fraud Detection - Week 1

Week 1 covers environment setup and deterministic synthetic data generation only.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m data_generation.run_all
pytest tests
```

Generated CSVs are written to `data/raw/` and ignored by git.

## Data Dictionary

| File | Column | Description |
|---|---|---|
| customers.csv | customer_id | Seeded synthetic UUID-shaped customer key. |
| customers.csv | full_name | Faker-generated customer name. |
| customers.csv | date_of_birth | Date of birth with age skewed toward 25-55. |
| customers.csv | ssn_like_id | Clearly synthetic identifier prefixed with `SYN`; not a real SSN format. |
| customers.csv | annual_income | Log-normal annual income clipped to the configured realistic range. |
| customers.csv | credit_score | Normally distributed score clipped to 300-850. |
| customers.csv | account_open_date | Account opening date inside the 18-month simulation window. |
| customers.csv | account_tenure_days | Days from account opening through the simulation end date. |
| customers.csv | is_synthetic_fraud | Fraud label: 0 legitimate, 1 synthetic fraud ring member. |
| customers.csv | ring_id | Ground-truth ring identifier for fraud members; blank for legitimate customers. |
| phones.csv | phone_id | Synthetic phone attribute key. |
| phones.csv | phone_number | Fake phone number in a reserved-style `555` format. |
| emails.csv | email_id | Synthetic email attribute key. |
| emails.csv | email_address | Non-deliverable synthetic email address using `example.test`. |
| addresses.csv | address_id | Synthetic address attribute key. |
| addresses.csv | street | Faker-generated street address. |
| addresses.csv | city | Faker-generated city. |
| addresses.csv | state | Faker-generated state abbreviation. |
| addresses.csv | zip | Synthetic ZIP-like value. |
| devices.csv | device_id | Synthetic device attribute key. |
| devices.csv | device_fingerprint | Fake hex hashed-looking device fingerprint. |
| customer_attribute_links.csv | customer_id | Customer key linked to an identity attribute. |
| customer_attribute_links.csv | attribute_type | One of `phone`, `email`, `address`, or `device`. |
| customer_attribute_links.csv | attribute_id | Attribute key resolving to the matching attribute table. |
| events.csv | event_id | Seeded synthetic UUID-shaped event key. |
| events.csv | customer_id | Customer associated with the event. |
| events.csv | event_date | Event date within the simulated account timeline. |
| events.csv | event_type | Account event category. |
| events.csv | credit_limit_at_time | Credit limit at event time. |
| events.csv | utilization_pct | Credit utilization percentage represented from 0.0 to 1.0. |
| ring_ground_truth.csv | ring_id | Fraud ring identifier for evaluation/debugging only. |
| ring_ground_truth.csv | customer_id | Fraud customer belonging to the ring. |

