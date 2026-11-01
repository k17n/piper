"""Entity resolution: normalize names and attach events to the right application."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from email.utils import parseaddr

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


CLOSED_STAGES = {"rejected", "withdrawn", "accepted"}
# A role-less confirmation joins an application only if that application started this close in time
# (e.g. LinkedIn's "application sent" and the company's own "thanks for applying" for the same role).
SAME_APPLICATION_WINDOW = timedelta(days=3)


def company_applications(session: Session, company: str) -> list[Application]:
    company_norm = normalize_company(company)
    if not company_norm:
        return []
    return [
        app
        for app in session.exec(select(Application)).all()
        if company_similarity(company, company_norm, app) >= COMPANY_MATCH
    ]


def _domain(addr: str) -> str:
    email = parseaddr(addr)[1].lower()
    return email.rsplit("@", 1)[1] if "@" in email else ""


def _confirmation_senders(session: Session, app: Application) -> set[str]:
    """Sender domains of the 'applied' emails already attached to this application."""
    rows = session.exec(
        select(Email.from_addr)
        .join(Event, Event.email_id == Email.id)
        .where(Event.application_id == app.id, Event.stage == "applied")
    ).all()
    return {_domain(f) for f in rows}


def ambiguous_applications(session: Session, company: str, role: str | None, stage: str) -> list[Application]:
    """Open applications an update could belong to when it names no role. More than one means we
    can't tell which (identical templates for several roles), so the user should choose."""
    if normalize_role(role) or stage == "applied":
        return []
    open_apps = [a for a in company_applications(session, company) if a.current_stage not in CLOSED_STAGES]
    return open_apps if len(open_apps) > 1 else []


def find_match(
    session: Session,
    company: str,
    role: str | None,
    *,
    stage: str | None = None,
    sender: str | None = None,
    occurred_at: datetime | None = None,
) -> Application | None:
    candidates = company_applications(session, company)
    if not candidates:
        return None
    role_norm = normalize_role(role)
    if not role_norm:
        if stage == "applied" and sender and occurred_at:
            # One confirmation per application: identical "thanks for applying" emails from the same
            # sender are separate applications, so an application takes at most one of them.
            domain = _domain(sender)
            free = [a for a in candidates if domain not in _confirmation_senders(session, a)]
            near = [a for a in free if abs(a.first_seen - occurred_at) <= SAME_APPLICATION_WINDOW]
            return min(near, key=lambda a: abs(a.first_seen - occurred_at)) if near else None
        open_apps = [a for a in candidates if a.current_stage not in CLOSED_STAGES]
        return max(open_apps or candidates, key=lambda a: a.last_event_at)

    best: tuple[float, Application] | None = None
    for app in candidates:
        score = 100.0 if not app.role_norm else role_similarity(role_norm, app.role_norm)
        if score >= ROLE_MATCH and (best is None or score > best[0]):
            best = (score, app)
    if best:
        return best[1]
    if stage and stage != "applied":
        # A status update (rejection, interview...) is about an application we already know. Companies
        # often append a team or program to the title ("Senior Product Designer, New Verticals"), so
        # accept the single open application whose role is a subset/superset of this one.
        related = [
            a for a in candidates
            if a.current_stage not in CLOSED_STAGES and a.role_norm
            and fuzz.token_set_ratio(role_norm, a.role_norm) == 100
            and set(role_norm.split()) & _SENIORITY == set(a.role_norm.split()) & _SENIORITY
        ]
        if len(related) == 1:
            return related[0]
    return None


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
    application_id: int | None = None,
    note: str = "",
) -> Application:
    """Attach an event to its application (or a new one). `application_id` forces the target,
    e.g. when the user picked it in the review queue."""
    sender = session.get(Email, email_id).from_addr if email_id and session.get(Email, email_id) else None
    if application_id is not None:
        app = session.get(Application, application_id)
    else:
        app = find_match(session, company, role, stage=stage, sender=sender, occurred_at=occurred_at)
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
            note=note,
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


_VIEWED = re.compile(r"\b(viewed|seen|looked at|opened)\b", re.I)


def mentions_viewed(text: str) -> bool:
    """Does the email say the employer looked at the application? Only then is it a `viewed` stage."""
    return bool(_VIEWED.search(text))


def fix_unfounded_viewed(session: Session) -> int:
    """One-time repair: the model sometimes labelled "we received your application" as `viewed`,
    which put a Viewed step in the sankey. Relabel such events (judged by the stored snippet) as applied."""
    fixed, touched = 0, {}
    rows = session.exec(
        select(Event, Email).join(Email, Email.id == Event.email_id).where(Event.stage == "viewed")
    ).all()
    for event, email in rows:
        if mentions_viewed(f"{email.subject}\n{email.snippet}"):
            continue
        event.stage = "applied"
        session.add(event)
        touched[event.application_id] = True
        fixed += 1
    session.flush()
    for app_id in touched:
        app = session.get(Application, app_id)
        if app and not app.manual_override:
            recompute_stage(session, app)
            session.add(app)
    session.commit()
    return fixed


def merge_orphan_updates(session: Session) -> int:
    """One-time repair: before status updates could match a longer role title, a rejection or
    interview naming "Senior Designer, New Verticals" became its own application next to the
    "Senior Designer" one it belongs to. Fold such update-only applications into that application."""
    merged = 0
    for orphan in session.exec(select(Application).where(Application.role_norm != "")).all():
        if orphan.manual_override or orphan.notes or orphan.job_url:
            continue
        events = session.exec(select(Event).where(Event.application_id == orphan.id)).all()
        if not events or any(e.stage == "applied" for e in events):
            continue
        first = min(e.occurred_at for e in events)
        targets = [
            a for a in company_applications(session, orphan.company_display)
            if a.id != orphan.id and a.role_norm and a.current_stage not in CLOSED_STAGES
            and a.first_seen <= first
            and fuzz.token_set_ratio(orphan.role_norm, a.role_norm) == 100
            and set(orphan.role_norm.split()) & _SENIORITY == set(a.role_norm.split()) & _SENIORITY
        ]
        if len(targets) != 1:
            continue
        target = targets[0]
        for e in events:
            e.application_id = target.id
            session.add(e)
        session.flush()
        target.last_event_at = max(target.last_event_at, orphan.last_event_at)
        session.add(target)
        session.delete(orphan)
        session.flush()
        if not target.manual_override:
            recompute_stage(session, target)
        recompute_category(session, target)
        merged += 1
    session.commit()
    return merged


def split_merged_confirmations(session: Session) -> int:
    """One-time repair: older versions folded several identical role-less "thanks for applying"
    emails from one sender into a single application. Give each extra confirmation its own
    application; the original keeps the earliest one plus its notes, manual stage and other events."""
    created = 0
    for app in session.exec(select(Application).where(Application.role_norm == "")).all():
        rows = session.exec(
            select(Event, Email)
            .join(Email, Email.id == Event.email_id)
            .where(Event.application_id == app.id, Event.stage == "applied")
            .order_by(Event.occurred_at)
        ).all()
        seen: set[str] = set()
        moved = 0
        for event, email in rows:
            domain = _domain(email.from_addr)
            if domain not in seen:
                seen.add(domain)
                continue
            new_app = Application(
                company_norm=app.company_norm, company_display=app.company_display, source=app.source,
                first_seen=event.occurred_at, last_event_at=event.occurred_at, current_stage="applied",
            )
            session.add(new_app)
            session.flush()
            event.application_id = new_app.id
            session.add(event)
            recompute_category(session, new_app)
            moved += 1
        created += moved
        if moved:
            remaining = session.exec(select(Event).where(Event.application_id == app.id)).all()
            if remaining:
                app.first_seen = min(e.occurred_at for e in remaining)
                app.last_event_at = max(e.occurred_at for e in remaining)
            if not app.manual_override:
                recompute_stage(session, app)
            session.add(app)
    session.commit()
    return created
