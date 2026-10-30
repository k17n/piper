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
