import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from piper_jobs.api import create_app
from piper_jobs.db import InsightSummary, get_engine, utcnow
from piper_jobs.insights import PROMPT_VERSION
from piper_jobs.resolver import apply_event


# Letters, not numbers: the resolver folds "Company10"/"Company11" into "Company0"/"Company1".
LETTERS = "ABCDEFGHIJKL"


@pytest.fixture
def client(settings):
    now = utcnow()
    with Session(get_engine(settings.db_path)) as s:
        for i in range(12):
            apply_event(s, company=f"Company{LETTERS[i]}", role="Product Designer", stage="applied",
                        source="linkedin", occurred_at=now - timedelta(days=i + 1))
        s.commit()
    with TestClient(create_app(settings)) as c:
        temperatures = []

        def generate(messages, temperature):
            temperatures.append(temperature)
            total = re.search(r"Applications over .*?: (\d+)", messages[-1]["content"]).group(1)
            return f"You sent {total} applications."

        svc = c.app.state.summaries
        svc.generate, svc.spawn, svc.debounce = generate, (lambda fn: fn()), 0
        c.temperatures = temperatures
        yield c


def test_summary_is_generated_once_then_served_from_the_cache(client):
    params = {"range": "all"}
    first = client.get("/api/analytics/summary", params=params).json()
    assert first["status"] == "pending" and first["facts"]
    ready = client.get("/api/analytics/summary", params=params).json()
    assert ready["status"] == "ready" and ready["text"] == "You sent 12 applications."
    client.get("/api/analytics/summary", params=params)
    assert client.temperatures == [0.0]


def test_too_few_applications_in_the_view(client):
    data = client.get("/api/analytics/summary", params={"range": "all", "q": "CompanyA"}).json()
    assert data["status"] == "insufficient_data"  # only CompanyA matches
    assert client.temperatures == []


def test_refresh_writes_it_again_with_different_wording(client):
    params = {"range": "all"}
    client.get("/api/analytics/summary", params=params)
    client.get("/api/analytics/summary", params=params)
    client.post("/api/analytics/summary/refresh", params=params)
    assert client.temperatures == [0.0, 0.6]
    assert client.get("/api/analytics/summary", params=params).json()["status"] == "ready"


def test_invalid_tz_offset_is_rejected(client):
    assert client.get("/api/analytics/summary", params={"tz_offset": 99999}).status_code == 422


def test_startup_removes_summaries_of_other_models(settings):
    with Session(get_engine(settings.db_path)) as s:
        s.add(InsightSummary(hash="old", text="t", model="some-other-model", prompt_version=PROMPT_VERSION))
        s.add(InsightSummary(hash="new", text="t", model=settings.ollama_model, prompt_version=PROMPT_VERSION))
        s.commit()
    with TestClient(create_app(settings)):
        pass
    with Session(get_engine(settings.db_path)) as s:
        assert s.get(InsightSummary, "old") is None
        assert s.get(InsightSummary, "new") is not None
