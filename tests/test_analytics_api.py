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
