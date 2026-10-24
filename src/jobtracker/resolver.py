"""Entity resolution: normalize names and attach events to the right application."""

from __future__ import annotations

import re
from datetime import datetime

from rapidfuzz import fuzz
from sqlmodel import Session, select

from .categories import classify
from .db import Application, Email, Event
from .stages import compute_current_stage

COMPANY_MATCH = 90
ROLE_MATCH = 80

_SUFFIXES = {
    "inc", "incorporated", "llc", "ltd", "limited", "pvt", "private", "plc", "gmbh",
    "corp", "corporation", "co", "company", "technologies", "technology", "labs", "group",
}
_VIA = re.compile(r"\s+via\s+\S+.*$", re.I)


def clean_company_display(name: str) -> str:
    return _VIA.sub("", name).strip(" ,.-")


def normalize_company(name: str | None) -> str:
    if not name:
        return ""
    text = clean_company_display(name).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t for t in text.split() if t not in _SUFFIXES]
    return " ".join(tokens)


def normalize_role(role: str | None) -> str:
    if not role:
        return ""
    text = re.sub(r"[^\w\s]", " ", role.lower())
    return " ".join(text.split())


_SENIORITY = {"intern", "junior", "jr", "senior", "sr", "staff", "principal", "lead", "head",
               "i", "ii", "iii", "iv", "1", "2", "3", "4"}


def role_similarity(a: str, b: str) -> float:
    """token_sort (not token_set: a subset must not score 100); differing seniority never matches."""
    if set(a.split()) & _SENIORITY != set(b.split()) & _SENIORITY:
        return 0.0
    return fuzz.token_sort_ratio(a, b)


def _compact(name: str) -> str:
    return re.sub(r"[\W_]", "", clean_company_display(name).lower())


def company_similarity(company: str, company_norm: str, app: Application) -> float:
    """Token match on normalized names, or an exact match ignoring spaces ("OrbitLabs" = "Orbit Labs")."""
    if _compact(company) == _compact(app.company_display):
        return 100.0
    return fuzz.token_set_ratio(company_norm, app.company_norm)


def find_match(session: Session, company: str, role: str | None) -> Application | None:
    company_norm = normalize_company(company)
    role_norm = normalize_role(role)
    if not company_norm:
        return None
    candidates = [
        app
        for app in session.exec(select(Application)).all()
        if company_similarity(company, company_norm, app) >= COMPANY_MATCH
    ]
    if not candidates:
        return None
    if not role_norm:
        return max(candidates, key=lambda a: a.last_event_at)

    best: tuple[float, Application] | None = None
    for app in candidates:
        score = 100.0 if not app.role_norm else role_similarity(role_norm, app.role_norm)
        if score >= ROLE_MATCH and (best is None or score > best[0]):
            best = (score, app)
    return best[1] if best else None


def apply_event(
    session: Session,
    *,
    company: str,
    role: str | None,
    stage: str,
    source: str | None,
    occurred_at: datetime,
    email_id: str | None = None,
    confidence: float = 1.0,
) -> Application:
    app = find_match(session, company, role)
    if app is None:
        app = Application(
            company_norm=normalize_company(company),
            company_display=clean_company_display(company),
            role_norm=normalize_role(role),
            role_display=role or "",
            source=source or "other",
            first_seen=occurred_at,
            last_event_at=occurred_at,
            current_stage=stage,
        )
        session.add(app)
        session.flush()
    else:
        if role and not app.role_norm:
            app.role_norm, app.role_display = normalize_role(role), role
        app.first_seen = min(app.first_seen, occurred_at)
        app.last_event_at = max(app.last_event_at, occurred_at)

    session.add(
        Event(
            email_id=email_id,
            application_id=app.id,
            stage=stage,
            occurred_at=occurred_at,
            confidence=confidence,
            source=source,
        )
    )
    session.flush()
    if not app.manual_override:
        recompute_stage(session, app)
    recompute_category(session, app)
    return app


def recompute_stage(session: Session, app: Application) -> None:
    events = session.exec(select(Event).where(Event.application_id == app.id)).all()
    app.current_stage = compute_current_stage((e.stage, e.occurred_at) for e in events)


def recompute_category(session: Session, app: Application) -> None:
    """Role type from the role, then the subjects of its emails, then the company. Yours wins."""
    if app.category_manual:
        return
    rows = session.exec(
        select(Email.subject, Email.from_addr, Email.to_addr)
        .join(Event, Event.email_id == Email.id)
        .where(Event.application_id == app.id)
    ).all()
    domains = [addr.rsplit("@", 1)[-1].strip("> ").lower() for _s, f, t in rows for addr in (f, t) if "@" in addr]
    app.category = classify(app.role_display, app.company_display, [s for s, _f, _t in rows], domains)
    session.add(app)


def recompute_all_categories(session: Session) -> None:
    for app in session.exec(select(Application).where(Application.category_manual == False)).all():  # noqa: E712
        recompute_category(session, app)
    session.commit()
