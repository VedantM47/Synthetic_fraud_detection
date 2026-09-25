"""Plain-English explanations for customer risk scores and fraud rings.

Customer explanations are built from two sources:

* the model's own attributions (baseline Shapley values: how much each
  feature moved the score away from a typical legitimate customer's),
  turned into sentences with the customer's actual values, e.g. "shares a
  phone number with 4 other accounts"; and
* graph context that the analyst needs regardless of the model: ring
  membership, how many linked accounts are high risk, analyst decisions.
"""

from __future__ import annotations

from backend import settings
from backend.pipeline.ingest import ATTRIBUTE_TYPE_LABELS

ARTICLES = {
    "phone": "a phone number",
    "email": "an email address",
    "address": "an address",
    "device": "a device",
    "ip": "an IP address",
    "national_id": "a national ID",
    "bank_account": "a bank account or card",
}
LEVEL_WORDS = {"high": "High", "medium": "Medium", "low": "Low"}


def plural(count: float, word: str, plural_word: str | None = None) -> str:
    return word if round(count) == 1 else (plural_word or f"{word}s")


def attribute_phrase(kind: str) -> str:
    if kind in ARTICLES:
        return ARTICLES[kind]
    return f"an identifier ({kind.replace('_', ' ')})"


def attribute_noun(kind: str) -> str:
    return ATTRIBUTE_TYPE_LABELS.get(kind, kind.replace("_", " "))


ATTRIBUTE_PLURALS = {
    "phone": "phone numbers",
    "email": "email addresses",
    "address": "addresses",
    "device": "devices",
    "ip": "IP addresses",
    "national_id": "national IDs",
    "bank_account": "bank accounts or cards",
    "identifier": "identifiers",
}


def attribute_plural(kind: str) -> str:
    return ATTRIBUTE_PLURALS.get(kind, f"{kind.replace('_', ' ')} values")


def join_clauses(clauses: list[str]) -> str:
    if len(clauses) <= 1:
        return "".join(clauses)
    return ", ".join(clauses[:-1]) + " and " + clauses[-1]


def fmt_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def clause(feature: str, value: float, direction: str, labels: dict[str, str]) -> str | None:
    """Sentence fragment (following "it") stating one feature value.

    Clauses state facts only; whether the fact raised or lowered the score
    comes from the model attribution and is shown separately. Returns None
    for facts that would read as nonsense in the given direction (an absent
    shared attribute cannot be the reason a score went up).
    """
    v = float(value)
    n = int(round(v))
    up = direction == "up"
    if feature.endswith("_shared_count"):
        kind = feature.removesuffix("_shared_count")
        if n > 0:
            return f"shares {attribute_phrase(kind)} with {n} other {plural(n, 'account')}"
        return None if up else f"doesn't share its {attribute_noun(kind)} with any other account"
    if feature == "network_degree":
        if n > 0:
            return f"is linked to {n} other {plural(n, 'account')} through shared identity details"
        return None if up else "isn't linked to any other account"
    if feature == "shared_attribute_count":
        if n > 0:
            return f"has {n} overlapping identity {plural(n, 'link')} with other accounts"
        return None if up else "has no identity details in common with other accounts"
    if feature == "max_utilization_pct":
        return f"reached a peak credit utilization of {pct(v)}"
    if feature == "mean_utilization_pct":
        return f"ran an average credit utilization of {pct(v)}"
    if feature == "utilization_range":
        if round(v * 100) == 0:
            return "kept the same credit utilization throughout"
        return f"had its credit utilization swing by {v * 100:.0f} percentage points"
    if feature == "max_events_7d":
        return f"had at most {n} account {plural(n, 'event')} in any 7-day window"
    if feature == "max_events_single_day":
        return f"had at most {n} account {plural(n, 'event')} on a single day"
    if feature == "events_per_30_days":
        return f"averages {v:.1f} account events per 30 days"
    if feature == "total_event_count":
        return f"has {n} account {plural(n, 'event')} on record"
    if feature == "purchase_count":
        return "hasn't made any purchases" if n == 0 else f"made {n} {plural(n, 'purchase')}"
    if feature == "payment_count":
        return "hasn't made any payments" if n == 0 else f"made {n} {plural(n, 'payment')}"
    if feature == "limit_increase_count":
        if n == 0:
            return "hasn't received any credit-limit increases"
        return f"received {n} credit-limit {plural(n, 'increase')}"
    if feature == "distinct_event_dates":
        return f"was active on {n} different {plural(n, 'day')}"
    if feature == "event_span_days":
        return f"has account activity spanning {n} {plural(n, 'day')}"
    if feature == "min_days_between_events":
        return f"had account events as little as {n} {plural(n, 'day')} apart"
    if feature == "mean_days_between_events":
        return f"averages {v:.1f} days between account events"
    if feature == "max_credit_limit":
        return f"reached a credit limit of {fmt_number(v)}"
    if feature == "annual_income":
        return f"reports an annual income of {fmt_number(v)}"
    if feature == "credit_score":
        return f"has a credit score of {fmt_number(v)}"
    if feature == "account_tenure_days":
        return f"has an account that is {n} {plural(n, 'day')} old"
    return f"has {labels.get(feature, feature.replace('_', ' '))} of {fmt_number(v)}"


def capitalize(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _select(candidates: list[dict], limit: int) -> list[dict]:
    """The largest contributions, in order.

    Nothing is skipped for being "redundant": the written reasons must match
    the contribution chart, so the biggest factor is always named.
    """
    return candidates[:limit]


def explain_customer(
    *,
    risk: float,
    level: str,
    features: list[str],
    values: dict[str, float],
    contributions: list[float],
    labels: dict[str, str],
    shared_counts: dict[str, int],
    degree: int,
    high_neighbors: int,
    ring: dict | None,
    analyst_label: int | None,
    baseline_score: float,
) -> dict:
    items = []
    for feature, delta in zip(features, contributions):
        if abs(delta) < settings.MIN_REASON_CONTRIBUTION:
            continue
        direction = "up" if delta > 0 else "down"
        text = clause(feature, values.get(feature, 0.0), direction, labels)
        if text is None:
            continue
        items.append(
            {
                "feature": feature,
                "label": labels.get(feature, feature),
                "value": float(values.get(feature, 0.0)),
                "direction": direction,
                # Same precision as the stored contributions so the reason list
                # and the factor chart always display identical numbers.
                "impact": round(float(delta) * 100, 2),
                "text": capitalize(text),
                "clause": text,
            }
        )
    ups = _select(sorted([i for i in items if i["direction"] == "up"], key=lambda i: -i["impact"]), 4)
    downs = _select(sorted([i for i in items if i["direction"] == "down"], key=lambda i: i["impact"]), 3)

    score = int(round(risk * 100))
    word = LEVEL_WORDS[level]
    if level == "high":
        if ups:
            summary = f"{word} risk ({score}/100): flagged because it {join_clauses([i['clause'] for i in ups[:3]])}."
        else:
            summary = f"{word} risk ({score}/100): flagged by a combination of weaker signals rather than one clear reason."
    elif level == "medium":
        if ups:
            summary = f"{word} risk ({score}/100): worth a look because it {join_clauses([i['clause'] for i in ups[:2]])}."
        else:
            summary = f"{word} risk ({score}/100): no single strong signal, but several small ones add up."
        if downs:
            summary += f" In its favour: it {downs[0]['clause']}."
    else:
        if downs or ups:
            summary = f"{word} risk ({score}/100): below the alert threshold."
            if downs:
                summary += f" In its favour: it {join_clauses([i['clause'] for i in downs[:2]])}."
            if ups and ups[0]["impact"] >= 5:
                summary += f" Still worth noting: it {ups[0]['clause']}."
        elif degree == 0:
            summary = (
                f"{word} risk ({score}/100): it isn't linked to any other account and its score is close "
                "to that of a typical legitimate customer."
            )
        else:
            summary = (
                f"{word} risk ({score}/100): no strong fraud signals; its score is close to that of a "
                "typical legitimate customer."
            )

    context = []
    if ring is not None:
        kinds = [attribute_noun(kind) for kind in ring["shared_types"]][:3]
        linked_by = f" linked by shared {join_clauses(kinds)}" if kinds else ""
        if ring["suspected"]:
            context.append(
                f"Part of suspected fraud ring {ring['ring_id']}: {ring['size']} accounts{linked_by}, "
                f"{ring['n_high']} of them high risk."
            )
            if level != "low":
                summary += f" It belongs to suspected ring {ring['ring_id']} ({ring['size']} linked accounts)."
        else:
            context.append(
                f"In connected group {ring['ring_id']} ({ring['size']} accounts{linked_by}), which is not currently suspected."
            )
    if degree == 1:
        context.append(
            "Its one linked account is rated high risk."
            if high_neighbors
            else "Its one linked account is not rated high risk."
        )
    elif degree > 1:
        if high_neighbors == 0:
            context.append(f"None of its {degree} linked accounts are rated high risk.")
        else:
            verb = "is" if high_neighbors == 1 else "are"
            context.append(f"{high_neighbors} of its {degree} linked accounts {verb} rated high risk.")
    mentioned = {item["feature"] for item in ups + downs}
    for kind, count in shared_counts.items():
        feature = f"{kind}_shared_count"
        if count > 0 and feature not in mentioned:
            context.append(f"Shares {attribute_phrase(kind)} with {count} other {plural(count, 'account')}.")
    if analyst_label == 1:
        context.append("An analyst confirmed this account as fraud.")
    elif analyst_label == 0:
        context.append("An analyst marked this account as legitimate.")

    if ups and level != "low":
        top_reason = ups[0]["text"]
    elif downs and level == "low":
        top_reason = downs[0]["text"]
    elif ups:
        top_reason = ups[0]["text"]
    else:
        top_reason = context[0] if context else "No strong signals"
    return {
        "summary": summary,
        "score": score,
        "baseline_score": round(baseline_score * 100, 1),
        "reasons": ups,
        "mitigating": downs,
        "context": context,
        "top_reason": top_reason,
    }


def explain_ring(ring: dict) -> str:
    size = ring["size"]
    evidence = ring["evidence"]
    by_type: dict[str, int] = {}
    for item in evidence:
        by_type[item["attribute_type"]] = by_type.get(item["attribute_type"], 0) + 1
    parts = []
    for kind, count in sorted(by_type.items(), key=lambda entry: -entry[1]):
        noun = attribute_noun(kind) if count == 1 else attribute_plural(kind)
        parts.append(f"{count} shared {noun}")
    linked = f" linked by {join_clauses(parts)}" if parts else ""
    top = evidence[0] if evidence else None
    text = f"{size} accounts{linked}."
    if top and top["members"] >= 3:
        text += f" One {attribute_noun(top['attribute_type'])} is used by {top['members']} of them."
    text += (
        f" {ring['n_high']} of {size} members are rated high risk (average score {round(ring['score'] * 100)}/100)."
    )
    if ring.get("open_span_days") is not None and ring["open_span_days"] <= 60 and size >= 3:
        text += f" All accounts were opened within {ring['open_span_days']} days of each other."
    return text
