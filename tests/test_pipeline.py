"""Sync pipeline against a fake Gmail and a fake model: conversations, follow-ups, review, re-scan."""

from datetime import datetime

import pytest
from sqlmodel import Session, select

from jobtracker import gmail_client
from jobtracker.db import Application, Email, Event, ReviewItem, get_engine, get_state
from jobtracker.gmail_client import ThreadInfo, strip_quoted
from jobtracker.pipeline import sync
from jobtracker.schema import JobEvent, RawEmail

ME = "Alex <alex@example.com>"


def mail(id, from_addr, subject, day, body="", **kw) -> RawEmail:
    return RawEmail(id, kw.pop("thread", None), from_addr, subject, datetime(2026, 9, day), body, **kw)


class FakeGmail:
    """Stands in for the gmail_client functions the pipeline calls."""

    def __init__(self, emails, threads=(), by_query=None):
        self.emails = {e.id: e for e in emails}
        self.threads = list(threads)
        self.by_query = by_query or {}  # substring of query → ids
        self.queries: list[str] = []

    def list_message_ids(self, _service, query):
        self.queries.append(query)
        for key, ids in self.by_query.items():
            if key in query:
                return list(ids)
        return []

    def install(self, monkeypatch):
        monkeypatch.setattr(gmail_client, "list_message_ids", self.list_message_ids)
        monkeypatch.setattr(gmail_client, "list_sent_threads", lambda _s, _settings: self.threads)
        monkeypatch.setattr(gmail_client, "fetch_email", lambda _s, mid: self.emails[mid])
        monkeypatch.setattr(gmail_client, "my_address", lambda _s: "alex@example.com")


class FakeModel:
    name = "fake"

    def __init__(self, answers):
        self.answers = answers  # email id → JobEvent
        self.calls: list[str] = []
        self.contexts: dict[str, str] = {}

    def extract(self, email):
        self.calls.append(email.id)
        self.contexts[email.id] = email.context
        return self.answers[email.id]


def ev(company=None, stage=None, conf=0.9, job=True, role=None, source="direct"):
    return JobEvent(is_job_related=job, company=company, role=role, stage=stage,
                    source=source if job else None, confidence=conf)


@pytest.fixture
def northstar(monkeypatch):
    """You emailed Northstar, they replied, you replied; later a calendar invite from their domain."""
    emails = [
        mail("m1", ME, "Product designer for Northstar", 1, "Hi Sam, would love to help design...",
             to_addr="sam@northstar.bio", outgoing=True, thread="t1"),
        mail("m2", "Sam <sam@northstar.bio>", "Re: Product designer for Northstar", 2,
             "Sounds great, let's do a call.\n\nOn Tue, Sep 1, 2026 Alex wrote:\n> Hi Sam", thread="t1"),
        mail("m3", ME, "Re: Product designer for Northstar", 3, "Thursday works", outgoing=True, thread="t1"),
        mail("inv", "Jordan <jordan@northstar.bio>", "Invitation: Alex / Chris @ Thu", 5, "Join with Google Meet"),
        mail("promo", "Shop <deals@shop.com>", "Interview outfits 40% off", 6, "Sale!", promotional=True, bulk=True),
    ]
    thread = ThreadInfo("t1", ["m1", "m2", "m3"], {"m1", "m3"},
                        {"m1": datetime(2026, 9, 1), "m2": datetime(2026, 9, 2), "m3": datetime(2026, 9, 3)})
    fake = FakeGmail(emails, [thread], {"from:(northstar.bio)": ["inv"], "newer_than": ["promo"]})
    fake.install(monkeypatch)
    model = FakeModel({
        "m1": ev("Northstar", "applied", role="Product Designer"),
        "m2": ev("Northstar", "interview"),
        "inv": ev("Northstar", "interview", conf=0.8),
    })
    return fake, model


def test_conversation_outreach_and_follow_up(settings, northstar):
    fake, model = northstar
    result = sync(settings, service=object(), extractor=model)

    # promo never reaches the model; your later reply is stored without analysis
    assert sorted(model.calls) == ["inv", "m1", "m2"]
    assert result["followed"] == 1 and result["domains"] == 1
    # the invite is read knowing you're in a hiring process with Northstar
    assert model.contexts["inv"] == "The candidate is already in a hiring process with Northstar (northstar.bio)."
    assert model.contexts["m1"] == ""

    with Session(get_engine(settings.db_path)) as s:
        apps = s.exec(select(Application)).all()
        assert [(a.company_display, a.current_stage, a.source) for a in apps] == [("Northstar", "interview", "direct")]
        stages = sorted(e.stage for e in s.exec(select(Event)).all())
        assert stages == ["applied", "interview", "interview"]
        statuses = {e.id: e.llm_status for e in s.exec(select(Email)).all()}
        assert statuses == {"m1": "ok", "m2": "ok", "m3": "outgoing", "inv": "ok", "promo": "skipped"}
        assert get_state(s, "gmail_address") == "alex@example.com"


def test_second_sync_makes_no_model_calls(settings, northstar):
    fake, model = northstar
    sync(settings, service=object(), extractor=model)
    model.calls.clear()
    sync(settings, service=object(), extractor=model)
    assert model.calls == []
    assert "after:" in fake.queries[-2]  # incremental main search


def test_outreach_is_always_applied(settings, monkeypatch):
    out = mail("o1", ME, "Hello", 1, "Keen to join your design team", to_addr="maya@lumen.ai", outgoing=True)
    FakeGmail([out], [ThreadInfo("t", ["o1"], {"o1"}, {"o1": datetime(2026, 9, 1)})]).install(monkeypatch)
    sync(settings, service=object(), extractor=FakeModel({"o1": ev("Lumen", "interview")}))
    with Session(get_engine(settings.db_path)) as s:
        assert s.exec(select(Event.stage)).all() == ["applied"]


def test_unsure_goes_to_review_with_readable_text_but_bulk_does_not(settings, monkeypatch):
    emails = [
        mail("p", "Neha <neha@studio.in>", "quick question", 1, "Are you open to a freelance design role?"),
        mail("b", "News <news@studio.in>", "Our design newsletter", 2, "Read more", bulk=True),
        mail("l", "Ravi <ravi@acme.com>", "Application", 3, "Thanks for applying"),
    ]
    FakeGmail(emails, by_query={"newer_than": ["p", "b", "l"]}).install(monkeypatch)
    settings.follow_company_domains = False
    model = FakeModel({
        "p": ev(job=False, conf=0.4),  # unsure, from a person → review
        "b": ev(job=False, conf=0.4),  # unsure, but bulk mail → silently not a job
        "l": ev("Acme", "applied", conf=0.3),  # job, low confidence → review
    })
    sync(settings, service=object(), extractor=model)
    with Session(get_engine(settings.db_path)) as s:
        items = {i.email_id: i for i in s.exec(select(ReviewItem)).all()}
        assert set(items) == {"p", "l"}
        assert items["p"].reason == "Not sure if this is about a job"
        assert "freelance design role" in items["p"].excerpt


def test_filter_change_rescans_skipped(settings, monkeypatch):
    junk = mail("j", "Jobs <jobalerts-noreply@linkedin.com>", "New jobs for you", 1)
    fake = FakeGmail([junk], by_query={"newer_than": ["j"], "after:": ["j"]})
    fake.install(monkeypatch)
    settings.include_sent_threads = settings.follow_company_domains = False
    sync(settings, service=object(), extractor=FakeModel({}))

    settings.always_include = ["linkedin.com"]  # user changes filters
    model = FakeModel({"j": ev(job=False, conf=0.9)})
    sync(settings, service=object(), extractor=model)
    assert model.calls == ["j"]  # the skipped email was re-checked
    assert "newer_than" in fake.queries[-1]  # full window, not incremental


def test_strip_quoted_reply():
    body = "Sounds great.\n\nOn Tue, Sep 1, 2026 at 3:12 PM Alex R <k@example.com>\nwrote:\n> old text"
    assert strip_quoted(body) == "Sounds great."
    assert strip_quoted("> only quoted\nnew line") == "new line"


def test_not_job_from_known_company_is_rechecked_after_upgrade(settings, northstar, monkeypatch):
    fake, model = northstar
    model.answers["inv"] = ev(job=False, conf=0.9)  # an older prompt got the invite wrong
    sync(settings, service=object(), extractor=model)

    monkeypatch.setattr("jobtracker.pipeline.PROMPT_VERSION", 999)  # prompt improved
    model.answers["inv"] = ev("Northstar", "interview", conf=0.85)
    model.calls.clear()
    sync(settings, service=object(), extractor=model)
    assert model.calls == ["inv"]
    with Session(get_engine(settings.db_path)) as s:
        assert s.get(Email, "inv").llm_status == "ok"
