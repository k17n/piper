from datetime import timedelta

import pytest
from sqlmodel import select

from piper_jobs.db import InsightSummary, get_engine, utcnow
from piper_jobs.insights import MIN_APPLICATIONS, PROMPT_VERSION, build_facts, facts_hash
from piper_jobs.summaries import (
    DEBOUNCE_SECONDS, MAX_ENTRIES, RETRY_AFTER_SECONDS, SummaryService, delete_cached, get_cached,
    prune_excess, prune_stale, save,
)


def test_save_then_get_returns_text_and_marks_it_used(session):
    save(session, "k", "hello", "qwen", 1)
    row = session.get(InsightSummary, "k")
    row.last_used_at = utcnow() - timedelta(days=3)
    session.add(row)
    session.commit()
    assert get_cached(session, "k") == "hello"
    assert session.get(InsightSummary, "k").last_used_at > utcnow() - timedelta(minutes=1)


def test_get_missing_returns_none(session):
    assert get_cached(session, "nope") is None


def test_saving_again_replaces_the_text(session):
    save(session, "k", "first", "qwen", 1)
    save(session, "k", "second", "qwen", 1)
    assert get_cached(session, "k") == "second"
    assert len(session.exec(select(InsightSummary)).all()) == 1


def test_delete_cached(session):
    save(session, "k", "hello", "qwen", 1)
    delete_cached(session, "k")
    delete_cached(session, "never-saved")  # no error
    assert get_cached(session, "k") is None


def test_prune_excess_keeps_the_most_recently_used(session):
    now = utcnow()
    for i in range(MAX_ENTRIES + 5):
        session.add(InsightSummary(hash=f"k{i}", text="t", model="m", prompt_version=1,
                                   created_at=now, last_used_at=now - timedelta(minutes=i)))
    session.commit()
    prune_excess(session)
    kept = {r.hash for r in session.exec(select(InsightSummary)).all()}
    assert len(kept) == MAX_ENTRIES
    assert "k0" in kept and f"k{MAX_ENTRIES + 4}" not in kept


def test_saving_prunes_beyond_the_limit(session):
    now = utcnow()
    for i in range(MAX_ENTRIES):
        session.add(InsightSummary(hash=f"k{i}", text="t", model="m", prompt_version=1,
                                   created_at=now, last_used_at=now - timedelta(hours=1, minutes=i)))
    session.commit()
    save(session, "fresh", "new", "m", 1)
    assert len(session.exec(select(InsightSummary)).all()) == MAX_ENTRIES
    assert get_cached(session, "fresh") == "new"


def test_prune_stale_removes_other_models_and_prompt_versions(session):
    save(session, "keep", "t", "qwen", 2)
    save(session, "old-model", "t", "llama", 2)
    save(session, "old-prompt", "t", "qwen", 1)
    prune_stale(session, "qwen", 2)
    assert {r.hash for r in session.exec(select(InsightSummary)).all()} == {"keep"}


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Recorder:
    """A fake model: records calls, replies with a grounded sentence unless told otherwise."""

    def __init__(self, reply="You sent 24 applications.", error=None):
        self.reply, self.error, self.temperatures = reply, error, []

    def __call__(self, messages, temperature):
        self.temperatures.append(temperature)
        if self.error:
            raise self.error
        return self.reply

    @property
    def calls(self):
        return len(self.temperatures)


@pytest.fixture
def make_service(settings):
    def make(model, syncing=lambda: False):
        clock = Clock()
        svc = SummaryService(settings, get_engine(settings.db_path), is_syncing=syncing, generate=model,
                             spawn=lambda fn: fn(), clock=clock)
        return svc, clock

    return make


def test_too_few_applications_calls_no_model(make_service, sample_analytics):
    model = Recorder()
    svc, clock = make_service(model)
    result = svc.status(sample_analytics(total=MIN_APPLICATIONS - 1))
    clock.now += 60
    svc.status(sample_analytics(total=MIN_APPLICATIONS - 1))
    assert result["status"] == "insufficient_data" and result["text"] is None
    assert model.calls == 0


def test_waits_for_the_quiet_period_then_generates(make_service, sample_analytics):
    model = Recorder()
    svc, clock = make_service(model)
    a = sample_analytics()
    first = svc.status(a)
    assert first["status"] == "pending" and first["facts"] == build_facts(a)
    clock.now += DEBOUNCE_SECONDS - 1
    assert svc.status(a)["status"] == "pending" and model.calls == 0
    clock.now += 2
    assert svc.status(a)["status"] == "pending" and model.calls == 1  # started now
    done = svc.status(a)
    assert done["status"] == "ready" and done["text"] == "You sent 24 applications."
    assert model.calls == 1


def test_a_cached_summary_calls_no_model(make_service, sample_analytics, session, settings):
    a = sample_analytics()
    save(session, facts_hash(build_facts(a), settings.ollama_model), "Cached text.", settings.ollama_model, PROMPT_VERSION)
    model = Recorder()
    svc, _ = make_service(model)
    assert svc.status(a) == {"status": "ready", "text": "Cached text.", "facts": build_facts(a)}
    assert model.calls == 0


def test_nothing_is_generated_during_a_sync(make_service, sample_analytics):
    model, syncing = Recorder(), [True]
    svc, clock = make_service(model, syncing=lambda: syncing[0])
    a = sample_analytics()
    svc.status(a)
    clock.now += 60
    assert svc.status(a)["status"] == "pending" and model.calls == 0
    syncing[0] = False
    svc.status(a)
    assert model.calls == 1  # no new quiet period once the sync is over


def test_a_reply_with_unknown_numbers_is_not_used(make_service, sample_analytics):
    model = Recorder(reply="You sent 99 applications.")
    svc, clock = make_service(model)
    a = sample_analytics()
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS
    svc.status(a)  # generates; the reply fails the check
    result = svc.status(a)
    assert result["status"] == "fallback" and result["text"] is None and result["facts"] == build_facts(a)
    svc.status(a)
    assert model.calls == 1  # not retried straight away
    clock.now += RETRY_AFTER_SECONDS + 1
    assert svc.status(a)["status"] == "pending"  # allowed to try again, after a new quiet period


def test_a_model_error_falls_back(make_service, sample_analytics):
    svc, clock = make_service(Recorder(error=ConnectionError("ollama is not running")))
    a = sample_analytics()
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS
    svc.status(a)
    assert svc.status(a)["status"] == "fallback"


def test_changed_facts_get_their_own_summary(make_service, sample_analytics):
    model = Recorder(reply="You sent 24 applications.")
    svc, clock = make_service(model)
    a, b = sample_analytics(), sample_analytics()
    b["summary"]["this_week"] = 9
    for data in (a, b):
        svc.status(data)
        clock.now += DEBOUNCE_SECONDS
        svc.status(data)
        assert svc.status(data)["status"] == "ready"
    assert model.calls == 2


def test_refresh_asks_again_with_different_wording(make_service, sample_analytics, session, settings):
    a = sample_analytics()
    save(session, facts_hash(build_facts(a), settings.ollama_model), "Old text.", settings.ollama_model, PROMPT_VERSION)
    model = Recorder(reply="You sent 24 jobs.")
    svc, _ = make_service(model)
    svc.refresh(a)  # no quiet period
    assert model.temperatures == [0.6]
    assert svc.status(a) == {"status": "ready", "text": "You sent 24 jobs.", "facts": build_facts(a)}
