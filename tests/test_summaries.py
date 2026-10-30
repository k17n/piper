from datetime import timedelta

from sqlmodel import select

from piper_jobs.db import InsightSummary, utcnow
from piper_jobs.summaries import (
    MAX_ENTRIES, delete_cached, get_cached, prune_excess, prune_stale, save,
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
