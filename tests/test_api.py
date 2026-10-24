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
                apply_event(s, company=company, role="Engineer", stage=stage, source=source,
                            occurred_at=now - timedelta(days=days - i))
        s.commit()
    with TestClient(create_app(settings)) as c:
        yield c


def names(resp):
    return sorted(a["company"] for a in resp.json())


@pytest.mark.parametrize("params,expected", [
    ({"range": "30d"}, ["Recent"]),
    ({}, ["Mid", "Recent"]),  # default is 90d
    ({"range": "180d"}, ["Mid", "Older", "Recent"]),
    ({"range": "all"}, ["Ancient", "Mid", "Older", "Recent"]),
])
def test_range_presets(client, params, expected):
    assert names(client.get("/api/applications", params=params)) == expected


def test_custom_range(client):
    today = utcnow().date()
    params = {"range": "custom", "from": str(today - timedelta(days=130)), "to": str(today - timedelta(days=50))}
    assert names(client.get("/api/applications", params=params)) == ["Mid", "Older"]


def test_other_filters(client):
    assert names(client.get("/api/applications", params={"range": "all", "sources": "linkedin"})) == ["Older", "Recent"]
    assert names(client.get("/api/applications", params={"range": "all", "stages": ["accepted", "rejected"]})) == ["Ancient", "Mid"]
    assert names(client.get("/api/applications", params={"range": "all", "q": "anc"})) == ["Ancient"]
    # "Older" (viewed 119 days ago) is ghosted at query time
    assert names(client.get("/api/applications", params={"range": "all", "include_ghosted": "false"})) == ["Ancient", "Mid", "Recent"]


@pytest.mark.parametrize("params", [{"range": "30d"}, {"range": "180d"}, {"range": "all", "sources": "linkedin"}])
def test_totals_consistent_across_endpoints(client, params):
    n = len(client.get("/api/applications", params=params).json())
    assert client.get("/api/stats", params=params).json()["total"] == n
    sankey = client.get("/api/sankey", params=params).json()
    src = {x["name"] for x in sankey["nodes"] if x["kind"] == "source"}
    assert sum(l["value"] for l in sankey["links"] if l["source"] in src) == n


def test_patch_sets_override(client):
    app = client.get("/api/applications", params={"q": "Recent"}).json()[0]
    r = client.patch(f"/api/applications/{app['id']}", json={"stage": "offer", "notes": "call back"})
    assert r.status_code == 200
    assert r.json()["manual_override"] is True and r.json()["stage"] == "offer"
    r = client.patch(f"/api/applications/{app['id']}", json={"manual_override": False})
    assert r.json()["stage"] == "interview" and r.json()["notes"] == "call back"


def test_saved_views_keep_one_default(client):
    a = client.post("/api/views", json={"name": "A", "filters": {"range": "30d"}, "is_default": True}).json()
    b = client.post("/api/views", json={"name": "B", "filters": {"range": "custom", "from": "2026-01-01",
                                                                  "sources": ["ats"]}}).json()
    assert b["filters"]["from"] == "2026-01-01"
    assert client.post("/api/views", json={"name": "A", "filters": {}}).status_code == 409

    client.patch(f"/api/views/{b['id']}", json={"is_default": True})
    views = {v["name"]: v for v in client.get("/api/views").json()}
    assert [n for n, v in views.items() if v["is_default"]] == ["B"]

    client.patch(f"/api/views/{a['id']}", json={"name": "A2", "filters": {"range": "all"}})
    assert client.delete(f"/api/views/{b['id']}").status_code == 204
    views = client.get("/api/views").json()
    assert [(v["name"], v["filters"]["range"], v["is_default"]) for v in views] == [("A2", "all", False)]


def test_meta_and_docs(client):
    assert client.get("/api/meta").json()["data_since"] is not None
    assert client.get("/docs").status_code == 200


def test_email_thread_is_fetched_live(client, settings, monkeypatch):
    from datetime import datetime

    from piper_jobs import gmail_client
    from piper_jobs.db import Email
    from piper_jobs.schema import RawEmail

    with Session(get_engine(settings.db_path)) as s:
        s.add(Email(id="m2", thread_id="t1", from_addr="a@acme.com", subject="Re: hi", received_at=datetime(2026, 9, 2)))
        s.commit()
    monkeypatch.setattr(gmail_client, "get_service", lambda *_a, **_k: object())
    monkeypatch.setattr(gmail_client, "fetch_thread", lambda _s, tid: [
        RawEmail("m1", tid, "Me <me@x.com>", "hi", datetime(2026, 9, 1), "Hello", outgoing=True),
        RawEmail("m2", tid, "A <a@acme.com>", "Re: hi", datetime(2026, 9, 2), "Let's talk"),
    ])
    data = client.get("/api/emails/m2/thread").json()
    assert data["subject"] == "hi"
    assert [(m["id"], m["outgoing"], m["highlight"]) for m in data["messages"]] == [("m1", True, False), ("m2", False, True)]
    assert client.get("/api/emails/nope/thread").status_code == 404


def test_role_type_filter_and_manual_override(client):
    apps = client.get("/api/applications", params={"range": "all"}).json()
    assert {a["category"] for a in apps} == {"other"}  # "Engineer" roles
    target = apps[0]
    r = client.patch(f"/api/applications/{target['id']}", json={"category": "design"})
    assert r.json()["category"] == "design" and r.json()["category_manual"] is True
    assert names(client.get("/api/applications", params={"range": "all", "categories": "design"})) == [target["company"]]
    both = client.get("/api/applications", params={"range": "all", "categories": ["design", "other"]}).json()
    assert len(both) == len(apps)
    r = client.patch(f"/api/applications/{target['id']}", json={"category_auto": True})
    assert r.json()["category"] == "other" and r.json()["category_manual"] is False
    view = client.post("/api/views", json={"name": "Design", "filters": {"range": "all", "categories": ["design"]}}).json()
    assert view["filters"]["categories"] == ["design"]


def test_ui_index_is_never_served_stale(client):
    from piper_jobs.api import STATIC_DIR

    if not (STATIC_DIR / "index.html").is_file():
        pytest.skip("UI not built")
    r = client.get("/")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    asset = next((STATIC_DIR / "assets").glob("*.css")).name
    assert "immutable" in client.get(f"/assets/{asset}").headers["cache-control"]
