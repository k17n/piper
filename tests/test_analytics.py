from __future__ import annotations

from datetime import date, datetime, timedelta

from piper_jobs.analytics import compute_analytics, previous_filters
from piper_jobs.db import Application, Event
from piper_jobs.filters import AppRow, Filters
from piper_jobs.stats import compute_stats

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
