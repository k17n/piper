"""KPI and insight aggregations over filtered application rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median

from .filters import AppRow

RESPONSE_STAGES = {"assessment", "interview", "offer", "accepted", "rejected"}
INTERVIEW_STAGES = {"interview", "offer", "accepted"}
OFFER_STAGES = {"offer", "accepted"}


def _rate(n: int, total: int) -> float:
    return round(n / total, 4) if total else 0.0


def first_response_days(row: AppRow) -> float | None:
    times = [e.occurred_at for e in row.events if e.stage in RESPONSE_STAGES]
    if not times:
        return None
    return (min(times) - row.app.first_seen).total_seconds() / 86400


def compute_stats(rows: list[AppRow]) -> dict:
    total = len(rows)
    responded = sum(1 for r in rows if r.reached & RESPONSE_STAGES)
    interviews = sum(1 for r in rows if r.reached & INTERVIEW_STAGES)
    offers = sum(1 for r in rows if r.reached & OFFER_STAGES)
    days = [d for r in rows if (d := first_response_days(r)) is not None]
    by_stage = Counter(r.stage for r in rows)
    return {
        "total": total,
        "active": sum(by_stage[s] for s in ("applied", "viewed", "assessment", "interview", "offer")),
        "response_rate": _rate(responded, total),
        "interview_rate": _rate(interviews, total),
        "offer_rate": _rate(offers, total),
        "median_days_to_first_response": round(median(days), 1) if days else None,
        "by_stage": dict(by_stage),
    }


def compute_insights(rows: list[AppRow]) -> dict:
    per_day = Counter(r.app.first_seen.date().isoformat() for r in rows)
    groups: dict[str, list[AppRow]] = defaultdict(list)
    for r in rows:
        groups[r.app.source].append(r)
    by_source = [
        {
            "source": source,
            "total": len(rs),
            "response_rate": _rate(sum(1 for r in rs if r.reached & RESPONSE_STAGES), len(rs)),
            "interview_rate": _rate(sum(1 for r in rs if r.reached & INTERVIEW_STAGES), len(rs)),
        }
        for source, rs in sorted(groups.items())
    ]
    return {"per_day": [{"date": d, "count": c} for d, c in sorted(per_day.items())], "by_source": by_source}
