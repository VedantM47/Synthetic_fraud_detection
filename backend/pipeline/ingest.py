"""Read uploaded files, suggest column roles and build the canonical dataset.

Every dataset, whether generated synthetically or uploaded by a user in their
own format, is converted into the same canonical form before analysis:

* ``customers``: one row per customer with ``customer_id``, ``name``,
  ``label`` (1/0/NaN), ``truth_ring``, ``open_date`` and numeric features.
* ``links``: customer-to-identity-attribute links with a normalised
  ``attribute_id`` (the matching key) and a display ``attribute_value``.
* ``events``: optional account events used for temporal features.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.generate_temporal_features import TEMPORAL_FEATURE_COLUMNS
from src.models.random_forest_baseline import NETWORK_FEATURES, TABULAR_FEATURES


class IngestError(ValueError):
    """A problem with uploaded data that the user can fix."""


CUSTOMER_ROLES = {
    "ignore": "Ignore",
    "customer_id": "Customer ID",
    "name": "Name",
    "label": "Fraud label",
    "ring": "Known ring ID (evaluation only)",
    "open_date": "Account open date",
    "feature": "Numeric feature",
    "phone": "Phone number",
    "email": "Email address",
    "address": "Address",
    "device": "Device ID / fingerprint",
    "ip": "IP address",
    "national_id": "National ID / SSN",
    "bank_account": "Bank account / card",
    "identifier": "Other shared identifier",
}
IDENTITY_ROLES = ["phone", "email", "address", "device", "ip", "national_id", "bank_account", "identifier"]
SINGLE_ROLES = ["customer_id", "label", "ring", "open_date"]
SENSITIVE_TYPES = {"national_id", "bank_account"}

ATTRIBUTE_TYPE_LABELS = {
    "phone": "phone number",
    "email": "email address",
    "address": "address",
    "device": "device",
    "ip": "IP address",
    "national_id": "national ID",
    "bank_account": "bank account or card",
    "identifier": "identifier",
}

TABULAR_FEATURE_LABELS = {
    "annual_income": "Annual income",
    "credit_score": "Credit score",
    "account_tenure_days": "Account age (days)",
}

RESERVED_NAMES = (
    {"customer_id", "name", "label", "truth_ring", "open_date"}
    | set(NETWORK_FEATURES)
    | set(TEMPORAL_FEATURE_COLUMNS)
    | {f"{kind}_shared_count" for kind in IDENTITY_ROLES}
)

PLACEHOLDER_VALUES = {
    "",
    "-",
    "--",
    "0",
    "na",
    "n/a",
    "n.a.",
    "none",
    "null",
    "nil",
    "nan",
    "unknown",
    "missing",
    "undefined",
    "not available",
    "notavailable",
    "test",
    "xxx",
}

ADDRESS_ABBREVIATIONS = {
    "street": "st",
    "avenue": "ave",
    "road": "rd",
    "drive": "dr",
    "lane": "ln",
    "boulevard": "blvd",
    "court": "ct",
    "place": "pl",
    "apartment": "apt",
    "suite": "ste",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
}

POSITIVE_LABELS = {"1", "1.0", "true", "t", "yes", "y", "fraud", "fraudulent", "bad", "positive", "confirmed"}
NEGATIVE_LABELS = {
    "0",
    "0.0",
    "false",
    "f",
    "no",
    "n",
    "legit",
    "legitimate",
    "genuine",
    "good",
    "normal",
    "negative",
    "clean",
    "not fraud",
    "notfraud",
    "non-fraud",
    "nonfraud",
}

ID_NAMES = [
    "customerid",
    "custid",
    "clientid",
    "userid",
    "accountid",
    "applicantid",
    "applicationid",
    "memberid",
    "personid",
    "partyid",
    "customerno",
    "customernumber",
    "customerref",
    "id",
    "customer",
    "client",
]
LABEL_NAMES = {
    "issyntheticfraud",
    "isfraud",
    "fraud",
    "fraudflag",
    "fraudlabel",
    "label",
    "target",
    "class",
    "isfraudulent",
    "fraudulent",
    "y",
    "fraudindicator",
    "confirmedfraud",
}
RING_NAMES = {"ringid", "fraudringid", "ring", "ringlabel", "ringname", "fraudring"}
OPEN_DATE_NAMES = {
    "accountopendate",
    "opendate",
    "accountopened",
    "dateopened",
    "openeddate",
    "openedon",
    "opened",
    "accountopeningdate",
    "signupdate",
    "createdat",
    "createddate",
    "registrationdate",
    "registered",
    "applicationdate",
    "accountcreated",
    "joindate",
    "joined",
    "onboardingdate",
}
NAME_NAMES = {
    "fullname",
    "name",
    "customername",
    "clientname",
    "applicantname",
    "firstname",
    "lastname",
    "givenname",
    "surname",
    "middlename",
    "accountholder",
    "holdername",
}
DOB_NAMES = {"dateofbirth", "dob", "birthdate", "birthday"}
NUMERIC_HINTS = {
    "income",
    "salary",
    "score",
    "limit",
    "balance",
    "amount",
    "age",
    "days",
    "tenure",
    "count",
    "pct",
    "percent",
    "rate",
    "ratio",
    "utilization",
    "utilisation",
    "months",
    "years",
    "loan",
    "debt",
}
ADDRESS_PART_TOKENS = {
    "city",
    "state",
    "zip",
    "zipcode",
    "postcode",
    "postal",
    "postalcode",
    "pincode",
    "pin",
    "country",
    "province",
    "county",
    "town",
    "region",
}
ID_LIKE_TOKENS = {"id", "no", "number", "num", "ref", "code", "key", "uuid"}

LINK_FIELD_NAMES = {
    "customer_id": ID_NAMES,
    "attribute_type": ["attributetype", "type", "kind", "attributekind", "identifiertype", "linktype"],
    "attribute_value": ["attributeid", "attributevalue", "value", "attribute", "identifier", "val", "identifiervalue"],
}
EVENT_FIELD_NAMES = {
    "customer_id": ID_NAMES,
    "event_date": [
        "eventdate",
        "date",
        "timestamp",
        "transactiondate",
        "txndate",
        "eventtime",
        "datetime",
        "time",
        "posteddate",
        "createdat",
        "activitydate",
    ],
    "event_type": ["eventtype", "type", "transactiontype", "txntype", "category", "event", "activitytype"],
    "utilization": [
        "utilizationpct",
        "utilization",
        "utilisation",
        "util",
        "utilizationrate",
        "creditutilization",
        "utilizationpercent",
    ],
    "credit_limit": ["creditlimitattime", "creditlimit", "limit", "cardlimit", "creditline"],
}

ATTRIBUTE_TYPE_SYNONYMS = {
    "phone": "phone",
    "phonenumber": "phone",
    "mobile": "phone",
    "cell": "phone",
    "telephone": "phone",
    "msisdn": "phone",
    "email": "email",
    "mail": "email",
    "emailaddress": "email",
    "address": "address",
    "addr": "address",
    "homeaddress": "address",
    "street": "address",
    "device": "device",
    "deviceid": "device",
    "fingerprint": "device",
    "devicefingerprint": "device",
    "ip": "ip",
    "ipaddress": "ip",
    "ssn": "national_id",
    "nationalid": "national_id",
    "taxid": "national_id",
    "passport": "national_id",
    "bank": "bank_account",
    "bankaccount": "bank_account",
    "iban": "bank_account",
    "card": "bank_account",
    "cardnumber": "bank_account",
}

EVENT_TYPE_SYNONYMS = {
    "purchase": "purchase",
    "purchases": "purchase",
    "spend": "purchase",
    "debit": "purchase",
    "transaction": "purchase",
    "txn": "purchase",
    "sale": "purchase",
    "payment": "payment",
    "repayment": "payment",
    "pay": "payment",
    "bill_payment": "payment",
    "credit_limit_increase": "credit_limit_increase",
    "limit_increase": "credit_limit_increase",
    "cli": "credit_limit_increase",
    "credit_line_increase": "credit_limit_increase",
}


@dataclass
class CanonicalData:
    customers: pd.DataFrame
    links: pd.DataFrame
    events: pd.DataFrame | None
    tabular_features: list[str]
    feature_labels: dict[str, str]
    event_columns: set[str] = field(default_factory=set)
    label_mode: str | None = None
    warnings: list[str] = field(default_factory=list)
    source: str = "upload"

    @property
    def has_labels(self) -> bool:
        return bool(self.customers["label"].notna().any())

    @property
    def attribute_types(self) -> list[str]:
        return sorted(self.links["attribute_type"].unique().tolist()) if len(self.links) else []


# --------------------------------------------------------------------------
# Reading files
# --------------------------------------------------------------------------


def _detect_encoding(path: Path) -> str:
    raw = path.read_bytes()[: 256 * 1024]
    try:
        raw.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "latin-1"


def _detect_delimiter(header_line: str) -> str:
    counts = {}
    for delimiter in [",", ";", "\t", "|"]:
        in_quotes = False
        count = 0
        for char in header_line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == delimiter and not in_quotes:
                count += 1
        counts[delimiter] = count
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def read_table(path: Path, nrows: int | None = None) -> pd.DataFrame:
    """Read a CSV/TSV file as strings, keeping empty cells as ``""``."""
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls", ".xlsm", ".parquet", ".json"}:
        raise IngestError(f"{path.name}: please export the file as CSV (comma, semicolon or tab separated).")
    if not path.is_file() or path.stat().st_size == 0:
        raise IngestError(f"{path.name}: the file is empty.")
    encoding = _detect_encoding(path)
    with open(path, encoding=encoding, newline="") as handle:
        header_line = handle.readline()
    delimiter = _detect_delimiter(header_line)
    try:
        frame = pd.read_csv(
            path,
            sep=delimiter,
            encoding=encoding,
            dtype=str,
            keep_default_na=False,
            nrows=nrows,
            skipinitialspace=True,
        )
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
        raise IngestError(f"{path.name}: could not be read as CSV ({error}).") from error
    frame.columns = [str(column).strip() for column in frame.columns]
    unnamed = [column for column in frame.columns if column.startswith("Unnamed:") and frame[column].eq("").all()]
    frame = frame.drop(columns=unnamed)
    if frame.columns.duplicated().any():
        raise IngestError(f"{path.name}: column names must be unique.")
    if frame.empty or len(frame.columns) == 0:
        raise IngestError(f"{path.name}: no rows found.")
    return frame.apply(lambda column: column.str.strip())


# --------------------------------------------------------------------------
# Column role suggestions
# --------------------------------------------------------------------------


def column_tokens(name: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))
    return [token for token in re.split(r"[^a-z0-9]+", spaced.lower()) if token]


def normalized_name(name: str) -> str:
    return "".join(column_tokens(name))


def _non_empty(values: pd.Series) -> pd.Series:
    return values[values != ""]


def numeric_share(values: pd.Series) -> float:
    values = _non_empty(values)
    if values.empty:
        return 0.0
    cleaned = values.str.replace(r"[,\s$€£₹%]", "", regex=True)
    return float(pd.to_numeric(cleaned, errors="coerce").notna().mean())


def date_share(values: pd.Series) -> float:
    values = _non_empty(values).head(500)
    if values.empty:
        return 0.0
    parsed = pd.to_datetime(values, errors="coerce", format="mixed")
    return float(parsed.notna().mean())


def parse_labels(values: pd.Series) -> pd.Series:
    lowered = values.astype(str).str.strip().str.lower()
    result = pd.Series(np.nan, index=values.index, dtype=float)
    result[lowered.isin(POSITIVE_LABELS)] = 1.0
    result[lowered.isin(NEGATIVE_LABELS)] = 0.0
    return result


def _label_like(values: pd.Series) -> bool:
    values = _non_empty(values)
    if values.empty:
        return False
    parsed = parse_labels(values)
    return parsed.notna().mean() >= 0.9 and parsed.dropna().nunique() <= 2


def _identity_role(tokens: list[str], norm: str) -> str | None:
    token_set = set(tokens)
    if "email" in norm or "mail" in token_set:
        return "email"
    if token_set & {"ip", "ipv4", "ipv6"} or norm in {"ipaddress", "ipaddr", "loginip", "signupip"}:
        return "ip"
    if (
        token_set & {"phone", "mobile", "cell", "cellphone", "msisdn", "telephone", "tel", "landline", "whatsapp"}
        or "phone" in norm
    ):
        return "phone"
    if token_set & {"device", "fingerprint", "imei", "udid"} or "device" in norm or "fingerprint" in norm:
        return "device"
    if (
        token_set & {"ssn", "sin", "nin", "tin", "pan", "aadhaar", "aadhar", "passport"}
        or "nationalid" in norm
        or "socialsecurity" in norm
        or "taxid" in norm
        or norm == "ssnlikeid"
    ):
        return "national_id"
    if (
        token_set & {"iban", "bic", "swift"}
        or "bankaccount" in norm
        or "accountnumber" in norm
        or "cardnumber" in norm
        or "routing" in norm
    ):
        return "bank_account"
    if token_set & {"address", "addr", "street", "addressline", "line1", "line2"} or "address" in norm:
        return "address"
    return None


def suggest_customer_roles(frame: pd.DataFrame) -> dict[str, str]:
    roles: dict[str, str] = {}
    id_candidates: list[tuple[int, str]] = []
    address_parts: list[str] = []

    for column in frame.columns:
        values = frame[column]
        tokens = column_tokens(column)
        norm = "".join(tokens)
        token_set = set(tokens)
        role = "ignore"
        if norm in ID_NAMES:
            id_candidates.append((ID_NAMES.index(norm), column))
            role = "ignore"  # resolved below
        elif norm in LABEL_NAMES and _label_like(values):
            role = "label"
        elif norm in RING_NAMES or "ring" in token_set:
            role = "ring"
        elif norm in DOB_NAMES:
            role = "ignore"
        elif norm in OPEN_DATE_NAMES or (
            token_set & {"open", "opened", "opening", "signup", "created", "registration", "registered"}
            and date_share(values) >= 0.8
        ):
            role = "open_date"
        elif norm in NAME_NAMES:
            role = "name"
        elif token_set & NUMERIC_HINTS and numeric_share(values) >= 0.95:
            role = "feature"
        else:
            identity = _identity_role(tokens, norm)
            if identity is not None:
                role = identity
            elif token_set & ADDRESS_PART_TOKENS:
                address_parts.append(column)
            elif numeric_share(values) >= 0.95:
                non_empty = _non_empty(values)
                unique = non_empty.nunique()
                id_like = token_set & ID_LIKE_TOKENS and unique == len(non_empty)
                role = "feature" if unique > 1 and not id_like else "ignore"
        roles[column] = role

    if id_candidates:
        id_candidates.sort()
        roles[id_candidates[0][1]] = "customer_id"
    else:
        for column in frame.columns:
            non_empty = _non_empty(frame[column])
            if (
                roles[column] in {"ignore", "feature"}
                and set(column_tokens(column)) & ID_LIKE_TOKENS
                and len(non_empty) == len(frame)
                and non_empty.is_unique
            ):
                roles[column] = "customer_id"
                break

    if any(role == "address" for role in roles.values()):
        for column in address_parts:
            roles[column] = "address"

    for single in ["label", "ring", "open_date"]:
        matches = [column for column, role in roles.items() if role == single]
        for extra in matches[1:]:
            roles[extra] = "ignore"
    return roles


def _suggest_fields(frame: pd.DataFrame, field_names: dict[str, list[str]]) -> dict[str, str | None]:
    normalized = {column: normalized_name(column) for column in frame.columns}
    used: set[str] = set()
    result: dict[str, str | None] = {}
    for field_name, names in field_names.items():
        choice = None
        for name in names:
            for column, norm in normalized.items():
                if norm == name and column not in used:
                    choice = column
                    break
            if choice:
                break
        if choice:
            used.add(choice)
        result[field_name] = choice
    return result


def suggest_link_fields(frame: pd.DataFrame) -> dict[str, str | None]:
    return _suggest_fields(frame, LINK_FIELD_NAMES)


def suggest_event_fields(frame: pd.DataFrame) -> dict[str, str | None]:
    return _suggest_fields(frame, EVENT_FIELD_NAMES)


def profile_columns(frame: pd.DataFrame) -> list[dict]:
    sample = frame.head(50_000)
    profiles = []
    for column in frame.columns:
        values = sample[column]
        non_empty = _non_empty(values)
        profiles.append(
            {
                "name": column,
                "n_unique": int(non_empty.nunique()),
                "n_empty": int((values == "").sum()),
                "examples": non_empty.drop_duplicates().head(3).tolist(),
                "numeric_share": round(numeric_share(values), 3),
            }
        )
    return profiles


def preview_file(path: Path, kind: str) -> dict:
    frame = read_table(path)
    preview = {
        "filename": path.name,
        "n_rows": int(len(frame)),
        "columns": profile_columns(frame),
        "sample_rows": frame.head(8).to_dict(orient="records"),
    }
    if kind == "customers":
        preview["suggested_roles"] = suggest_customer_roles(frame)
    elif kind == "links":
        preview["suggested_fields"] = suggest_link_fields(frame)
    elif kind == "events":
        preview["suggested_fields"] = suggest_event_fields(frame)
    return preview


# --------------------------------------------------------------------------
# Value normalisation
# --------------------------------------------------------------------------


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def normalize_identity(kind: str, raw: str) -> str | None:
    """Return the matching key for an identity value, or None if unusable."""
    text = str(raw).strip()
    if text.lower() in PLACEHOLDER_VALUES:
        return None
    if kind == "phone":
        digits = re.sub(r"\D", "", text)
        if len(digits) < 7:
            return None
        digits = digits[-10:]
        return None if len(set(digits)) == 1 else digits
    if kind == "email":
        lowered = text.lower()
        if "@" not in lowered or lowered.startswith("@") or lowered.endswith("@"):
            return None
        return lowered
    if kind == "address":
        cleaned = re.sub(r"[^a-z0-9 ]", " ", text.lower())
        tokens = [ADDRESS_ABBREVIATIONS.get(token, token) for token in cleaned.split()]
        return " ".join(tokens) or None
    if kind in SENSITIVE_TYPES:
        compact = re.sub(r"[^0-9a-z]", "", text.lower())
        if len(compact) < 4 or len(set(compact)) == 1:
            return None
        return compact
    if kind == "ip":
        lowered = text.lower()
        return None if lowered in {"0.0.0.0", "127.0.0.1", "::1", "255.255.255.255"} else lowered
    return re.sub(r"\s+", " ", text.lower())


def _display_value(kind: str, raw: str, key: str) -> str:
    if kind in SENSITIVE_TYPES:
        return f"•••• {key[-4:]}"
    return str(raw).strip()


def build_links(customer_ids: pd.Series, raw_values: pd.Series, kinds: pd.Series) -> pd.DataFrame:
    """Normalise raw identity values into link rows (one per usable value)."""
    frame = pd.DataFrame(
        {"customer_id": customer_ids.to_numpy(), "attribute_type": kinds.to_numpy(), "raw": raw_values.to_numpy()}
    )
    frame = frame[frame["raw"].astype(str).str.strip() != ""]
    rows = []
    for kind, group in frame.groupby("attribute_type", sort=True):
        uniques = group["raw"].astype(str).unique()
        keys = {raw: normalize_identity(kind, raw) for raw in uniques}
        mapped = group["raw"].astype(str).map(keys)
        usable = group[mapped.notna()].copy()
        usable_keys = mapped[mapped.notna()]
        if kind in SENSITIVE_TYPES:
            usable["attribute_id"] = [f"{kind}:{_hash(key)}" for key in usable_keys]
        else:
            usable["attribute_id"] = [f"{kind}:{key}" for key in usable_keys]
        usable["attribute_value"] = [
            _display_value(kind, raw, key) for raw, key in zip(usable["raw"].astype(str), usable_keys)
        ]
        rows.append(usable)
    if not rows:
        return pd.DataFrame(columns=["customer_id", "attribute_type", "attribute_id", "attribute_value"])
    links = pd.concat(rows, ignore_index=True)
    links = links.drop_duplicates(["customer_id", "attribute_type", "attribute_id"])
    return links[["customer_id", "attribute_type", "attribute_id", "attribute_value"]].reset_index(drop=True)


def canonical_attribute_type(raw: str) -> str:
    norm = normalized_name(raw)
    if norm in ATTRIBUTE_TYPE_SYNONYMS:
        return ATTRIBUTE_TYPE_SYNONYMS[norm]
    for prefix, kind in [("phone", "phone"), ("email", "email"), ("address", "address"), ("device", "device")]:
        if norm.startswith(prefix):
            return kind
    snake = "_".join(column_tokens(raw))[:32]
    return snake or "identifier"


def canonical_event_type(raw: str) -> str:
    snake = "_".join(column_tokens(raw))
    return EVENT_TYPE_SYNONYMS.get(snake, snake or "event")


def _feature_name(column: str, taken: set[str]) -> str:
    base = "_".join(column_tokens(column)) or "feature"
    if base[0].isdigit():
        base = f"col_{base}"
    if base in RESERVED_NAMES:
        base = f"col_{base}"
    name = base
    suffix = 2
    while name in taken:
        name = f"{base}_{suffix}"
        suffix += 1
    return name


def _to_number(values: pd.Series) -> pd.Series:
    cleaned = values.astype(str).str.replace(r"[,\s$€£₹%]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


# --------------------------------------------------------------------------
# Canonical dataset builders
# --------------------------------------------------------------------------


def validate_customer_roles(frame: pd.DataFrame, roles: dict[str, str]) -> None:
    unknown_columns = sorted(set(roles) - set(frame.columns))
    if unknown_columns:
        raise IngestError(f"Mapped columns not found in the customers file: {', '.join(unknown_columns)}")
    bad_roles = sorted({role for role in roles.values() if role not in CUSTOMER_ROLES})
    if bad_roles:
        raise IngestError(f"Unknown column roles: {', '.join(bad_roles)}")
    for role in SINGLE_ROLES:
        columns = [column for column, value in roles.items() if value == role]
        if len(columns) > 1:
            raise IngestError(f"Only one column can be the {CUSTOMER_ROLES[role]} (got {', '.join(columns)}).")


def build_from_upload(files: dict[str, Path], mapping: dict) -> CanonicalData:
    warnings: list[str] = []
    customer_mapping = mapping.get("customers") or {}
    roles: dict[str, str] = dict(customer_mapping.get("roles") or {})
    label_mode = customer_mapping.get("label_mode") or "train"
    if label_mode not in {"train", "evaluate"}:
        raise IngestError("label_mode must be 'train' or 'evaluate'.")

    frame = read_table(files["customers"])
    validate_customer_roles(frame, roles)
    frame = frame.copy()

    id_column = next((column for column, role in roles.items() if role == "customer_id"), None)
    if id_column:
        frame["__id"] = frame[id_column]
        missing = frame["__id"].eq("")
        if missing.any():
            warnings.append(f"{int(missing.sum())} customer rows had no customer ID and were skipped.")
            frame = frame[~missing]
    else:
        width = max(6, len(str(len(frame))))
        frame["__id"] = [f"C{index:0{width}d}" for index in range(1, len(frame) + 1)]
        warnings.append("No customer ID column was mapped, so row numbers were used as IDs.")
    if frame.empty:
        raise IngestError("The customers file has no usable rows.")

    duplicate_rows = int(frame["__id"].duplicated().sum())
    if duplicate_rows:
        warnings.append(
            f"{duplicate_rows} rows repeated an existing customer ID; their identity details were merged."
        )

    scalar = frame.replace("", np.nan).groupby("__id", sort=False).first()
    customers = pd.DataFrame({"customer_id": scalar.index.astype(str)})

    name_columns = [column for column, role in roles.items() if role == "name"]
    if name_columns:
        names = scalar[name_columns].fillna("").astype(str).agg(" ".join, axis=1).str.split().str.join(" ")
        customers["name"] = np.where(names.to_numpy() != "", names.to_numpy(), customers["customer_id"].to_numpy())
    else:
        customers["name"] = customers["customer_id"]

    label_column = next((column for column, role in roles.items() if role == "label"), None)
    if label_column:
        labels = parse_labels(scalar[label_column].fillna(""))
        customers["label"] = labels.to_numpy()
        unparsed = int(scalar[label_column].notna().sum() - labels.notna().sum())
        if unparsed:
            warnings.append(f"{unparsed} fraud label values were not recognised and treated as unlabeled.")
        if labels.notna().sum() == 0:
            warnings.append("The fraud label column had no recognisable values (expected 1/0, yes/no, fraud/legit).")
    else:
        customers["label"] = np.nan

    ring_column = next((column for column, role in roles.items() if role == "ring"), None)
    customers["truth_ring"] = scalar[ring_column].fillna("").astype(str).to_numpy() if ring_column else ""

    open_column = next((column for column, role in roles.items() if role == "open_date"), None)
    open_dates = pd.Series(pd.NaT, index=scalar.index)
    if open_column:
        open_dates = pd.to_datetime(scalar[open_column], errors="coerce", format="mixed")
        bad_dates = int(scalar[open_column].notna().sum() - open_dates.notna().sum())
        if bad_dates:
            warnings.append(f"{bad_dates} account open dates could not be parsed.")
    customers["open_date"] = [value.date().isoformat() if pd.notna(value) else "" for value in open_dates]

    feature_labels: dict[str, str] = {}
    tabular_features: list[str] = []
    taken: set[str] = set()
    for column in [column for column, role in roles.items() if role == "feature"]:
        values = _to_number(scalar[column].fillna(""))
        if values.notna().sum() == 0:
            warnings.append(f"Column '{column}' has no numeric values and was not used as a feature.")
            continue
        name = _feature_name(column, taken)
        taken.add(name)
        missing = int(values.isna().sum())
        if missing:
            warnings.append(f"{missing} missing values in '{column}' were filled with the median.")
        customers[name] = values.fillna(values.median()).to_numpy(dtype=float)
        tabular_features.append(name)
        feature_labels[name] = TABULAR_FEATURE_LABELS.get(name, column)

    # Identity links from customer columns.
    link_frames = []
    for kind in IDENTITY_ROLES:
        columns = [column for column, role in roles.items() if role == kind]
        if not columns:
            continue
        if kind == "address" and len(columns) > 1:
            parts = frame[columns].astype(str)
            combined = parts.agg(lambda row: ", ".join(part for part in row if part), axis=1)
            link_frames.append(build_links(frame["__id"], combined, pd.Series(kind, index=frame.index)))
        else:
            for column in columns:
                link_frames.append(build_links(frame["__id"], frame[column], pd.Series(kind, index=frame.index)))

    known_ids = set(customers["customer_id"])
    links_mapping = mapping.get("links")
    if files.get("links") is not None and links_mapping:
        link_frames.append(_links_from_file(files["links"], links_mapping, known_ids, warnings))

    links = (
        pd.concat(link_frames, ignore_index=True)
        if link_frames
        else pd.DataFrame(columns=["customer_id", "attribute_type", "attribute_id", "attribute_value"])
    )
    links = links.drop_duplicates(["customer_id", "attribute_type", "attribute_id"]).reset_index(drop=True)

    events = None
    event_columns: set[str] = set()
    events_mapping = mapping.get("events")
    if files.get("events") is not None and events_mapping:
        events, event_columns = _events_from_file(files["events"], events_mapping, known_ids, warnings)

    if open_column and "account_tenure_days" not in tabular_features and open_dates.notna().any():
        reference_date = open_dates.max()
        if events is not None and len(events):
            reference_date = max(reference_date, events["event_date"].max())
        tenure = (reference_date - open_dates).dt.days.astype(float)
        customers["account_tenure_days"] = tenure.fillna(tenure.median()).to_numpy()
        tabular_features.append("account_tenure_days")
        feature_labels["account_tenure_days"] = TABULAR_FEATURE_LABELS["account_tenure_days"]

    if len(customers) < 2:
        raise IngestError("At least two customers are needed.")

    return CanonicalData(
        customers=customers.reset_index(drop=True),
        links=links,
        events=events,
        tabular_features=tabular_features,
        feature_labels=feature_labels,
        event_columns=event_columns,
        label_mode=label_mode if label_column else None,
        warnings=warnings,
        source="upload",
    )


def _require_fields(mapping: dict, fields: list[str], frame: pd.DataFrame, filename: str) -> None:
    for field_name in fields:
        column = mapping.get(field_name)
        if not column:
            raise IngestError(f"{filename}: choose the column for '{field_name}'.")
    for field_name, column in mapping.items():
        if column and column not in frame.columns:
            raise IngestError(f"{filename}: column '{column}' not found.")


def _links_from_file(path: Path, mapping: dict, known_ids: set[str], warnings: list[str]) -> pd.DataFrame:
    frame = read_table(path)
    _require_fields(mapping, ["customer_id", "attribute_type", "attribute_value"], frame, path.name)
    customer_ids = frame[mapping["customer_id"]]
    unknown = ~customer_ids.isin(known_ids)
    if unknown.any():
        warnings.append(f"{int(unknown.sum())} identity links referenced unknown customers and were skipped.")
    frame = frame[~unknown]
    raw_types = frame[mapping["attribute_type"]]
    type_map = {raw: canonical_attribute_type(raw) for raw in raw_types.unique()}
    kinds = raw_types.map(type_map)
    return build_links(frame[mapping["customer_id"]], frame[mapping["attribute_value"]], kinds)


def _events_from_file(
    path: Path, mapping: dict, known_ids: set[str], warnings: list[str]
) -> tuple[pd.DataFrame | None, set[str]]:
    frame = read_table(path)
    _require_fields(mapping, ["customer_id", "event_date"], frame, path.name)
    dates = pd.to_datetime(frame[mapping["event_date"]].replace("", np.nan), errors="coerce", format="mixed")
    customer_ids = frame[mapping["customer_id"]]
    valid = dates.notna() & customer_ids.isin(known_ids)
    skipped = int((~valid).sum())
    if skipped:
        warnings.append(f"{skipped} events had an unknown customer or unreadable date and were skipped.")
    frame = frame[valid]
    dates = dates[valid]
    if frame.empty:
        warnings.append("No usable events were found, so temporal features were not computed.")
        return None, set()

    columns: set[str] = set()
    events = pd.DataFrame({"customer_id": frame[mapping["customer_id"]].to_numpy(), "event_date": dates.to_numpy()})
    if mapping.get("event_type"):
        raw_types = frame[mapping["event_type"]]
        type_map = {raw: canonical_event_type(raw) for raw in raw_types.unique()}
        events["event_type"] = raw_types.map(type_map).to_numpy()
        columns.add("event_type")
    else:
        events["event_type"] = "event"
    if mapping.get("utilization"):
        utilization = _to_number(frame[mapping["utilization"]])
        if utilization.notna().any():
            if utilization.max() > 1.5:
                utilization = utilization / 100.0
                warnings.append("Utilization values looked like percentages and were divided by 100.")
            events["utilization_pct"] = utilization.fillna(utilization.median()).clip(lower=0).to_numpy()
            columns.add("utilization_pct")
    if "utilization_pct" not in events:
        events["utilization_pct"] = 0.0
    if mapping.get("credit_limit"):
        limit = _to_number(frame[mapping["credit_limit"]])
        if limit.notna().any():
            events["credit_limit_at_time"] = limit.fillna(limit.median()).to_numpy()
            columns.add("credit_limit_at_time")
    if "credit_limit_at_time" not in events:
        events["credit_limit_at_time"] = 0.0
    return events.reset_index(drop=True), columns


def canonical_from_generated(generated: dict[str, pd.DataFrame]) -> CanonicalData:
    """Canonical form of a dataset produced by ``data_generation.generate_all``.

    Customer order and feature names match the research pipeline so the
    experiment table reproduces the numbers in PROJECT_STATUS.md exactly.
    """
    raw = generated["customers"]
    customers = pd.DataFrame(
        {
            "customer_id": raw["customer_id"].astype(str),
            "name": raw["full_name"].astype(str),
            "label": raw["is_synthetic_fraud"].astype(float),
            "truth_ring": raw["ring_id"].fillna("").astype(str),
            "open_date": raw["account_open_date"].astype(str),
        }
    )
    for feature in TABULAR_FEATURES:
        customers[feature] = raw[feature]

    display = {}
    for frame, id_column, builder in [
        (generated["phones"], "phone_id", lambda row: row["phone_number"]),
        (generated["emails"], "email_id", lambda row: row["email_address"]),
        (
            generated["addresses"],
            "address_id",
            lambda row: f"{row['street']}, {row['city']}, {row['state']} {row['zip']}",
        ),
        (generated["devices"], "device_id", lambda row: f"device {row['device_fingerprint'][:12]}"),
    ]:
        for row in frame.to_dict(orient="records"):
            display[row[id_column]] = str(builder(row))
    links = generated["links"][["customer_id", "attribute_type", "attribute_id"]].copy()
    links["attribute_value"] = links["attribute_id"].map(display).fillna(links["attribute_id"])

    events = generated["events"][
        ["customer_id", "event_date", "event_type", "utilization_pct", "credit_limit_at_time"]
    ].copy()
    events["event_date"] = pd.to_datetime(events["event_date"])
    return CanonicalData(
        customers=customers,
        links=links.reset_index(drop=True),
        events=events,
        tabular_features=list(TABULAR_FEATURES),
        feature_labels={feature: TABULAR_FEATURE_LABELS[feature] for feature in TABULAR_FEATURES},
        event_columns={"event_type", "utilization_pct", "credit_limit_at_time"},
        label_mode="train",
        warnings=[],
        source="synthetic",
    )
