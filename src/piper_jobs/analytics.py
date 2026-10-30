"""Analytics aggregations over filtered application rows: pace, mix and conversion."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import date, datetime, timedelta
from statistics import median

from .categories import CATEGORIES, SENIORITY_LEVELS, normalize_title, seniority
from .filters import AppRow, Filters
from .schema import SOURCES
from .stats import INTERVIEW_STAGES, OFFER_STAGES, RESPONSE_STAGES, _rate, first_response_days

HEATMAP_DAYS = 364  # 52 weeks
TOP_N = 8
OPEN_STAGES = {"applied", "viewed", "assessment", "interview", "offer"}
OUTCOME_KEYS = ["active", "rejected", "ghosted", "withdrawn", "accepted"]
RESPONSE_BUCKETS = [("<=2d", 2), ("3-7d", 7), ("8-14d", 14), ("15-30d", 30), (">30d", None)]
AGE_BUCKETS = [("0-7d", 7), ("8-14d", 14), ("15-21d", 21), ("22d+", None)]


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


def _ids(rows: list[AppRow]) -> list[int]:
    return [r.app.id for r in rows]


def _mix(rows: list[AppRow], key: Callable[[AppRow], str], order) -> list[dict]:
    groups: dict[str, list[AppRow]] = {k: [] for k in order}
    for r in rows:
        groups.setdefault(key(r), []).append(r)  # an unexpected value still counts, after the known ones
    return [{"key": k, "count": len(rs), "ids": _ids(rs)} for k, rs in groups.items()]


def _category_by_week(dated: list[tuple[date, AppRow]], start: date, end: date) -> list[dict]:
    if not dated:
        return []
    weeks = {w: Counter() for w in _bucket_starts(start, end, "week")}
    for day, r in dated:
        weeks[_bucket(day, "week")][r.app.category] += 1
    return [{"week": w.isoformat(), **{c: counts[c] for c in CATEGORIES}} for w, counts in weeks.items()]


def _top_titles(rows: list[AppRow]) -> list[dict]:
    groups: dict[str, list[AppRow]] = defaultdict(list)
    for r in rows:
        if title := normalize_title(r.app.role_display):
            groups[title].append(r)
    ranked = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:TOP_N]
    return [{"title": t, "count": len(rs), "ids": _ids(rs)} for t, rs in ranked]


def _top_companies(rows: list[AppRow]) -> list[dict]:
    groups: dict[str, list[AppRow]] = defaultdict(list)
    for r in rows:
        groups[r.app.company_norm].append(r)
    repeated = [rs for rs in groups.values() if len(rs) > 1]
    repeated.sort(key=lambda rs: (-len(rs), rs[0].app.company_display))
    out = []
    for rs in repeated[:TOP_N]:
        latest = max(rs, key=lambda r: r.app.last_event_at)
        out.append({"company": latest.app.company_display, "count": len(rs), "stage": latest.stage, "ids": _ids(rs)})
    return out


def _weekday(dated: list[tuple[date, AppRow]]) -> list[dict]:
    groups: dict[int, list[AppRow]] = {i: [] for i in range(7)}
    for day, r in dated:
        groups[day.weekday()].append(r)
    return [{"day": i, "count": len(rs), "ids": _ids(rs)} for i, rs in groups.items()]


def _conversion(rows: list[AppRow], key: Callable[[AppRow], str]) -> list[dict]:
    groups: dict[str, list[AppRow]] = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    out = []
    for k, rs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        days = [x for r in rs if (x := first_response_days(r)) is not None]
        out.append({
            "key": k,
            "total": len(rs),
            "responded": _rate(sum(1 for r in rs if r.reached & RESPONSE_STAGES), len(rs)),
            "interviewed": _rate(sum(1 for r in rs if r.reached & INTERVIEW_STAGES), len(rs)),
            "offers": sum(1 for r in rs if r.reached & OFFER_STAGES),
            "median_days": round(median(days), 1) if days else None,
        })
    return out


def _cohorts(dated: list[tuple[date, AppRow]], today: date) -> list[dict]:
    weeks: dict[date, list[AppRow]] = defaultdict(list)
    for day, r in dated:
        weeks[_bucket(day, "week")].append(r)
    return [
        {
            "week": w.isoformat(),
            "total": len(rs),
            "responded": _rate(sum(1 for r in rs if r.reached & RESPONSE_STAGES), len(rs)),
            "maturing": (today - w).days < 14,  # replies to these may simply not have arrived yet
        }
        for w, rs in sorted(weeks.items())
    ]


def _first_bucket(value: float, buckets: list[tuple[str, int | None]]) -> str:
    return next(label for label, limit in buckets if limit is None or value <= limit)


def _response_time(rows: list[AppRow]) -> dict:
    days = [x for r in rows if (x := first_response_days(r)) is not None]
    counts = Counter(_first_bucket(x, RESPONSE_BUCKETS) for x in days)
    return {
        "buckets": [{"key": label, "count": counts[label]} for label, _ in RESPONSE_BUCKETS],
        "median": round(median(days), 1) if days else None,
    }


def _open_by_age(rows: list[AppRow], now: datetime) -> list[dict]:
    groups: dict[str, list[AppRow]] = {label: [] for label, _ in AGE_BUCKETS}
    for r in rows:
        if r.stage in OPEN_STAGES:
            groups[_first_bucket((now - r.app.last_event_at).days, AGE_BUCKETS)].append(r)
    return [{"key": k, "count": len(rs), "ids": _ids(rs)} for k, rs in groups.items()]


def _outcomes(rows: list[AppRow]) -> list[dict]:
    groups: dict[str, list[AppRow]] = {k: [] for k in OUTCOME_KEYS}
    for r in rows:
        groups["active" if r.stage in OPEN_STAGES else r.stage].append(r)
    return [{"key": k, "count": len(rs), "ids": _ids(rs)} for k, rs in groups.items()]


def _breakdown(rows, dated, start: date, end: date, today: date, now: datetime) -> dict:
    return {
        "mix": {
            "category": _mix(rows, lambda r: r.app.category, CATEGORIES),
            "source": _mix(rows, lambda r: r.app.source, SOURCES),
            "seniority": _mix(rows, lambda r: seniority(r.app.role_display), SENIORITY_LEVELS),
        },
        "category_by_week": _category_by_week(dated, start, end),
        "top_titles": _top_titles(rows),
        "top_companies": _top_companies(rows),
        "weekday": _weekday(dated),
        "conversion": {
            "source": _conversion(rows, lambda r: r.app.source),
            "category": _conversion(rows, lambda r: r.app.category),
            "seniority": _conversion(rows, lambda r: seniority(r.app.role_display)),
        },
        "cohorts": _cohorts(dated, today),
        "response_time": _response_time(rows),
        "open_by_age": _open_by_age(rows, now),
        "outcomes": _outcomes(rows),
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
        return {
            "range": {"from": None, "to": end.isoformat()},
            "summary": _summary(per_day, end, end, today, previous_total),
            "series": [],
            "daily": [],
            **_breakdown([], [], end, end, today, now),
        }
    start = min(known)
    daily_start = max(start, end - timedelta(days=HEATMAP_DAYS - 1))
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "summary": _summary(per_day, start, end, today, previous_total),
        "series": _series(dated, granularity, start, end, with_apps=True),
        "daily": _series([(day, r) for day, r in dated if day >= daily_start], "day", daily_start, end, with_apps=False),
        **_breakdown(rows, dated, start, end, today, now),
    }
