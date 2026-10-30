# Analytics Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Analytics tab showing applications per day, what kinds of roles are applied to, and what converts, as specified in [docs/PRD-analytics.md](../../PRD-analytics.md).

**Architecture:** A pure function `compute_analytics(rows, ...)` in a new `analytics.py` aggregates the rows `load_rows` already returns; a new `GET /api/analytics` endpoint exposes it with the shared filters. The frontend adds an `analytics` tab whose `AnalyticsTab` component owns one query and lays out small single-purpose widget components (ECharts for time series, plain CSS for bars and the heatmap).

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pytest; React 19 + TypeScript, Vite, Tailwind 4, ECharts via `echarts-for-react`, TanStack Query.

## Global Constraints

- No schema change, no new network calls, no new dependencies (spec §7).
- "Applied date" is `applications.first_seen`, bucketed in the user's local time zone via `tz_offset` (spec §4).
- Rates are 0–1 floats rounded to 4 places, like `/api/stats` (spec §7.1).
- Groups with fewer than 5 applications are marked "small sample"; no bare percentage without its count (spec §6.5).
- The Analytics total must equal the Dashboard "Applications" tile for the same filters; every mix sums to that total (spec §8).
- Charts work in light and dark theme and update immediately on theme change; no horizontal page scroll; one column below `md` (spec §6.8).
- The tab lives in the URL as `?tab=analytics` (spec §6.8).
- Seniority labels: Intern · Junior · Mid · Senior · Staff · Lead · Head / Director+ · Unspecified.
- Code style: match surrounding code (short docstrings, no heavy comments). Run Python with `uv run`; frontend commands from `web/`.
- Before writing chart code in Tasks 6–10, load the `dataviz` skill and follow its palette/axis/tooltip rules.

## File Structure

| File | Responsibility |
|---|---|
| `src/piper_jobs/categories.py` (modify) | Add `seniority()` and `normalize_title()` beside role-type rules |
| `src/piper_jobs/analytics.py` (create) | `compute_analytics`, `previous_filters` — pure aggregation, no I/O |
| `src/piper_jobs/api.py` (modify) | `GET /api/analytics` |
| `src/piper_jobs/seed.py` (modify) | Add design/product roles so sample data exercises the mixes |
| `tests/test_categories.py` (modify) | Seniority and title tests |
| `tests/test_analytics.py` (create) | Aggregation tests |
| `tests/test_analytics_api.py` (create) | Endpoint tests |
| `web/src/components/KpiCards.tsx` (modify) | Export `Kpi` for reuse |
| `web/src/lib/api.ts` (modify) | `Analytics` types, `api.analytics` |
| `web/src/lib/urlState.ts` (modify) | `"analytics"` tab |
| `web/src/lib/stages.ts` (modify) | `CATEGORY_COLOR`, `SENIORITY` labels |
| `web/src/App.tsx` (modify) | Nav entry, render `AnalyticsTab` |
| `web/src/components/analytics/format.ts` (create) | Date/bucket formatting, default granularity |
| `web/src/components/analytics/chartTheme.ts` (create) | Read theme colours from CSS variables |
| `web/src/components/analytics/AnalyticsTab.tsx` (create) | Query, granularity state, layout |
| `web/src/components/analytics/SummaryTiles.tsx` (create) | Six summary tiles |
| `web/src/components/analytics/AppsOverTime.tsx` (create) | Bars + 7-day average |
| `web/src/components/analytics/MixBars.tsx` (create) | Generic clickable horizontal bars |
| `web/src/components/analytics/Section.tsx` (create) | Card wrapper and segmented control shared by the widgets |
| `web/src/components/analytics/CategoryOverTime.tsx` (create) | 100% stacked weekly bars |
| `web/src/components/analytics/Heatmap.tsx` (create) | Calendar heatmap |
| `web/src/components/analytics/ConversionTable.tsx` (create) | Conversion by dimension |
| `web/src/components/analytics/Cohorts.tsx` (create) | Weekly cohort response-rate line |
| `docs/PRD.md`, `docs/PRD-analytics.md` (modify) | Mark shipped; README feature line |

---

### Task 0: Branch and commit the spec

**Files:** `docs/PRD-analytics.md`, `docs/PRD.md`, `docs/superpowers/plans/2026-10-30-analytics-tab.md`

- [ ] **Step 1: Create the feature branch from main**

```bash
git fetch origin 2>/dev/null; git checkout -b feat/analytics-tab main
```
Expected: `Switched to a new branch 'feat/analytics-tab'`. If the working tree carries the uncommitted docs, they come along.

- [ ] **Step 2: Commit the docs**

```bash
git add docs/PRD-analytics.md docs/PRD.md docs/superpowers/plans/2026-10-30-analytics-tab.md
git commit -m "docs: Analytics tab feature PRD and implementation plan"
```

---

### Task 1: Seniority and title normalisation

**Files:**
- Modify: `src/piper_jobs/categories.py` (append)
- Modify: `tests/test_categories.py` (append)

**Interfaces:**
- Produces: `SENIORITY_LEVELS: list[str]` = `["intern","junior","mid","senior","staff","lead","head","unspecified"]`; `seniority(role: str | None) -> str`; `normalize_title(role: str | None) -> str`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_categories.py`

```python
import pytest

from piper_jobs.categories import SENIORITY_LEVELS, normalize_title, seniority


@pytest.mark.parametrize("role,expected", [
    ("Sr. Product Designer", "senior"),
    ("Senior Product Manager", "senior"),
    ("Product Designer III", "senior"),
    ("Product Designer II", "mid"),
    ("Mid-level UX Designer", "mid"),
    ("Product Designer I", "junior"),
    ("Associate Product Manager", "junior"),
    ("Jr Designer", "junior"),
    ("Design Intern", "intern"),
    ("Staff Designer", "staff"),
    ("Principal Product Manager", "staff"),
    ("Design Lead", "lead"),
    ("Engineering Manager", "lead"),
    ("Head of Product", "head"),
    ("Senior Director of Design", "head"),
    ("VP Product", "head"),
    ("Product Designer", "unspecified"),
    ("Product Manager", "unspecified"),
    ("", "unspecified"),
    (None, "unspecified"),
])
def test_seniority(role, expected):
    assert seniority(role) == expected
    assert expected in SENIORITY_LEVELS


@pytest.mark.parametrize("role,expected", [
    ("Sr. Product Designer", "product designer"),
    ("Product Designer II", "product designer"),
    ("Senior  Product-Designer", "product designer"),
    ("Head of Product", "head of product"),
    (None, ""),
    ("", ""),
])
def test_normalize_title(role, expected):
    assert normalize_title(role) == expected
```

(If `tests/test_categories.py` already imports `pytest`, drop the duplicate import.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_categories.py -q`
Expected: FAIL — `ImportError: cannot import name 'SENIORITY_LEVELS'`.

- [ ] **Step 3: Implement** — append to `src/piper_jobs/categories.py`

```python
SENIORITY_LEVELS = ["intern", "junior", "mid", "senior", "staff", "lead", "head", "unspecified"]

# Checked in this order, so "Senior Director" is head, not senior. "Manager" alone is a job, not a level.
_SENIORITY_RULES: list[tuple[str, re.Pattern]] = [
    ("intern", re.compile(r"\b(intern|internship|trainee|apprentice)\b", re.I)),
    ("head", re.compile(r"\b(head of|director|vp|vice president|svp|evp|chief|cpo|cto|cdo|general manager)\b", re.I)),
    ("staff", re.compile(r"\b(staff|principal|distinguished|fellow)\b", re.I)),
    ("lead", re.compile(r"\b(lead|gpm|group product manager|(engineering|design|ux) manager)\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr)\b|\biii\b", re.I)),
    ("mid", re.compile(r"\b(mid|intermediate)\b|\bii\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr|associate|entry|graduate|apm)\b|\bi\b", re.I)),
]

_LEVEL_WORDS = {"intern", "junior", "jr", "senior", "sr", "staff", "principal", "lead", "mid",
                "i", "ii", "iii", "iv", "1", "2", "3", "4"}


def seniority(role: str | None) -> str:
    """Level from the role title; `unspecified` when the title carries no level."""
    for level, rx in _SENIORITY_RULES:
        if role and rx.search(role):
            return level
    return "unspecified"


def normalize_title(role: str | None) -> str:
    """Role title without level words or punctuation, so 'Sr. Designer' and 'Designer II' count together."""
    words = re.sub(r"[^\w\s]", " ", (role or "").lower()).split()
    return " ".join(w for w in words if w not in _LEVEL_WORDS)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_categories.py -q`
Expected: all pass. If `"Mid-level UX Designer"` fails, check that `\bmid\b` matches before the hyphen (it does); if `"Product Designer I"` returns `unspecified`, the `\bi\b` alternative is missing.

- [ ] **Step 5: Commit**

```bash
git add src/piper_jobs/categories.py tests/test_categories.py
git commit -m "feat(analytics): derive seniority and normalised title from the role"
```

---

### Task 2: Summary and time series

**Files:**
- Create: `src/piper_jobs/analytics.py`
- Create: `tests/test_analytics.py`

**Interfaces:**
- Consumes: `AppRow` from `filters.py`; `Application`, `Event` from `db.py`.
- Produces:
  - `compute_analytics(rows: list[AppRow], now: datetime, tz_offset: int = 0, granularity: str = "day", start: date | None = None, end: date | None = None, previous_total: int | None = None) -> dict`
  - `previous_filters(filters: Filters, today: date) -> Filters | None`
  - This task fills keys `range`, `summary`, `series`, `daily`; later tasks add the rest. `tz_offset` is minutes **ahead of** UTC (UTC+2 → `120`).
  - `series` / `daily` entries: `{"date": "YYYY-MM-DD", "count": int, "ids": [int], "apps": [{"id","company","role"}]}` (`daily` omits `apps`).

- [ ] **Step 1: Write the failing tests** — create `tests/test_analytics.py`

```python
from __future__ import annotations

from datetime import date, datetime, timedelta

from piper_jobs.analytics import compute_analytics, previous_filters
from piper_jobs.db import Application, Event
from piper_jobs.filters import AppRow, Filters

NOW = datetime(2026, 10, 30, 12, 0)  # a Friday; that week starts Mon 26 Oct
_ids = iter(range(1, 10_000))


def make_row(first_seen, *, stage="applied", events=None, role="Product Designer", category="product",
             source="linkedin", company="Acme", last_event=None) -> AppRow:
    app_id = next(_ids)
    app = Application(
        id=app_id, company_norm=company.lower(), company_display=company, role_norm=role.lower(),
        role_display=role, source=source, first_seen=first_seen, last_event_at=last_event or first_seen,
        current_stage=stage, category=category,
    )
    events = events if events is not None else [("applied", first_seen)]
    evs = [Event(application_id=app_id, stage=s, occurred_at=at) for s, at in events]
    return AppRow(app=app, events=evs, stage=stage, reached={e.stage for e in evs} | {stage})


def d(day: int, hour: int = 10, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour)


def run(rows, **kw):
    kw.setdefault("start", date(2026, 10, 24))
    kw.setdefault("end", date(2026, 10, 30))
    return compute_analytics(rows, NOW, **kw)


def test_series_is_zero_filled_and_sums_to_total():
    rows = [make_row(d(28)), make_row(d(28, 15)), make_row(d(25))]
    out = run(rows)
    assert [p["date"] for p in out["series"]] == [f"2026-10-{n}" for n in range(24, 31)]
    assert [p["count"] for p in out["series"]] == [0, 1, 0, 0, 2, 0, 0]
    assert sum(p["count"] for p in out["series"]) == out["summary"]["total"] == 3
    assert len(out["series"][4]["ids"]) == 2


def test_series_apps_are_capped_at_five_but_ids_are_complete():
    out = run([make_row(d(28, h)) for h in range(8)])
    point = next(p for p in out["series"] if p["date"] == "2026-10-28")
    assert point["count"] == 8 and len(point["ids"]) == 8 and len(point["apps"]) == 5


def test_tz_offset_moves_the_day():
    row = make_row(datetime(2026, 10, 28, 23, 30))
    assert next(p for p in run([row], tz_offset=0)["series"] if p["count"])["date"] == "2026-10-28"
    assert next(p for p in run([row], tz_offset=120)["series"] if p["count"])["date"] == "2026-10-29"


def test_range_widens_to_include_rows_outside_it():
    out = run([make_row(d(20))])  # before start (24 Oct)
    assert out["range"]["from"] == "2026-10-20"
    assert sum(p["count"] for p in out["series"]) == 1


def test_week_buckets_start_on_monday():
    rows = [make_row(d(26)), make_row(d(30))]
    out = run(rows, granularity="week", start=date(2026, 10, 20))
    assert [(p["date"], p["count"]) for p in out["series"]] == [("2026-10-19", 0), ("2026-10-26", 2)]


def test_month_buckets():
    rows = [make_row(d(20, month=9)), make_row(d(1))]
    out = run(rows, granularity="month", start=date(2026, 9, 15))
    assert [(p["date"], p["count"]) for p in out["series"]] == [("2026-09-01", 1), ("2026-10-01", 1)]


def test_summary_pace():
    rows = [make_row(d(30)), make_row(d(30, 14)), make_row(d(29)), make_row(d(26))]
    s = run(rows, previous_total=2)["summary"]
    assert s["total"] == 4 and s["previous_total"] == 2
    assert s["active_days"] == 3
    assert s["per_active_day"] == 1.33
    assert s["daily_average"] == round(4 / 7, 2)
    assert s["last_7d_average"] == round(4 / 7, 2)
    assert s["best_day"] == {"date": "2026-10-30", "count": 2}
    assert s["this_week"] == 4  # Mon 26 – Fri 30
    assert s["last_week"] == 0


def test_this_week_and_last_week():
    rows = [make_row(d(26)), make_row(d(30)), make_row(d(20))]
    s = run(rows, start=date(2026, 10, 19))["summary"]
    assert (s["this_week"], s["last_week"]) == (2, 1)


def test_streaks():
    def streak(days):
        s = run([make_row(d(n)) for n in days])["summary"]
        return s["streak"], s["longest_streak"]

    assert streak([30, 29, 28, 25]) == (3, 3)
    assert streak([29, 28]) == (2, 2)  # today not applied yet does not break it
    assert streak([29, 27]) == (1, 1)
    assert streak([27, 26, 25, 29]) == (1, 3)
    assert streak([]) == (0, 0)


def test_empty_input_has_full_shape():
    out = compute_analytics([], NOW, start=None, end=None)
    assert out["summary"]["total"] == 0
    assert out["summary"]["best_day"] is None
    assert out["summary"]["per_active_day"] == 0
    assert out["series"] == []
    assert out["range"] == {"from": None, "to": "2026-10-30"}


def test_previous_filters_shifts_the_window():
    prev = previous_filters(Filters(range="30d"), date(2026, 10, 30))
    # 30d = 30 Sep .. 30 Oct inclusive (31 days) -> previous 31 days ending 29 Sep
    assert (prev.range, prev.from_, prev.to) == ("custom", date(2026, 8, 30), date(2026, 9, 29))
    assert previous_filters(Filters(range="all"), date(2026, 10, 30)) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_analytics.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'piper_jobs.analytics'`.

- [ ] **Step 3: Implement** — create `src/piper_jobs/analytics.py`

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_analytics.py -q`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/piper_jobs/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): summary tiles data and zero-filled time series"
```

---

### Task 3: Mix, conversion, cohorts and pipeline-health data

**Files:**
- Modify: `src/piper_jobs/analytics.py`
- Modify: `tests/test_analytics.py` (append)

**Interfaces:**
- Consumes: Task 1 (`CATEGORIES`, `SENIORITY_LEVELS`, `seniority`, `normalize_title`), Task 2 (`_bucket`, `_bucket_starts`, and the test helpers `make_row`, `run`, `d`).
- Produces additional keys on `compute_analytics`:
  - `mix`: `{category|source|seniority: [{"key","count","ids"}]}` — every known key present (zero counts included), in fixed order.
  - `category_by_week`: `[{"week": iso, "design": n, "product": n, "vc": n, "other": n}]` (zero-filled; `[]` when no rows).
  - `top_titles`: `[{"title","count","ids"}]` (max 8); `top_companies`: `[{"company","count","stage","ids"}]` (max 8, only companies with 2+ applications).
  - `weekday`: 7 × `{"day": 0–6 (Mon=0), "count", "ids"}`.
  - `conversion`: `{source|category|seniority: [{"key","total","responded","interviewed","offers","median_days"}]}`, biggest group first; `responded`/`interviewed` are 0–1 rates, `offers` a count.
  - `cohorts`: `[{"week","total","responded","maturing"}]` for weeks that have applications; `maturing` is true when the week started under 14 days ago.
  - `response_time`: `{"buckets": [{"key","count"}], "median": float | None}`, keys `<=2d`, `3-7d`, `8-14d`, `15-30d`, `>30d`.
  - `open_by_age`: `[{"key","count","ids"}]`, keys `0-7d`, `8-14d`, `15-21d`, `22d+`; only non-terminal applications (not rejected / withdrawn / accepted / ghosted), by days since last event.
  - `outcomes`: `[{"key","count","ids"}]`, keys `active`, `rejected`, `ghosted`, `withdrawn`, `accepted`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_analytics.py`

```python
from piper_jobs.stats import compute_stats


def test_mix_sums_to_total_and_uses_stored_category():
    rows = [
        make_row(d(28), category="design", source="ats", role="Sr. Product Designer"),
        make_row(d(29), category="product", role="Product Manager"),
        make_row(d(30), category="product", role=""),
    ]
    mix = run(rows)["mix"]
    for name in ("category", "source", "seniority"):
        assert sum(x["count"] for x in mix[name]) == 3
    counts = lambda name: {x["key"]: x["count"] for x in mix[name]}  # noqa: E731
    assert counts("category") == {"design": 1, "product": 2, "vc": 0, "other": 0}
    assert counts("source")["ats"] == 1 and counts("source")["linkedin"] == 2
    assert counts("seniority")["senior"] == 1 and counts("seniority")["unspecified"] == 2
    assert [x["key"] for x in mix["category"]] == ["design", "product", "vc", "other"]
    assert len(next(x for x in mix["category"] if x["key"] == "product")["ids"]) == 2


def test_category_by_week_is_zero_filled():
    rows = [make_row(d(28), category="design"), make_row(d(29)), make_row(d(20))]
    out = run(rows, start=date(2026, 10, 19))["category_by_week"]
    assert out == [
        {"week": "2026-10-19", "design": 0, "product": 1, "vc": 0, "other": 0},
        {"week": "2026-10-26", "design": 1, "product": 1, "vc": 0, "other": 0},
    ]


def test_top_titles_and_companies():
    rows = [
        make_row(d(28), role="Sr. Product Designer", company="Acme"),
        make_row(d(29), role="Product Designer II", company="Acme", stage="interview", last_event=d(30)),
        make_row(d(30), role="Product Designer", company="Beta"),
        make_row(d(30, 13), role="Product Manager", company="Gamma"),
    ]
    out = run(rows)
    assert out["top_titles"][0]["title"] == "product designer" and out["top_titles"][0]["count"] == 3
    assert [c["company"] for c in out["top_companies"]] == ["Acme"]
    assert out["top_companies"][0]["count"] == 2 and out["top_companies"][0]["stage"] == "interview"
    assert len(out["top_companies"][0]["ids"]) == 2


def test_weekday_counts():
    out = run([make_row(d(28)), make_row(d(28, 15)), make_row(d(30))])["weekday"]
    assert [w["day"] for w in out] == list(range(7))
    assert out[2]["count"] == 2 and out[4]["count"] == 1  # Wed, Fri


def _funnel_rows():
    first = d(20)
    return [
        make_row(first, stage="interview", events=[("applied", first), ("interview", d(23))]),
        make_row(first, events=[("applied", first)]),
        make_row(first, stage="rejected", events=[("applied", first), ("rejected", d(25))]),
        make_row(first, events=[("applied", first)]),
        make_row(first, source="ats", stage="offer", events=[("applied", first), ("offer", d(22))]),
    ]


def test_conversion_by_source():
    by = {g["key"]: g for g in run(_funnel_rows(), start=date(2026, 10, 20))["conversion"]["source"]}
    # linkedin: interview after 3 days and rejection after 5 -> half responded, median 4.0 days
    assert by["linkedin"] == {"key": "linkedin", "total": 4, "responded": 0.5, "interviewed": 0.25,
                              "offers": 0, "median_days": 4.0}
    assert by["ats"] == {"key": "ats", "total": 1, "responded": 1.0, "interviewed": 1.0,
                         "offers": 1, "median_days": 2.0}


def test_conversion_agrees_with_dashboard_stats():
    rows = _funnel_rows()
    stats = compute_stats(rows)
    conv = run(rows, start=date(2026, 10, 20))["conversion"]
    for dim in ("source", "category", "seniority"):
        assert sum(round(g["responded"] * g["total"]) for g in conv[dim]) == round(stats["response_rate"] * stats["total"])
        assert sum(round(g["interviewed"] * g["total"]) for g in conv[dim]) == round(stats["interview_rate"] * stats["total"])
        totals = [g["total"] for g in conv[dim]]
        assert totals == sorted(totals, reverse=True)


def test_cohorts_flag_recent_weeks_as_maturing():
    rows = [
        make_row(d(30), stage="interview", events=[("applied", d(30)), ("interview", d(30, 11))]),
        make_row(d(29)),
        make_row(d(10)),
    ]
    out = run(rows, start=date(2026, 10, 5))["cohorts"]
    assert out == [
        {"week": "2026-10-05", "total": 1, "responded": 0.0, "maturing": False},
        {"week": "2026-10-26", "total": 2, "responded": 0.5, "maturing": True},
    ]


def test_response_time_buckets_and_median():
    def replied(days):
        return make_row(d(1), stage="interview", events=[("applied", d(1)), ("interview", d(1) + timedelta(days=days))])

    out = run([replied(1), replied(5), replied(40), make_row(d(2))], start=date(2026, 10, 1))["response_time"]
    assert {b["key"]: b["count"] for b in out["buckets"]} == {"<=2d": 1, "3-7d": 1, "8-14d": 0, "15-30d": 0, ">30d": 1}
    assert out["median"] == 5.0


def test_open_by_age_and_outcomes():
    rows = [
        make_row(d(25), last_event=d(28)),  # 2 days -> 0-7d
        make_row(d(5), stage="interview", last_event=d(12)),  # 18 days -> 15-21d
        make_row(d(5), stage="rejected"),
        make_row(d(5), stage="ghosted"),
        make_row(d(5), stage="withdrawn"),
    ]
    out = run(rows, start=date(2026, 10, 1))
    assert {b["key"]: b["count"] for b in out["open_by_age"]} == {"0-7d": 1, "8-14d": 0, "15-21d": 1, "22d+": 0}
    assert {o["key"]: o["count"] for o in out["outcomes"]} == {
        "active": 2, "rejected": 1, "ghosted": 1, "withdrawn": 1, "accepted": 0}


def test_empty_input_has_every_key():
    out = compute_analytics([], NOW, start=None, end=None)
    assert set(out) == {"range", "summary", "series", "daily", "mix", "category_by_week", "top_titles",
                        "top_companies", "weekday", "conversion", "cohorts", "response_time",
                        "open_by_age", "outcomes"}
    assert out["response_time"]["median"] is None
    assert all(g["count"] == 0 for g in out["mix"]["category"])
    assert out["conversion"]["source"] == [] and out["cohorts"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_analytics.py -q`
Expected: the new tests FAIL with `KeyError: 'mix'`; the Task 2 tests still pass.

- [ ] **Step 3: Implement** — in `src/piper_jobs/analytics.py` replace the imports block, add the constants and helpers, and replace `compute_analytics`.

Imports (top of file):

```python
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import date, datetime, timedelta
from statistics import median

from .categories import CATEGORIES, SENIORITY_LEVELS, normalize_title, seniority
from .filters import AppRow, Filters
from .schema import SOURCES
from .stats import INTERVIEW_STAGES, OFFER_STAGES, RESPONSE_STAGES, _rate, first_response_days
```

Constants (below `HEATMAP_DAYS`):

```python
TOP_N = 8
OPEN_STAGES = {"applied", "viewed", "assessment", "interview", "offer"}
OUTCOME_KEYS = ["active", "rejected", "ghosted", "withdrawn", "accepted"]
RESPONSE_BUCKETS = [("<=2d", 2), ("3-7d", 7), ("8-14d", 14), ("15-30d", 30), (">30d", None)]
AGE_BUCKETS = [("0-7d", 7), ("8-14d", 14), ("15-21d", 21), ("22d+", None)]
```

Helpers (below `_summary`):

```python
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
```

Replace `compute_analytics` entirely:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_analytics.py -q`
Expected: all pass. (`offer` is in `RESPONSE_STAGES`, so the ats row counts as responded; its first response is the `offer` event 2 days after `first_seen`.)

- [ ] **Step 5: Commit**

```bash
git add src/piper_jobs/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): mix, conversion, cohort and pipeline-health aggregations"
```

---

### Task 4: `GET /api/analytics`

**Files:**
- Modify: `src/piper_jobs/api.py` (import; new route after `/api/insights`)
- Create: `tests/test_analytics_api.py`

**Interfaces:**
- Consumes: `compute_analytics`, `previous_filters` (Tasks 2–3); existing `get_filters`, `rows_for`, `session_dep`, `utcnow`, `timedelta`, `Literal`, `Query` in `api.py`.
- Produces: `GET /api/analytics?<shared filters>&granularity=day|week|month&tz_offset=<minutes ahead of UTC, −840…840>` returning the `compute_analytics` dict. `previous_total` counts the same filters shifted back by the range length (`null` for range `all`).

- [ ] **Step 1: Write the failing tests** — create `tests/test_analytics_api.py`

```python
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from piper_jobs.api import create_app
from piper_jobs.db import get_engine, utcnow
from piper_jobs.resolver import apply_event


@pytest.fixture
def client(settings):
    now = utcnow()
    with Session(get_engine(settings.db_path)) as s:
        # first_seen: 10, 60, 120 and 300 days ago
        for company, days, source, stages in [
            ("Recent", 10, "linkedin", ["applied", "interview"]),
            ("Mid", 60, "ats", ["applied", "rejected"]),
            ("Older", 120, "linkedin", ["applied", "viewed"]),
            ("Ancient", 300, "recruiter", ["applied", "offer", "accepted"]),
        ]:
            for i, stage in enumerate(stages):
                apply_event(s, company=company, role="Product Designer", stage=stage, source=source,
                            occurred_at=now - timedelta(days=days - i))
        s.commit()
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.mark.parametrize("params", [
    {"range": "30d"}, {"range": "180d"}, {"range": "all"}, {"range": "all", "sources": "linkedin"},
])
def test_totals_agree_with_the_rest_of_the_app(client, params):
    data = client.get("/api/analytics", params=params).json()
    total = client.get("/api/stats", params=params).json()["total"]
    assert data["summary"]["total"] == total == len(client.get("/api/applications", params=params).json())
    assert sum(p["count"] for p in data["series"]) == total
    for name in ("category", "source", "seniority"):
        assert sum(g["count"] for g in data["mix"][name]) == total
    assert sum(o["count"] for o in data["outcomes"]) == total


def test_previous_total_compares_the_shifted_window(client):
    # the 30d window holds "Recent"; the 31 days before it hold "Mid" (60 days ago)
    data = client.get("/api/analytics", params={"range": "30d"}).json()
    assert data["summary"]["total"] == 1 and data["summary"]["previous_total"] == 1
    assert client.get("/api/analytics", params={"range": "all"}).json()["summary"]["previous_total"] is None


def test_granularity_changes_the_buckets(client):
    day = client.get("/api/analytics", params={"range": "30d", "granularity": "day"}).json()["series"]
    week = client.get("/api/analytics", params={"range": "30d", "granularity": "week"}).json()["series"]
    assert len(day) >= 30 and len(week) <= 6


@pytest.mark.parametrize("params", [{"granularity": "year"}, {"tz_offset": 99999}])
def test_invalid_parameters_are_rejected(client, params):
    assert client.get("/api/analytics", params=params).status_code == 422
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_analytics_api.py -q`
Expected: FAIL — 404 on `/api/analytics`.

- [ ] **Step 3: Implement** — in `src/piper_jobs/api.py`

Add next to the `from .stats import ...` line:

```python
from .analytics import compute_analytics, previous_filters
```

Add the route right after the `insights` route:

```python
    @app.get("/api/analytics")
    def analytics(
        filters: Filters = Depends(get_filters),
        granularity: Literal["day", "week", "month"] = "day",
        tz_offset: int = Query(0, ge=-840, le=840),  # minutes ahead of UTC, so days match the user's
        session: Session = Depends(session_dep),
    ):
        now = utcnow()
        today = (now + timedelta(minutes=tz_offset)).date()
        start, end = filters.date_bounds(today)
        previous = previous_filters(filters, today)
        previous_total = len(rows_for(session, previous)) if previous else None
        return compute_analytics(rows_for(session, filters), now, tz_offset, granularity, start, end, previous_total)
```

- [ ] **Step 4: Run the whole backend suite**

Run: `uv run pytest -q`
Expected: all pass, including the existing suites.

- [ ] **Step 5: Commit**

```bash
git add src/piper_jobs/api.py tests/test_analytics_api.py
git commit -m "feat(analytics): GET /api/analytics endpoint"
```

---

### Task 5: Seed variety (so the charts have something to show)

**Files:**
- Modify: `src/piper_jobs/seed.py` (the `ROLES` list)

- [ ] **Step 1: Add design, product and VC roles** — replace the `ROLES` list:

```python
ROLES = [
    "Software Engineer", "Backend Engineer", "Full Stack Developer", "Senior Software Engineer",
    "Platform Engineer", "Data Engineer", "Frontend Engineer", "SDE II",
    "Product Designer", "Senior Product Designer", "UX Designer", "Design Lead",
    "Product Manager", "Senior Product Manager", "Associate Product Manager",
    "Investment Associate",
]
```

- [ ] **Step 2: Run the suite** (some tests seed data)

Run: `uv run pytest -q`
Expected: all pass. If a test asserts on the exact seeded roles, loosen that assertion rather than shrinking `ROLES`.

- [ ] **Step 3: Commit**

```bash
git add src/piper_jobs/seed.py
git commit -m "chore(seed): add design, product and VC roles to sample data"
```

---

### Task 6: Frontend plumbing and summary tiles

**Files:**
- Modify: `web/src/lib/api.ts`, `web/src/lib/urlState.ts`, `web/src/lib/stages.ts`, `web/src/components/KpiCards.tsx`, `web/src/App.tsx`
- Create: `web/src/components/analytics/format.ts`, `chartTheme.ts`, `Section.tsx`, `SummaryTiles.tsx`, `AnalyticsTab.tsx`

**Interfaces:**
- Produces:
  - `api.analytics(f: Filters, granularity: Granularity, tzOffset?: number): Promise<Analytics>`; types `Granularity`, `Analytics`, `AnalyticsPoint`, `AnalyticsGroup`, `AnalyticsConversion`.
  - `Tab` includes `"analytics"`.
  - `CATEGORY_COLOR: Record<Category, string>`, `SENIORITY_LABEL: Record<string, string>` in `lib/stages.ts`.
  - `format.ts`: `defaultGranularity(f)`, `parseDay(iso)`, `fmtBucket(iso, g)`, `WEEKDAYS`, `pct(n)`, `esc(s)`.
  - `chartTheme.ts`: `chartColors()`, `tooltipStyle(c)`, `reducedMotion()`.
  - `Section.tsx`: `Section({title, hint?, right?, children, className?})`, `Segmented<T>({value, options, onChange})`.
  - `AnalyticsTab({ filters, dark, onSelect })` — holds the line `{/* widgets: keep this line, new sections go above it */}` that later tasks insert above (Task 10 removes it).
  - `Kpi` exported from `KpiCards.tsx`.

- [ ] **Step 1: Types and client** — in `web/src/lib/api.ts` add after the `Stats` interface:

```ts
export type Granularity = "day" | "week" | "month";

export interface AnalyticsPoint {
  date: string;
  count: number;
  ids: number[];
  apps?: { id: number; company: string; role: string }[];
}

export interface AnalyticsGroup {
  key: string;
  count: number;
  ids: number[];
}

export interface AnalyticsConversion {
  key: string;
  total: number;
  responded: number;
  interviewed: number;
  offers: number;
  median_days: number | null;
}

export interface Analytics {
  range: { from: string | null; to: string };
  summary: {
    total: number;
    previous_total: number | null;
    active_days: number;
    per_active_day: number;
    daily_average: number;
    last_7d_average: number;
    streak: number;
    longest_streak: number;
    best_day: { date: string; count: number } | null;
    this_week: number;
    last_week: number;
  };
  series: AnalyticsPoint[];
  daily: AnalyticsPoint[];
  mix: { category: AnalyticsGroup[]; source: AnalyticsGroup[]; seniority: AnalyticsGroup[] };
  category_by_week: ({ week: string } & Record<Category, number>)[];
  top_titles: { title: string; count: number; ids: number[] }[];
  top_companies: { company: string; count: number; stage: Stage; ids: number[] }[];
  weekday: { day: number; count: number; ids: number[] }[];
  conversion: { source: AnalyticsConversion[]; category: AnalyticsConversion[]; seniority: AnalyticsConversion[] };
  cohorts: { week: string; total: number; responded: number; maturing: boolean }[];
  response_time: { buckets: { key: string; count: number }[]; median: number | null };
  open_by_age: AnalyticsGroup[];
  outcomes: AnalyticsGroup[];
}
```

and in the `api` object after `stats`:

```ts
  analytics: (f: Filters, granularity: Granularity, tzOffset = -new Date().getTimezoneOffset()) => {
    const p = filterParams(f);
    p.set("granularity", granularity);
    p.set("tz_offset", String(tzOffset)); // minutes ahead of UTC; getTimezoneOffset() is minutes behind
    return http<Analytics>(`/api/analytics?${p}`);
  },
```

- [ ] **Step 2: Tab in the URL** — in `web/src/lib/urlState.ts` change the two lines:

```ts
export type Tab = "dashboard" | "analytics" | "applications" | "review";
const TABS: Tab[] = ["dashboard", "analytics", "applications", "review"];
```

- [ ] **Step 3: Shared constants** — append to `web/src/lib/stages.ts`:

```ts
// Role types are a categorical series, so each keeps one colour everywhere it is drawn.
export const CATEGORY_COLOR: Record<Category, string> = {
  design: "#8b6fd6",
  product: "#2a78d6",
  vc: "#d98a1f",
  other: "#9a988f",
};

export const SENIORITY_LABEL: Record<string, string> = {
  intern: "Intern",
  junior: "Junior",
  mid: "Mid",
  senior: "Senior",
  staff: "Staff / Principal",
  lead: "Lead",
  head: "Head / Director+",
  unspecified: "Unspecified",
};
```

- [ ] **Step 4: Export the KPI card** — in `web/src/components/KpiCards.tsx` change `function Kpi(` to `export function Kpi(`.

- [ ] **Step 5: Helpers** — create `web/src/components/analytics/format.ts`:

```ts
import type { Filters, Granularity } from "../../lib/api";

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const pct = (n: number) => `${Math.round(n * 100)}%`;

/** Escape text that goes into an ECharts HTML tooltip (company and role names come from email). */
export const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

/** A YYYY-MM-DD string as a local-midnight Date. */
export const parseDay = (iso: string) => new Date(`${iso}T00:00:00`);

export function fmtBucket(iso: string, g: Granularity) {
  const d = parseDay(iso);
  if (g === "month") return d.toLocaleDateString(undefined, { month: "short", year: "numeric" });
  const label = d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return g === "week" ? `Week of ${label}` : label;
}

/** Day bars up to ~3 months, weekly beyond that. */
export function defaultGranularity(f: Filters): Granularity {
  if (f.range === "180d" || f.range === "all") return "week";
  if (f.range === "custom" && f.from) {
    const to = f.to ? parseDay(f.to) : new Date();
    return (to.getTime() - parseDay(f.from).getTime()) / 86_400_000 > 90 ? "week" : "day";
  }
  return "day";
}
```

Create `web/src/components/analytics/chartTheme.ts`:

```ts
export interface ChartColors {
  ink: string;
  ink2: string;
  muted: string;
  line: string;
  surface: string;
  accent: string;
}

/** Read the live theme colours; call inside a memo that depends on `dark` so charts follow the toggle. */
export function chartColors(): ChartColors {
  const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return {
    ink: css("--text"),
    ink2: css("--text-2"),
    muted: css("--muted"),
    line: css("--border"),
    surface: css("--surface"),
    accent: css("--accent"),
  };
}

export const tooltipStyle = (c: ChartColors) => ({
  backgroundColor: c.surface,
  borderColor: c.line,
  textStyle: { color: c.ink, fontSize: 12 },
  extraCssText: "border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);",
});

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
```

Create `web/src/components/analytics/Section.tsx`:

```tsx
import type { ReactNode } from "react";
import { cx } from "../ui";

export function Section({
  title,
  hint,
  right,
  children,
  className,
}: {
  title: string;
  hint?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("card p-4", className)}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {hint && <div className="text-xs text-muted">{hint}</div>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex rounded-lg border border-line p-0.5 text-xs">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cx("h-6 rounded-md px-2.5", o.value === value ? "bg-surface-2 font-medium text-ink" : "text-ink-2 hover:text-ink")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Summary tiles** — create `web/src/components/analytics/SummaryTiles.tsx`:

```tsx
import type { Analytics } from "../../lib/api";
import { Kpi } from "../KpiCards";
import { fmtDate } from "../ui";

const int = (n: number) => String(Math.round(n));
const one = (n: number) => n.toFixed(1);

function versus(now: number, before: number | null, what: string) {
  if (before == null) return undefined;
  if (before === 0) return now > 0 ? `▲ from none ${what}` : `same as ${what}`;
  const change = Math.round(((now - before) / before) * 100);
  if (change === 0) return `same as ${what}`;
  return `${change > 0 ? "▲" : "▼"} ${Math.abs(change)}% vs ${what}`;
}

export function SummaryTiles({ s }: { s: Analytics["summary"] | undefined }) {
  const days = (n: number) => `${n} day${n === 1 ? "" : "s"}`;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <Kpi label="Applications" value={s?.total ?? null} format={int} hint={s ? versus(s.total, s.previous_total, "previous period") : undefined} />
      <Kpi label="Per active day" value={s?.per_active_day ?? null} format={one} hint={s ? `on ${days(s.active_days)} with an application` : undefined} />
      <Kpi label="Daily average" value={s?.daily_average ?? null} format={(n) => n.toFixed(2)} hint={s ? `${s.last_7d_average.toFixed(1)} a day over the last 7 days` : undefined} />
      <Kpi label="Current streak" value={s?.streak ?? null} format={int} hint={s ? `longest ${days(s.longest_streak)}` : undefined} />
      <Kpi label="Best day" value={s?.best_day?.count ?? null} format={int} hint={s?.best_day ? fmtDate(s.best_day.date) : undefined} />
      <Kpi label="This week" value={s?.this_week ?? null} format={int} hint={s ? versus(s.this_week, s.last_week, "last week") : undefined} />
    </div>
  );
}
```

- [ ] **Step 7: The tab** — create `web/src/components/analytics/AnalyticsTab.tsx`:

```tsx
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, type Filters, type Granularity } from "../../lib/api";
import type { Selection } from "../SankeyChart";
import { Empty } from "../ui";
import { defaultGranularity } from "./format";
import { SummaryTiles } from "./SummaryTiles";

export function AnalyticsTab({ filters, dark, onSelect }: { filters: Filters; dark: boolean; onSelect: (s: Selection) => void }) {
  const [chosen, setChosen] = useState<Granularity | null>(null);
  const granularity = chosen ?? defaultGranularity(filters);
  const { data } = useQuery({
    queryKey: ["analytics", filters, granularity],
    queryFn: () => api.analytics(filters, granularity),
    placeholderData: keepPreviousData,
  });

  if (data && data.summary.total === 0) {
    return (
      <div className="card">
        <Empty title="No applications in this range">
          Widen the date range, run a sync, or try sample data with <code>piper seed</code>.
        </Empty>
      </div>
    );
  }

  void [dark, onSelect, setChosen]; // used by the widgets added in the following tasks
  return (
    <div className="anim-fade-up flex flex-col gap-4">
      <SummaryTiles s={data?.summary} />
      {/* widgets: keep this line, new sections go above it */}
    </div>
  );
}
```

- [ ] **Step 8: Wire into the app** — in `web/src/App.tsx`:

Add the import: `import { AnalyticsTab } from "./components/analytics/AnalyticsTab";`

Add the nav entry after the dashboard entry in `NAV`:

```ts
  { tab: "analytics", label: "Analytics", icon: "▤" },
```

Add the tab body after the `{tab === "dashboard" && (...)}` block and before `{tab === "applications" && ...}`:

```tsx
          {tab === "analytics" && <AnalyticsTab filters={filters} dark={dark} onSelect={onSelect} />}
```

- [ ] **Step 9: Typecheck**

Run (from `web/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add web/src
git commit -m "feat(analytics): Analytics tab with summary tiles"
```

---

### Task 7: Applications over time

**Files:**
- Create: `web/src/components/analytics/AppsOverTime.tsx`
- Modify: `web/src/components/analytics/AnalyticsTab.tsx`

**Interfaces:**
- Consumes: Task 6 helpers (`chartColors`, `tooltipStyle`, `reducedMotion`, `fmtBucket`, `esc`, `Section`, `Segmented`).
- Produces: `AppsOverTime({ data, granularity, showAverage, dark, onSelect })`.

- [ ] **Step 1: The chart** — create `web/src/components/analytics/AppsOverTime.tsx`:

```tsx
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { AnalyticsPoint, Granularity } from "../../lib/api";
import type { Selection } from "../SankeyChart";
import { chartColors, reducedMotion, tooltipStyle } from "./chartTheme";
import { esc, fmtBucket } from "./format";

/** Mean of the last 7 points; null until there are 7. */
function trailingAverage(counts: number[]) {
  return counts.map((_, i) => (i < 6 ? null : Math.round((counts.slice(i - 6, i + 1).reduce((a, b) => a + b, 0) / 7) * 100) / 100));
}

export function AppsOverTime({
  data,
  granularity,
  showAverage,
  dark,
  onSelect,
}: {
  data: AnalyticsPoint[];
  granularity: Granularity;
  showAverage: boolean;
  dark: boolean;
  onSelect: (s: Selection) => void;
}) {
  const option = useMemo(() => {
    const c = chartColors(); // reads the live theme, so `dark` is a dependency below
    const counts = data.map((p) => p.count);
    const average = showAverage && granularity === "day" ? trailingAverage(counts) : null;
    return {
      animation: !reducedMotion(),
      grid: { left: 32, right: 12, top: 16, bottom: 28 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        ...tooltipStyle(c),
        formatter: (params: { dataIndex: number }[]) => {
          const p = data[params[0].dataIndex];
          const lines = (p.apps ?? []).map((a) => `${esc(a.company)} <span style="opacity:.7">· ${esc(a.role || "role not stated")}</span>`);
          const more = p.count - lines.length;
          const avg = average?.[params[0].dataIndex];
          return [
            `<b>${fmtBucket(p.date, granularity)}</b> · ${p.count} application${p.count === 1 ? "" : "s"}`,
            ...lines,
            more > 0 ? `+${more} more` : "",
            avg != null ? `<span style="opacity:.7">7-day average ${avg}</span>` : "",
          ]
            .filter(Boolean)
            .join("<br/>");
        },
      },
      xAxis: {
        type: "category",
        data: data.map((p) => fmtBucket(p.date, granularity)),
        axisLabel: { color: c.ink2, fontSize: 11, hideOverlap: true },
        axisLine: { lineStyle: { color: c.line } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        axisLabel: { color: c.ink2, fontSize: 11 },
        splitLine: { lineStyle: { color: c.line } },
      },
      series: [
        { name: "Applications", type: "bar", data: counts, barMaxWidth: 28, itemStyle: { color: c.accent, borderRadius: [3, 3, 0, 0] } },
        ...(average
          ? [{ name: "7-day average", type: "line", data: average, smooth: true, showSymbol: false, z: 3, lineStyle: { color: c.ink2, width: 2 }, itemStyle: { color: c.ink2 } }]
          : []),
      ],
    };
  }, [data, granularity, showAverage, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  const onEvents = useMemo(
    () => ({
      click: (p: { seriesType: string; dataIndex: number }) => {
        const point = data[p.dataIndex];
        if (p.seriesType === "bar" && point?.ids.length) onSelect({ title: fmtBucket(point.date, granularity), ids: point.ids });
      },
    }),
    [data, granularity, onSelect],
  );

  return <ReactECharts option={option} onEvents={onEvents} notMerge style={{ height: 280, width: "100%" }} opts={{ renderer: "svg" }} />;
}
```

- [ ] **Step 2: Use it in the tab** — in `AnalyticsTab.tsx` add imports:

```tsx
import { AppsOverTime } from "./AppsOverTime";
import { Section, Segmented } from "./Section";
```

Delete the `void [dark, onSelect, setChosen]; ...` line, and insert above the `{/* widgets ... */}` line:

```tsx
      {data && (
        <Section
          title="Applications over time"
          hint={data.summary.total < 7 ? "The 7-day average appears once there are 7 applications" : undefined}
          right={
            <Segmented
              value={granularity}
              onChange={setChosen}
              options={[
                { value: "day", label: "Day" },
                { value: "week", label: "Week" },
                { value: "month", label: "Month" },
              ]}
            />
          }
        >
          <AppsOverTime data={data.series} granularity={granularity} showAverage={data.summary.total >= 7} dark={dark} onSelect={onSelect} />
        </Section>
      )}
```

- [ ] **Step 3: Typecheck**

Run (from `web/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/src
git commit -m "feat(analytics): applications-over-time chart with granularity switch"
```

---

### Task 8: Mix widgets (role type, source, seniority, titles, companies, role type over time)

**Files:**
- Create: `web/src/components/analytics/MixBars.tsx`, `CategoryOverTime.tsx`
- Modify: `web/src/components/analytics/AnalyticsTab.tsx`

**Interfaces:**
- Consumes: Task 6 (`Section`, `chartTheme`, `CATEGORY_COLOR`, `SENIORITY_LABEL`, `sourceLabel`, `categoryLabel`, `stageLabel`).
- Produces: `MixItem = { key: string; label: string; count: number; ids?: number[]; color?: string }`; `MixBars({ items, title, onSelect?, empty? })` — horizontal bars with share of the items' total; rows carrying `ids` are clickable; `CategoryOverTime({ data, dark })`.

- [ ] **Step 1: Generic bars** — create `web/src/components/analytics/MixBars.tsx`:

```tsx
import type { Selection } from "../SankeyChart";
import { cx } from "../ui";
import { pct } from "./format";

export interface MixItem {
  key: string;
  label: string;
  count: number;
  ids?: number[];
  color?: string;
}

/** Horizontal bars with count and share. Rows that carry application ids open the side panel. */
export function MixBars({
  items,
  title,
  onSelect,
  empty = "Nothing to show yet",
}: {
  items: MixItem[];
  title: string;
  onSelect?: (s: Selection) => void;
  empty?: string;
}) {
  const total = items.reduce((sum, i) => sum + i.count, 0);
  const max = Math.max(1, ...items.map((i) => i.count));
  if (total === 0) return <div className="py-6 text-center text-sm text-muted">{empty}</div>;
  return (
    <ul className="flex flex-col gap-1">
      {items.map((i) => {
        const clickable = !!onSelect && !!i.ids?.length;
        return (
          <li key={i.key}>
            <button
              disabled={!clickable}
              onClick={() => clickable && onSelect!({ title: `${title}: ${i.label}`, ids: i.ids! })}
              className={cx(
                "grid w-full grid-cols-[minmax(6rem,11rem)_1fr_5rem] items-center gap-2 rounded-md px-1 py-0.5 text-left text-sm",
                clickable ? "hover:bg-surface-2" : "cursor-default",
              )}
            >
              <span className="truncate text-ink-2" title={i.label}>
                {i.label}
              </span>
              <span className="h-3 rounded-sm bg-surface-2">
                <span className="block h-full rounded-sm" style={{ width: `${(i.count / max) * 100}%`, background: i.color ?? "var(--accent)" }} />
              </span>
              <span className="tabular text-right text-ink">
                {i.count} <span className="text-muted">· {pct(i.count / total)}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
```

- [ ] **Step 2: Role type over time** — create `web/src/components/analytics/CategoryOverTime.tsx`:

```tsx
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { Analytics } from "../../lib/api";
import { CATEGORIES, CATEGORY_COLOR, categoryLabel } from "../../lib/stages";
import { chartColors, reducedMotion, tooltipStyle } from "./chartTheme";
import { fmtBucket, pct } from "./format";

export function CategoryOverTime({ data, dark }: { data: Analytics["category_by_week"]; dark: boolean }) {
  const option = useMemo(() => {
    const c = chartColors();
    const totals = data.map((w) => CATEGORIES.reduce((sum, cat) => sum + w[cat.value], 0));
    return {
      animation: !reducedMotion(),
      grid: { left: 40, right: 12, top: 12, bottom: 36 },
      legend: { bottom: 0, textStyle: { color: c.ink2, fontSize: 11 }, icon: "roundRect", itemWidth: 10, itemHeight: 10 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        ...tooltipStyle(c),
        formatter: (params: { dataIndex: number }[]) => {
          const i = params[0].dataIndex;
          const w = data[i];
          const rows = CATEGORIES.filter((cat) => w[cat.value] > 0).map(
            (cat) => `${categoryLabel(cat.value)}: ${w[cat.value]} (${pct(w[cat.value] / totals[i])})`,
          );
          return [`<b>${fmtBucket(w.week, "week")}</b> · ${totals[i]} applications`, ...rows].join("<br/>");
        },
      },
      xAxis: {
        type: "category",
        data: data.map((w) => fmtBucket(w.week, "day")),
        axisLabel: { color: c.ink2, fontSize: 11, hideOverlap: true },
        axisLine: { lineStyle: { color: c.line } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        max: 100,
        axisLabel: { color: c.ink2, fontSize: 11, formatter: "{value}%" },
        splitLine: { lineStyle: { color: c.line } },
      },
      series: CATEGORIES.map((cat) => ({
        name: cat.label,
        type: "bar",
        stack: "share",
        barMaxWidth: 36,
        itemStyle: { color: CATEGORY_COLOR[cat.value] },
        data: data.map((w, i) => (totals[i] ? (w[cat.value] / totals[i]) * 100 : 0)),
      })),
    };
  }, [data, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  return <ReactECharts option={option} notMerge style={{ height: 260, width: "100%" }} opts={{ renderer: "svg" }} />;
}
```

- [ ] **Step 3: Lay them out** — in `AnalyticsTab.tsx` add imports (merge `type Category` into the existing `../../lib/api` import):

```tsx
import { CATEGORY_COLOR, SENIORITY_LABEL, categoryLabel, sourceLabel, stageLabel } from "../../lib/stages";
import { CategoryOverTime } from "./CategoryOverTime";
import { MixBars } from "./MixBars";
```

and insert above the `{/* widgets ... */}` line:

```tsx
      {data && (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Role type" hint="What kind of roles you apply to">
              <MixBars
                title="Role type"
                onSelect={onSelect}
                items={data.mix.category.map((g) => ({ ...g, label: categoryLabel(g.key), color: CATEGORY_COLOR[g.key as Category] }))}
              />
            </Section>
            <Section title="Source" hint="Where applications come from">
              <MixBars title="Source" onSelect={onSelect} items={data.mix.source.map((g) => ({ ...g, label: sourceLabel(g.key) }))} />
            </Section>
            <Section title="Seniority" hint="Read from the role title">
              <MixBars title="Seniority" onSelect={onSelect} items={data.mix.seniority.map((g) => ({ ...g, label: SENIORITY_LABEL[g.key] ?? g.key }))} />
            </Section>
            <Section title="Top role titles" hint="Levels removed: “Sr. Designer” and “Designer II” count together">
              <MixBars
                title="Role"
                onSelect={onSelect}
                items={data.top_titles.map((t) => ({ key: t.title, label: t.title.replace(/\b\w/g, (m) => m.toUpperCase()), count: t.count, ids: t.ids }))}
                empty="No role titles yet"
              />
            </Section>
            <Section title="Companies applied to more than once">
              <MixBars
                title="Company"
                onSelect={onSelect}
                items={data.top_companies.map((c) => ({ key: c.company, label: `${c.company} · ${stageLabel(c.stage)}`, count: c.count, ids: c.ids }))}
                empty="No company has more than one application"
              />
            </Section>
          </div>
          {data.category_by_week.length >= 3 && (
            <Section title="Role type over time" hint="Share of each week’s applications">
              <CategoryOverTime data={data.category_by_week} dark={dark} />
            </Section>
          )}
        </>
      )}
```

- [ ] **Step 4: Typecheck**

Run (from `web/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(analytics): role type, source, seniority, titles and companies widgets"
```

---

### Task 9: When I apply (heatmap and weekday)

**Files:**
- Create: `web/src/components/analytics/Heatmap.tsx`
- Modify: `web/src/components/analytics/AnalyticsTab.tsx`

**Interfaces:**
- Consumes: `AnalyticsPoint[]` (`daily`, consecutive days), `parseDay`, `fmtBucket`, `WEEKDAYS`, `MixBars`.
- Produces: `Heatmap({ days, onSelect })`.

- [ ] **Step 1: Heatmap** — create `web/src/components/analytics/Heatmap.tsx`:

```tsx
import type { AnalyticsPoint } from "../../lib/api";
import type { Selection } from "../SankeyChart";
import { fmtBucket, parseDay } from "./format";

const LEVELS = 4;
const shade = (level: number) =>
  level === 0 ? "var(--surface-2)" : `color-mix(in srgb, var(--accent) ${(100 / LEVELS) * level}%, var(--surface-2))`;

/** One square per day, a column per week (Monday on top). `days` must be consecutive. */
export function Heatmap({ days, onSelect }: { days: AnalyticsPoint[]; onSelect: (s: Selection) => void }) {
  if (days.length === 0) return null;
  const max = Math.max(1, ...days.map((d) => d.count));
  const lead = (parseDay(days[0].date).getDay() + 6) % 7; // blank cells so the first day lands on its weekday row
  return (
    <div>
      <div className="overflow-x-auto pb-1">
        <div className="grid w-max grid-flow-col grid-rows-7 gap-[3px]">
          {Array.from({ length: lead }, (_, i) => (
            <span key={`pad-${i}`} className="size-3" />
          ))}
          {days.map((d) => {
            const level = d.count === 0 ? 0 : Math.max(1, Math.ceil((d.count / max) * LEVELS));
            const label = `${fmtBucket(d.date, "day")}: ${d.count} application${d.count === 1 ? "" : "s"}`;
            return (
              <button
                key={d.date}
                title={label}
                aria-label={label}
                disabled={d.count === 0}
                onClick={() => onSelect({ title: fmtBucket(d.date, "day"), ids: d.ids })}
                className="size-3 rounded-[3px] disabled:cursor-default"
                style={{ background: shade(level) }}
              />
            );
          })}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-end gap-1 text-xs text-muted">
        Less
        {Array.from({ length: LEVELS + 1 }, (_, l) => (
          <span key={l} className="size-3 rounded-[3px]" style={{ background: shade(l) }} />
        ))}
        More
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Layout** — in `AnalyticsTab.tsx` add `import { Heatmap } from "./Heatmap";` and merge `WEEKDAYS` into the existing `./format` import, then insert above the `{/* widgets ... */}` line:

```tsx
      {data && (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <Section title="Activity" hint="Each square is a day; darker means more applications">
            <Heatmap days={data.daily} onSelect={onSelect} />
          </Section>
          <Section title="Day of the week">
            <MixBars
              title="Applied on"
              onSelect={onSelect}
              items={data.weekday.map((w) => ({ key: String(w.day), label: WEEKDAYS[w.day], count: w.count, ids: w.ids }))}
            />
          </Section>
        </div>
      )}
```

- [ ] **Step 3: Typecheck**

Run (from `web/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/src
git commit -m "feat(analytics): activity heatmap and weekday breakdown"
```

---

### Task 10: What works and pipeline health

**Files:**
- Create: `web/src/components/analytics/ConversionTable.tsx`, `Cohorts.tsx`
- Modify: `web/src/components/analytics/AnalyticsTab.tsx`

**Interfaces:**
- Consumes: `Analytics["conversion"]`, `Analytics["cohorts"]`, `MixBars`, `Segmented`, `stageColor`.
- Produces: `ConversionTable({ conversion })`; `Cohorts({ data, dark })`.

- [ ] **Step 1: Conversion table** — create `web/src/components/analytics/ConversionTable.tsx`:

```tsx
import { useState } from "react";
import type { Analytics } from "../../lib/api";
import { SENIORITY_LABEL, categoryLabel, sourceLabel } from "../../lib/stages";
import { cx } from "../ui";
import { pct } from "./format";
import { Segmented } from "./Section";

type Dimension = "source" | "category" | "seniority";
const SMALL_SAMPLE = 5;
const HEADING: Record<Dimension, string> = { source: "Source", category: "Role type", seniority: "Seniority" };
const LABEL: Record<Dimension, (key: string) => string> = {
  source: sourceLabel,
  category: categoryLabel,
  seniority: (k) => SENIORITY_LABEL[k] ?? k,
};

export function ConversionTable({ conversion }: { conversion: Analytics["conversion"] }) {
  const [dimension, setDimension] = useState<Dimension>("source");
  const cell = (rate: number, total: number) => `${pct(rate)} (${Math.round(rate * total)})`;
  return (
    <div>
      <div className="mb-3">
        <Segmented
          value={dimension}
          onChange={setDimension}
          options={(Object.keys(HEADING) as Dimension[]).map((value) => ({ value, label: HEADING[value] }))}
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr className="text-left text-xs text-muted">
              <th className="py-1 pr-3 font-medium">{HEADING[dimension]}</th>
              <th className="px-3 py-1 text-right font-medium">Applied</th>
              <th className="px-3 py-1 text-right font-medium">Responded</th>
              <th className="px-3 py-1 text-right font-medium">Interviewed</th>
              <th className="px-3 py-1 text-right font-medium">Offers</th>
              <th className="py-1 pl-3 text-right font-medium">Median days to reply</th>
            </tr>
          </thead>
          <tbody>
            {conversion[dimension].map((r) => {
              const small = r.total < SMALL_SAMPLE;
              const rate = cx("tabular px-3 py-1.5 text-right", small ? "text-muted" : "text-ink");
              return (
                <tr key={r.key} className="border-t border-line" title={small ? `Small sample: fewer than ${SMALL_SAMPLE} applications` : undefined}>
                  <td className="py-1.5 pr-3 text-ink">
                    {LABEL[dimension](r.key)}
                    {small && <span className="ml-2 text-xs text-muted">small sample</span>}
                  </td>
                  <td className="tabular px-3 py-1.5 text-right text-ink">{r.total}</td>
                  <td className={rate}>{cell(r.responded, r.total)}</td>
                  <td className={rate}>{cell(r.interviewed, r.total)}</td>
                  <td className="tabular px-3 py-1.5 text-right text-ink">{r.offers}</td>
                  <td className="tabular py-1.5 pl-3 text-right text-ink-2">{r.median_days == null ? "—" : r.median_days.toFixed(1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Weekly cohorts** — create `web/src/components/analytics/Cohorts.tsx`:

```tsx
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { Analytics } from "../../lib/api";
import { chartColors, reducedMotion, tooltipStyle } from "./chartTheme";
import { fmtBucket, pct } from "./format";

/** Response rate by the week an application was sent. The newest weeks are dashed: replies may not be in yet. */
export function Cohorts({ data, dark }: { data: Analytics["cohorts"]; dark: boolean }) {
  const option = useMemo(() => {
    const c = chartColors();
    const rate = (i: number) => Math.round(data[i].responded * 1000) / 10;
    let lastMature = -1;
    data.forEach((p, i) => {
      if (!p.maturing) lastMature = i;
    });
    return {
      animation: !reducedMotion(),
      grid: { left: 40, right: 12, top: 12, bottom: 28 },
      tooltip: {
        trigger: "axis",
        ...tooltipStyle(c),
        formatter: (params: { dataIndex: number }[]) => {
          const p = data[params[0].dataIndex];
          const note = p.maturing ? '<br/><span style="opacity:.7">still maturing</span>' : "";
          return `<b>${fmtBucket(p.week, "week")}</b><br/>${pct(p.responded)} responded · ${p.total} applied${note}`;
        },
      },
      xAxis: {
        type: "category",
        data: data.map((p) => fmtBucket(p.week, "day")),
        axisLabel: { color: c.ink2, fontSize: 11, hideOverlap: true },
        axisLine: { lineStyle: { color: c.line } },
        axisTick: { show: false },
      },
      yAxis: { type: "value", min: 0, max: 100, axisLabel: { color: c.ink2, fontSize: 11, formatter: "{value}%" }, splitLine: { lineStyle: { color: c.line } } },
      series: [
        { type: "line", data: data.map((p, i) => (p.maturing ? null : rate(i))), symbolSize: 7, lineStyle: { color: c.accent, width: 2 }, itemStyle: { color: c.accent } },
        {
          type: "line",
          data: data.map((p, i) => (p.maturing || i === lastMature ? rate(i) : null)),
          symbolSize: 7,
          lineStyle: { color: c.accent, width: 2, type: "dashed", opacity: 0.6 },
          itemStyle: { color: c.accent, opacity: 0.6 },
        },
      ],
    };
  }, [data, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  return <ReactECharts option={option} notMerge style={{ height: 220, width: "100%" }} opts={{ renderer: "svg" }} />;
}
```

- [ ] **Step 3: Layout** — in `AnalyticsTab.tsx` add imports (merge `stageColor` into the existing `../../lib/stages` import):

```tsx
import { Cohorts } from "./Cohorts";
import { ConversionTable } from "./ConversionTable";
```

then **replace** the `{/* widgets: keep this line, new sections go above it */}` line (removing the marker) with:

```tsx
      {data && (
        <>
          <Section title="What works" hint="Share of applications that got a reply or an interview, with how many that is">
            <ConversionTable conversion={data.conversion} />
          </Section>
          <div className="grid gap-4 lg:grid-cols-2">
            {data.summary.total >= 7 && (
              <Section title="Response rate by week applied" hint="Dashed weeks may still be waiting for replies">
                <Cohorts data={data.cohorts} dark={dark} />
              </Section>
            )}
            <Section
              title="Time to first reply"
              hint={data.response_time.median == null ? "No replies yet" : `Median ${data.response_time.median.toFixed(1)} days`}
            >
              <MixBars title="Replied in" items={data.response_time.buckets.map((b) => ({ ...b, label: b.key }))} empty="No replies yet" />
            </Section>
            <Section title="Open applications by days since last update" hint="Quiet ones become “ghosted” after the ghost limit">
              <MixBars title="Quiet for" onSelect={onSelect} items={data.open_by_age.map((b) => ({ ...b, label: b.key }))} empty="No open applications" />
            </Section>
            <Section title="Outcomes">
              <MixBars
                title="Outcome"
                onSelect={onSelect}
                items={data.outcomes.map((o) => ({ ...o, label: stageLabel(o.key), color: o.key === "active" ? undefined : stageColor(o.key) }))}
              />
            </Section>
          </div>
        </>
      )}
```

- [ ] **Step 4: Typecheck and build**

Run (from `web/`): `npm run build`
Expected: `tsc` clean and the Vite build succeeds (`src/piper_jobs/static/` is git-ignored).

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(analytics): conversion table, weekly cohorts and pipeline health"
```

---

### Task 11: Verify in the running app

**Files:** none (verification only; fix anything found in the files above, adding a backend test first when the bug is in `analytics.py`).

- [ ] **Step 1: Run on throw-away sample data** (never touch the real `~/.piper`)

PowerShell:

```powershell
$env:PIPER_HOME = "$env:TEMP\piper-analytics-demo"
uv run piper seed --force
uv run piper ui --browser --port 8765
```

Expected: the app opens and **Analytics** is in the sidebar.

- [ ] **Step 2: Walk the acceptance list** (spec §8), in dark and light theme:

1. The summary "Applications" tile equals the Dashboard tile for the same range (filters persist across tabs).
2. Each mix card's counts add up to that total.
3. The Day / Week / Month switch redraws the bars; the 7-day line only appears on Day.
4. Clicking a bar, a mix row, a heatmap square, a weekday row and an open-age row opens the side panel with the matching number of applications.
5. Change one application's role type in the Applications table, return to Analytics: the Role type mix reflects it.
6. Switch the range between 30d and All: nothing shows `NaN`, `Infinity` or a bare percentage; groups under 5 are muted and say "small sample".
7. The theme toggle recolours the charts immediately.
8. Below 768 px wide: one column, no horizontal page scroll (only the heatmap and the table scroll inside their cards).
9. Reloading `?tab=analytics&range=30d` returns to the same view.
10. Empty state: `$env:PIPER_HOME = "$env:TEMP\piper-analytics-empty"; uv run piper ui --browser --port 8766` shows "No applications in this range" and no console errors.

- [ ] **Step 3: Final checks**

Run: `uv run pytest -q` and, from `web/`, `npm run build`
Expected: both succeed.

---

### Task 12: Documentation

**Files:**
- Modify: `docs/PRD.md`, `docs/PRD-analytics.md`, `README.md`

- [ ] **Step 1: Main PRD** — in `docs/PRD.md`:
  - Add after §6.14:

```markdown
### 6.15 Analytics ✅

A tab showing applications per day (with 7-day average, streak and best day), the mix of role types,
sources and seniority, an activity heatmap, and response rates by those same dimensions. It follows the
same filters and saved views. Full requirements: [PRD-analytics.md](PRD-analytics.md).
```

  - In §9 add `GET /api/analytics` to the endpoint list.
  - Delete the Analytics row from the §12 roadmap table.

- [ ] **Step 2: Feature PRD** — in `docs/PRD-analytics.md` set the Status row to `Built` and remove the §10 questions that implementation settled (keep any still open).

- [ ] **Step 3: README** — add one line naming the Analytics tab to the features list, matching its style (`grep -n "Dashboard\|Sankey" README.md` finds the place).

- [ ] **Step 4: Commit**

```bash
git add docs README.md
git commit -m "docs: mark Analytics tab as built"
```

---

## Self-review (spec coverage)

| Spec | Task |
|---|---|
| §6.1 summary tiles | 2 (data), 6 (UI) |
| §6.2 over time, granularity, tooltip, click | 2, 7 |
| §6.3 role type, over time, source, seniority, titles, companies; clickable | 1, 3, 8 |
| §6.4 heatmap, weekday | 3, 9 |
| §6.5 conversion + small sample, cohorts, time to first response | 3, 10 |
| §6.6 open by age, outcomes | 3, 10 |
| §6.7 empty and low-data states | 6 (empty), 7 (average hidden), 10 (cohorts hidden) |
| §6.8 theme, URL, shared colours, layout | 6, 8, 11 |
| §7 backend, endpoint, time zone | 2–4 |
| §8 tests and acceptance | 1–4, 11 |

Known deviations from the spec text, to fold back into `PRD-analytics.md` in Task 12: heatmap is plain CSS rather than an ECharts calendar; chart groups carry `ids` so every row is clickable; `response_time` is `{buckets, median}`; `open_by_age` buckets are `0-7d / 8-14d / 15-21d / 22d+` (anything older is already "ghosted"); "Lead / Manager" is just "Lead" because "Manager" alone is a job, not a level; `previous_total` is computed by re-running the shifted filters on the server.
