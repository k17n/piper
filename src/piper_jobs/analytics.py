"""Analytics aggregations over filtered application rows: pace, mix and conversion."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from .filters import AppRow, Filters

HEATMAP_DAYS = 364  # 52 weeks


def previous_filters(filters: Filters, today: date) -> Filters | None:
    """The same filters shifted back by their own length; None when the range has no start (All)."""
    start, end = filters.date_bounds(today)
    if start is None:
        return None
    end = end or today
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    return filters.model_copy(
        update={"range": "custom", "from_": prev_end - timedelta(days=length - 1), "to": prev_end}
    )


def _bucket(day: date, granularity: str) -> date:
    if granularity == "week":
        return day - timedelta(days=day.weekday())
    if granularity == "month":
        return day.replace(day=1)
    return day


def _next_bucket(bucket: date, granularity: str) -> date:
    if granularity == "week":
        return bucket + timedelta(days=7)
    if granularity == "month":
        return bucket.replace(year=bucket.year + 1, month=1) if bucket.month == 12 else bucket.replace(month=bucket.month + 1)
    return bucket + timedelta(days=1)


def _bucket_starts(start: date, end: date, granularity: str) -> list[date]:
    out, cur = [], _bucket(start, granularity)
    while cur <= end:
        out.append(cur)
        cur = _next_bucket(cur, granularity)
    return out


def _series(dated: list[tuple[date, AppRow]], granularity: str, start: date, end: date, with_apps: bool) -> list[dict]:
    buckets: dict[date, list[AppRow]] = {b: [] for b in _bucket_starts(start, end, granularity)}
    for day, row in dated:
        buckets[_bucket(day, granularity)].append(row)
    out = []
    for bucket, rows in buckets.items():
        rows = sorted(rows, key=lambda r: r.app.first_seen)
        point = {"date": bucket.isoformat(), "count": len(rows), "ids": [r.app.id for r in rows]}
        if with_apps:
            point["apps"] = [
                {"id": r.app.id, "company": r.app.company_display, "role": r.app.role_display} for r in rows[:5]
            ]
        out.append(point)
    return out


def _streaks(active: set[date], today: date) -> tuple[int, int]:
    """(current, longest). Current ends today, or yesterday so an unfinished day does not break it."""
    current, day = 0, today if today in active else today - timedelta(days=1)
    while day in active:
        current += 1
        day -= timedelta(days=1)
    longest = run = 0
    previous: date | None = None
    for day in sorted(active):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    return current, longest


def _summary(per_day: Counter, start: date, end: date, today: date, previous_total: int | None) -> dict:
    total = sum(per_day.values())
    span = (end - start).days + 1
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)
    streak, longest = _streaks(set(per_day), today)
    best = max(per_day.items(), key=lambda kv: (kv[1], kv[0]), default=None)
    return {
        "total": total,
        "previous_total": previous_total,
        "active_days": len(per_day),
        "per_active_day": round(total / len(per_day), 2) if per_day else 0,
        "daily_average": round(total / span, 2) if span > 0 else 0,
        "last_7d_average": round(sum(per_day[today - timedelta(days=i)] for i in range(7)) / 7, 2),
        "streak": streak,
        "longest_streak": longest,
        "best_day": {"date": best[0].isoformat(), "count": best[1]} if best else None,
        "this_week": sum(c for day, c in per_day.items() if week_start <= day <= today),
        "last_week": sum(c for day, c in per_day.items() if last_week_start <= day < week_start),
    }


def compute_analytics(
    rows: list[AppRow],
    now: datetime,
    tz_offset: int = 0,
    granularity: str = "day",
    start: date | None = None,
    end: date | None = None,
    previous_total: int | None = None,
) -> dict:
    """`tz_offset` is minutes ahead of UTC. `start`/`end` are the filter's bounds (local days); the range
    widens to include any row that falls outside them after the time-zone shift."""
    offset = timedelta(minutes=tz_offset)
    today = (now + offset).date()
    dated = [((r.app.first_seen + offset).date(), r) for r in rows]
    days = [day for day, _ in dated]
    end = max([end or today, *days])
    known = [x for x in (start, *days) if x is not None]
    per_day = Counter(days)
    if not known:  # no rows and an open-ended range (All): nothing to draw
        return {"range": {"from": None, "to": end.isoformat()},
                "summary": _summary(per_day, end, end, today, previous_total), "series": [], "daily": []}
    start = min(known)
    daily_start = max(start, end - timedelta(days=HEATMAP_DAYS - 1))
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "summary": _summary(per_day, start, end, today, previous_total),
        "series": _series(dated, granularity, start, end, with_apps=True),
        "daily": _series([(day, r) for day, r in dated if day >= daily_start], "day", daily_start, end, with_apps=False),
    }
