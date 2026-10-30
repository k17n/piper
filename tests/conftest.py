from __future__ import annotations

import pytest
from sqlmodel import Session

from piper_jobs.config import Settings
from piper_jobs.db import dispose_engine, get_engine


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(data_dir=tmp_path)
    yield s
    dispose_engine(s.db_path)


@pytest.fixture
def session(settings):
    with Session(get_engine(settings.db_path)) as s:
        yield s


@pytest.fixture
def sample_analytics():
    """A hand-built `compute_analytics` result: 24 applications, a clear LinkedIn-vs-ATS gap."""

    def make(total: int = 24, **over) -> dict:
        g = lambda key, count: {"key": key, "count": count, "ids": []}  # noqa: E731
        data = {
            "range": {"from": "2026-10-01", "to": "2026-10-30"},
            "summary": {
                "total": total, "previous_total": 18, "active_days": 15, "per_active_day": 1.6,
                "daily_average": 0.8, "last_7d_average": 1.1, "streak": 3, "longest_streak": 6,
                "best_day": {"date": "2026-10-12", "count": 4}, "this_week": 5, "last_week": 7,
            },
            "mix": {
                "category": [g("design", 6), g("product", 14), g("vc", 0), g("other", 4)],
                "source": [g("linkedin", 16), g("ats", 8)],
                "seniority": [g("senior", 10), g("unspecified", 14)],
            },
            "conversion": {
                "source": [
                    {"key": "linkedin", "total": 16, "responded": 0.0625, "interviewed": 0.0, "offers": 0, "median_days": None},
                    {"key": "ats", "total": 8, "responded": 0.375, "interviewed": 0.25, "offers": 0, "median_days": 4.0},
                ],
                "category": [
                    {"key": "product", "total": 14, "responded": 0.2143, "interviewed": 0.1429, "offers": 0, "median_days": 5.0},
                    {"key": "design", "total": 4, "responded": 0.5, "interviewed": 0.25, "offers": 0, "median_days": 3.0},
                ],
                "seniority": [],
            },
            "cohorts": [
                {"week": "2026-10-19", "total": 8, "responded": 0.25, "maturing": False},
                {"week": "2026-10-26", "total": 5, "responded": 0.0, "maturing": True},
            ],
            "response_time": {"buckets": [], "median": 4.5},
            "open_by_age": [g("0-7d", 5), g("15-21d", 3), g("22d+", 1)],
        }
        data.update(over)
        return data

    return make
