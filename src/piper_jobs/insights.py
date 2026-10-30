"""Facts behind the written summary, and the checks around the model's reply. Pure: no I/O."""

from __future__ import annotations

import hashlib
import re

PROMPT_VERSION = 1  # bump when the prompt changes: older cached summaries are then discarded
MIN_APPLICATIONS = 10  # below this there is nothing worth summarising
MIN_GROUP = 5  # smaller groups are too small to compare

CATEGORY_LABEL = {"design": "Design", "product": "Product", "vc": "VC", "other": "Other"}
SOURCE_LABEL = {
    "linkedin": "LinkedIn", "ats": "Company site / ATS", "recruiter": "Recruiter",
    "direct": "Direct", "referral": "Referral", "other": "Other",
}
SENIORITY_LABEL = {
    "intern": "Intern", "junior": "Junior", "mid": "Mid", "senior": "Senior", "staff": "Staff / Principal",
    "lead": "Lead", "head": "Head / Director+", "unspecified": "Unspecified",
}

SYSTEM_PROMPT = (
    "You write a short summary of a person's job search for them. You are given facts, one per line. "
    "Write two to four plain sentences. Use only numbers that appear in the facts, copied exactly. "
    "Do not give advice or make predictions. If the most recent weeks may still be waiting for replies, "
    "say that recent reply rates may not be final. No bullet points, no headings."
)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _pct(rate: float) -> str:
    return f"{round(rate * 100)}%"


def _shares(groups: list[dict], labels: dict[str, str], top: int = 3) -> str | None:
    total = sum(g["count"] for g in groups)
    ranked = sorted((g for g in groups if g["count"]), key=lambda g: (-g["count"], g["key"]))[:top]
    if not total:
        return None
    return ", ".join(f"{labels.get(g['key'], g['key'])} {_pct(g['count'] / total)} ({g['count']})" for g in ranked)


def build_facts(a: dict) -> list[str]:
    s = a["summary"]
    first = f"Applications from {a['range']['from'] or 'the start'} to {a['range']['to']}: {s['total']}"
    if s["previous_total"] is not None:
        first += f" (previous period of the same length: {s['previous_total']})"
    facts = [
        first,
        f"Pace: {s['daily_average']} a day on average, {s['per_active_day']} on the {s['active_days']} days "
        f"with an application; current streak {s['streak']} days, longest {s['longest_streak']}",
        f"This week: {s['this_week']}, last week: {s['last_week']}",
    ]
    for title, key, labels in (("Role types", "category", CATEGORY_LABEL), ("Sources", "source", SOURCE_LABEL),
                               ("Seniority", "seniority", SENIORITY_LABEL)):
        if text := _shares(a["mix"][key], labels):
            facts.append(f"{title}: {text}")
    for title, key, labels in (("Source", "source", SOURCE_LABEL), ("Role type", "category", CATEGORY_LABEL)):
        groups = [g for g in a["conversion"][key] if g["total"] >= MIN_GROUP]
        for g in groups:
            facts.append(f"{title} {labels.get(g['key'], g['key'])}: {g['total']} applied, "
                         f"{_pct(g['responded'])} replied, {_pct(g['interviewed'])} interviewed")
        if len(groups) >= 2:
            best = max(groups, key=lambda g: g["responded"])
            worst = min(groups, key=lambda g: g["responded"])
            if best["responded"] != worst["responded"]:
                facts.append(f"Highest reply rate by {title.lower()}: {labels.get(best['key'], best['key'])}; "
                             f"lowest: {labels.get(worst['key'], worst['key'])}")
    if (median := a["response_time"]["median"]) is not None:
        facts.append(f"Median time to a first reply: {median} days")
    if maturing := sum(1 for c in a["cohorts"] if c["maturing"]):
        facts.append(f"The most recent {maturing} week{'s' if maturing != 1 else ''} of applications "
                     "may still be waiting for replies")
    if quiet := sum(b["count"] for b in a["open_by_age"] if b["key"] in ("15-21d", "22d+")):
        facts.append(f"Open applications quiet for over two weeks: {quiet}")
    return facts


def facts_hash(facts: list[str], model: str, prompt_version: int = PROMPT_VERSION) -> str:
    raw = "\n".join([model, str(prompt_version), *facts])
    return hashlib.sha256(raw.encode()).hexdigest()


def build_messages(facts: list[str]) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Facts:\n" + "\n".join(f"- {f}" for f in facts)},
    ]


def numbers_in(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def is_grounded(summary: str, facts: list[str]) -> bool:
    """The reply is non-empty and uses no number that is not in the facts."""
    return bool(summary.strip()) and numbers_in(summary) <= numbers_in("\n".join(facts))
