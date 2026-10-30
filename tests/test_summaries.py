from datetime import timedelta

import pytest
from sqlmodel import select

from piper_jobs.db import InsightSummary, get_engine, utcnow
from piper_jobs.insights import MIN_APPLICATIONS, PROMPT_VERSION, build_facts, facts_hash
from piper_jobs.summaries import (
    DEBOUNCE_SECONDS, GENERATE_TIMEOUT_SECONDS, MAX_ENTRIES, RETRY_AFTER_SECONDS, SummaryService, delete_cached,
    get_cached, ollama_generate, prune_excess, prune_stale, save,
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
    for i in reversed(range(MAX_ENTRIES + 5)):  # inserted oldest first, so only the ordering can save k0
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

    def __init__(self, reply="You sent 24 applications.", error=None, replies=None):
        self.reply, self.error, self.temperatures = reply, error, []
        self.replies, self.messages = list(replies or []), []  # replies: used in order, then `reply`

    def __call__(self, messages, temperature):
        self.temperatures.append(temperature)
        self.messages.append(messages)
        if self.error:
            raise self.error
        return self.replies.pop(0) if self.replies else self.reply

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
    assert model.calls == 2  # the first reply and one retry; not tried again straight away
    clock.now += RETRY_AFTER_SECONDS + 1
    assert svc.status(a)["status"] == "pending"  # allowed to try again, after a new quiet period


def _generate_once(svc, clock, a):
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS
    svc.status(a)  # generates
    return svc.status(a)


def test_an_ungrounded_reply_is_retried_once_with_the_offending_numbers(make_service, sample_analytics):
    model = Recorder(replies=["You sent 99 and 77 applications.", "You sent 24 applications."])
    svc, clock = make_service(model)
    a = sample_analytics()
    result = _generate_once(svc, clock, a)
    assert result["status"] == "ready" and result["text"] == "You sent 24 applications."
    assert model.calls == 2
    first, second = model.messages
    assert second[:len(first)] == first
    assert second[-2] == {"role": "assistant", "content": "You sent 99 and 77 applications."}
    assert second[-1] == {"role": "user", "content": (
        "That used numbers that are not in the facts: 77, 99. "
        "Write it again using only numbers copied exactly from the facts.")}


def test_two_ungrounded_replies_fall_back_and_are_not_retried_again(make_service, sample_analytics):
    model = Recorder(replies=["You sent 99.", "You sent 98."])
    svc, clock = make_service(model)
    a = sample_analytics()
    assert _generate_once(svc, clock, a)["status"] == "fallback"
    assert model.calls == 2
    clock.now += RETRY_AFTER_SECONDS - 1
    assert svc.status(a)["status"] == "fallback"
    assert model.calls == 2


def test_a_grounded_first_reply_is_not_retried(make_service, sample_analytics):
    model = Recorder()
    svc, clock = make_service(model)
    assert _generate_once(svc, clock, sample_analytics())["status"] == "ready"
    assert model.calls == 1


def test_a_model_error_is_not_retried(make_service, sample_analytics):
    model = Recorder(error=ConnectionError("down"))
    svc, clock = make_service(model)
    assert _generate_once(svc, clock, sample_analytics())["status"] == "fallback"
    assert model.calls == 1


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


def _recording_service(settings, model, clock=None):
    clock = clock or Clock()
    spawned = []
    svc = SummaryService(settings, get_engine(settings.db_path), is_syncing=lambda: False, generate=model,
                         spawn=spawned.append, clock=clock)
    return svc, clock, spawned


def test_a_spawn_failure_falls_back_and_can_be_retried(settings, sample_analytics):
    model = Recorder()
    clock = Clock()
    attempts = []

    def flaky(fn):
        attempts.append(fn)
        if len(attempts) == 1:
            raise RuntimeError("can't start new thread")
        fn()

    svc = SummaryService(settings, get_engine(settings.db_path), is_syncing=lambda: False, generate=model,
                         spawn=flaky, clock=clock)
    a = sample_analytics()
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS
    result = svc.status(a)
    assert result["status"] == "fallback" and result["text"] is None and result["facts"] == build_facts(a)
    clock.now += RETRY_AFTER_SECONDS + 1
    assert svc.status(a)["status"] == "pending"  # a fresh quiet period starts...
    assert len(attempts) == 1 and model.calls == 0  # ...and nothing runs yet
    clock.now += DEBOUNCE_SECONDS - 1
    assert svc.status(a)["status"] == "pending" and len(attempts) == 1
    clock.now += 1
    svc.status(a)  # the quiet period is over: the run starts
    assert len(attempts) == 2 and model.calls == 1
    assert svc.status(a)["status"] == "ready"


def test_ollama_client_gets_a_timeout(monkeypatch, settings):
    import ollama

    captured = {}

    class FakeClient:
        def __init__(self, host=None, **kwargs):
            captured.update(kwargs)

        def chat(self, **kwargs):
            class Reply:
                class message:
                    content = "hi"

            return Reply

    monkeypatch.setattr(ollama, "Client", FakeClient)
    assert ollama_generate(settings)([], 0.0) == "hi"
    assert captured["timeout"] == GENERATE_TIMEOUT_SECONDS == 120


def test_refresh_during_a_run_still_regenerates_with_new_wording(settings, sample_analytics):
    model = Recorder()
    svc, clock, spawned = _recording_service(settings, model)
    a = sample_analytics()
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS
    svc.status(a)  # run #1 recorded, not executed
    assert len(spawned) == 1
    svc.refresh(a)
    assert len(spawned) == 1  # still only one at a time
    spawned[0]()
    assert model.temperatures == [0.0]
    svc.status(a)  # the refresh asked for a new generation
    assert len(spawned) == 2
    model.reply = "You sent 24 jobs."
    spawned[1]()
    assert model.temperatures == [0.0, 0.6]
    assert svc.status(a) == {"status": "ready", "text": "You sent 24 jobs.", "facts": build_facts(a)}


def test_generation_starts_exactly_at_the_quiet_period(settings, sample_analytics):
    svc, clock, spawned = _recording_service(settings, Recorder())
    a = sample_analytics()
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS - 1
    svc.status(a)
    assert spawned == []
    clock.now += 1
    svc.status(a)
    assert len(spawned) == 1


def test_retry_window_boundaries(make_service, sample_analytics):
    model = Recorder(error=ConnectionError("down"))
    svc, clock = make_service(model)
    a = sample_analytics()
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS
    svc.status(a)  # fails at this moment
    clock.now += RETRY_AFTER_SECONDS - 1
    assert svc.status(a)["status"] == "fallback"
    clock.now += 2
    assert svc.status(a)["status"] == "pending"


def test_only_one_generation_at_a_time(settings, sample_analytics):
    svc, clock, spawned = _recording_service(settings, Recorder())
    a = sample_analytics()
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS
    svc.status(a)
    svc.status(a)
    clock.now += 60
    svc.status(a)
    assert len(spawned) == 1
