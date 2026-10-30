"""The written summary: a small cache of model replies, and the service that decides when to ask the model."""

from __future__ import annotations

from sqlmodel import Session, select

from .db import InsightSummary, utcnow

MAX_ENTRIES = 50


def get_cached(session: Session, key: str) -> str | None:
    row = session.get(InsightSummary, key)
    if row is None:
        return None
    row.last_used_at = utcnow()
    session.add(row)
    session.commit()
    return row.text


def save(session: Session, key: str, text: str, model: str, prompt_version: int) -> None:
    now = utcnow()
    row = session.get(InsightSummary, key)
    if row:
        row.text, row.model, row.prompt_version, row.last_used_at = text, model, prompt_version, now
        session.add(row)
    else:
        session.add(InsightSummary(hash=key, text=text, model=model, prompt_version=prompt_version,
                                   created_at=now, last_used_at=now))
    session.commit()
    prune_excess(session)


def delete_cached(session: Session, key: str) -> None:
    row = session.get(InsightSummary, key)
    if row:
        session.delete(row)
        session.commit()


def prune_excess(session: Session, keep: int = MAX_ENTRIES) -> None:
    """Keep the most recently used entries."""
    rows = session.exec(select(InsightSummary).order_by(InsightSummary.last_used_at.desc())).all()
    for row in rows[keep:]:
        session.delete(row)
    session.commit()


def prune_stale(session: Session, model: str, prompt_version: int) -> None:
    """Drop summaries written by another model or an older prompt."""
    rows = session.exec(
        select(InsightSummary).where((InsightSummary.model != model) | (InsightSummary.prompt_version != prompt_version))
    ).all()
    for row in rows:
        session.delete(row)
    session.commit()
