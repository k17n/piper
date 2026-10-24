"""Sync pipeline: Gmail → prefilter → LLM → resolver → SQLite, with progress callbacks."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, or_, select

from .config import JOB_PLATFORMS, Settings
from .db import Application, Email, Event, ReviewItem, get_engine, get_state, set_state, utcnow
from .llm import ExtractionError, Extractor, get_extractor
from .llm.prompt import PROMPT_VERSION
from .prefilter import RULES_VERSION, should_process
from .resolver import ambiguous_applications, apply_event
from .schema import RawEmail, Stage

Progress = Callable[[dict[str, Any]], None]
MIN_CONFIDENCE = 0.5  # job-related but less sure than this → review
UNSURE_NOT_JOB = 0.6  # "not job-related" but less sure than this (and from a person) → review
REVIEW_EXCERPT = 1500  # characters kept for review items only, so you can read them in the app

FREE_MAIL = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "yahoo.co.in",
    "icloud.com", "me.com", "proton.me", "protonmail.com", "rediffmail.com", "aol.com", "zoho.com",
}


def _is_company_domain(domain: str, settings: Settings) -> bool:
    if not domain or domain in FREE_MAIL:
        return False
    return not any(domain == p or domain.endswith("." + p) for p in JOB_PLATFORMS + settings.always_ignore)


def _app_for_emails(session: Session, condition) -> Application | None:
    return session.exec(
        select(Application)
        .join(Event, Event.application_id == Application.id)
        .join(Email, Email.id == Event.email_id)
        .where(condition)
        .order_by(Event.occurred_at.desc())
    ).first()


def job_context(session: Session, raw: RawEmail, settings: Settings) -> str:
    """What we already know about this email's company, so the model reads invites etc. correctly."""
    from .gmail_client import sender_domain

    app = _app_for_emails(session, Email.thread_id == raw.thread_id) if raw.thread_id else None
    domain = sender_domain(raw.from_addr)
    if app is None and _is_company_domain(domain, settings):
        app = _app_for_emails(session, or_(Email.from_addr.contains(f"@{domain}"), Email.to_addr.contains(f"@{domain}")))
    if app is None:
        return ""
    where = f" ({domain})" if _is_company_domain(domain, settings) else ""
    return f"The candidate is already in a hiring process with {app.company_display}{where}."


def _review(session: Session, email: Email, raw: RawEmail, reason: str, extracted: dict | None = None) -> None:
    email.llm_status = "review"
    session.add(email)
    session.flush()
    session.add(ReviewItem(email_id=raw.id, reason=reason[:500], extracted=extracted,
                           excerpt=raw.body[:REVIEW_EXCERPT]))


def process_email(
    session: Session, raw: RawEmail, extractor: Extractor, settings: Settings, *, outreach: bool = False
) -> str:
    """Store one email and its extraction. Returns the email's llm_status.

    `outreach` marks the first email of a thread the user started: if it's about a job, it is the
    "applied" event for that company. The user's other sent emails are stored but not analysed.
    Anything the model is unsure about goes to the review queue; bulk/promotional mail never does.
    Connection errors propagate (the email is not stored) so it is retried next sync.
    """
    email = Email(
        id=raw.id,
        thread_id=raw.thread_id,
        from_addr=raw.from_addr,
        to_addr=raw.to_addr if raw.outgoing else "",
        subject=raw.subject,
        received_at=raw.received_at,
        snippet=raw.snippet,
    )
    keep, _reason = should_process(raw, include=settings.always_include, ignore=settings.always_ignore,
                                  never=settings.never_job_subjects)
    if raw.outgoing and not outreach:
        email.llm_status = "outgoing"
    elif not keep:
        email.llm_status = "skipped"
    else:
        raw.context = raw.context or job_context(session, raw, settings)
        try:
            event = extractor.extract(raw)
        except ExtractionError as exc:
            _review(session, email, raw, f"The model's answer couldn't be read: {exc}")
            event = None
        if event is not None and outreach and event.is_job_related:
            event.stage, event.source = Stage.applied, event.source or "direct"
        if event is not None:
            extracted = event.model_dump(mode="json")
            if not event.is_job_related:
                if event.confidence < UNSURE_NOT_JOB and not raw.bulk:
                    _review(session, email, raw, "Not sure if this is about a job", extracted)
                else:
                    email.llm_status = "not_job"
            elif event.confidence < MIN_CONFIDENCE:
                _review(session, email, raw, "Low confidence", extracted)
            elif not event.company or not event.stage:
                _review(session, email, raw, "Couldn't tell the company or stage", extracted)
            elif options := ambiguous_applications(session, event.company, event.role, event.stage.value):
                extracted["candidates"] = [a.id for a in options]
                _review(session, email, raw, f"Which {options[0].company_display} application is this about?", extracted)
            else:
                email.llm_status = "ok"
                session.add(email)
                session.flush()
                apply_event(
                    session,
                    company=event.company,
                    role=event.role,
                    stage=event.stage.value,
                    source=event.source,
                    occurred_at=raw.received_at,
                    email_id=raw.id,
                    confidence=event.confidence,
                )
    email.processed_at = utcnow()
    session.add(email)
    session.commit()
    return email.llm_status


def store_own_reply(session: Session, message_id: str, thread_id: str, sent_at: datetime) -> None:
    """The user's later replies in a conversation: remembered (so never re-fetched), not analysed."""
    session.add(Email(id=message_id, thread_id=thread_id, from_addr="me", received_at=sent_at,
                      processed_at=utcnow(), llm_status="outgoing"))
    session.commit()


def _known_ids(session: Session, ids: list[str]) -> set[str]:
    known: set[str] = set()
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        known.update(session.exec(select(Email.id).where(Email.id.in_(chunk))).all())
    return known


def company_domains(session: Session, settings: Settings) -> list[str]:
    """Domains of companies you're in touch with: senders of job emails, and recipients of your
    job outreach. Job boards, ATS vendors, personal mail providers and your own domain are left out."""
    from email.utils import getaddresses

    from .gmail_client import sender_domain

    mine = sender_domain(get_state(session, "gmail_address") or "")
    domains: set[str] = {d for d in settings.always_include if "@" not in d}
    rows = session.exec(select(Email.from_addr, Email.to_addr).where(Email.llm_status == "ok")).all()
    for from_addr, to_addr in rows:
        found = [sender_domain(from_addr)]
        if to_addr:  # your outreach: follow whoever you wrote to
            found = [a.rsplit("@", 1)[-1].lower() for _n, a in getaddresses([to_addr]) if "@" in a]
        domains.update(d for d in found if d != mine and _is_company_domain(d, settings))
    return sorted(domains)


def _dismiss_reviews_now_filtered(session: Session, settings: Settings) -> None:
    """Open review items that today's filter rules would drop (e.g. a newly listed never-job subject)."""
    for item in session.exec(select(ReviewItem).where(ReviewItem.resolved == False)).all():  # noqa: E712
        email = session.get(Email, item.email_id)
        if email is None:
            continue
        stored = RawEmail(email.id, email.thread_id, email.from_addr, email.subject, email.received_at, "")
        keep, _ = should_process(stored, include=settings.always_include, ignore=settings.always_ignore,
                                  never=settings.never_job_subjects)
        if not keep:
            item.resolved, email.llm_status = True, "skipped"
            session.add(item)
            session.add(email)


def _delete_review_history(session: Session, email_ids: list[str]) -> None:
    for i in range(0, len(email_ids), 500):
        chunk = email_ids[i : i + 500]
        for item in session.exec(select(ReviewItem).where(ReviewItem.email_id.in_(chunk))).all():
            session.delete(item)
    session.flush()  # review items must be gone before their emails are deleted (foreign key)


def _not_job_with_known_company(session: Session, settings: Settings) -> list[Email]:
    """'Not a job' verdicts made without context that we can now give (known company or thread).
    Emails with review history are left alone: you decided those yourself ("Not a job email")."""
    from .gmail_client import sender_domain

    domains = set(company_domains(session, settings))
    threads = set(session.exec(
        select(Email.thread_id).join(Event, Event.email_id == Email.id).where(Email.thread_id.is_not(None))
    ).all())
    reviewed = set(session.exec(select(ReviewItem.email_id)).all())
    return [
        e for e in session.exec(select(Email).where(Email.llm_status == "not_job")).all()
        if e.id not in reviewed and (sender_domain(e.from_addr) in domains or e.thread_id in threads)
    ]


def sync(
    settings: Settings,
    progress: Progress = lambda _p: None,
    *,
    dry_run: bool = False,
    full: bool = False,
    interactive: bool = True,
    service=None,
    extractor: Extractor | None = None,
) -> dict[str, Any]:
    from . import gmail_client

    engine = get_engine(settings.db_path)
    started = utcnow()
    signature = settings.filter_signature(f"{RULES_VERSION}.{PROMPT_VERSION}")
    with Session(engine) as session:
        last = None if full else get_state(session, "last_sync_at")
        if get_state(session, "filter_signature") != signature:
            # Filters changed: search the whole window again and re-check what was skipped before.
            last = None
            if not dry_run:
                skipped = session.exec(select(Email).where(Email.llm_status == "skipped")).all()
                # skipped emails can carry a review item the rules auto-dismissed; it goes with them
                _delete_review_history(session, [e.id for e in skipped])
                for e in skipped:
                    session.delete(e)
                for e in _not_job_with_known_company(session, settings):
                    session.delete(e)
                _dismiss_reviews_now_filtered(session, settings)
                session.commit()
    after = datetime.fromisoformat(last) - timedelta(days=1) if last else None
    query = gmail_client.build_query(settings, after)

    progress({"state": "running", "phase": "listing", "message": "Searching Gmail..."})
    service = service or gmail_client.get_service(settings, interactive=interactive)
    if not dry_run:
        with Session(engine) as session:  # lets the app link review items to the right Gmail account
            set_state(session, "gmail_address", gmail_client.my_address(service))
            session.commit()

    # message id → "inbound" | "outreach" (first mail of a thread you started) | "reply" (your later mail)
    plan: dict[str, str] = {mid: "inbound" for mid in gmail_client.list_message_ids(service, query)}
    reply_info: dict[str, tuple[str, datetime]] = {}
    if settings.include_sent_threads:
        progress({"state": "running", "phase": "listing", "message": "Reading your conversations..."})
        for thread in gmail_client.list_sent_threads(service, settings):
            for mid in thread.message_ids:
                if mid in thread.sent_ids:
                    first = thread.started_by_me and mid == thread.message_ids[0]
                    plan[mid] = "outreach" if first else "reply"
                    reply_info[mid] = (thread.id, thread.dates[mid])
                else:
                    plan.setdefault(mid, "inbound")

    with Session(engine) as session:
        known = _known_ids(session, list(plan))
    todo = [(mid, kind) for mid, kind in plan.items() if mid not in known]

    if dry_run:
        emails, own_replies = [], 0
        for n, (mid, kind) in enumerate(todo, 1):
            progress({"state": "running", "phase": "fetching", "current": n, "total": len(todo)})
            if kind == "reply":
                own_replies += 1
                continue
            raw = gmail_client.fetch_email(service, mid)
            keep, reason = should_process(raw, include=settings.always_include, ignore=settings.always_ignore,
                                  never=settings.never_job_subjects)
            emails.append({"id": raw.id, "date": raw.received_at.isoformat(), "from": raw.from_addr,
                           "subject": raw.subject, "keep": keep, "reason": reason, "kind": kind})
        return {"query": query, "matched": len(plan), "new": len(todo), "own_replies": own_replies,
                "emails": emails}

    extractor = extractor or get_extractor(settings)
    counts: dict[str, int] = {}

    def run(items: list[tuple[str, str]], session: Session, label: str) -> None:
        for n, (mid, kind) in enumerate(items, 1):
            if kind == "reply":
                thread_id, sent_at = reply_info[mid]
                store_own_reply(session, mid, thread_id, sent_at)
                status = "outgoing"
            else:
                raw = gmail_client.fetch_email(service, mid)
                progress({"state": "running", "phase": "extracting", "current": n, "total": len(items),
                          "model": extractor.name, "message": f"{label}{raw.subject[:80]}"})
                status = process_email(session, raw, extractor, settings, outreach=kind == "outreach")
            counts[status] = counts.get(status, 0) + 1

    with Session(engine) as session:
        run(todo, session, "")

        # Second pass: everything from companies you're in touch with (calendar invites, bookings, ...).
        followed = 0
        domains = company_domains(session, settings) if settings.follow_company_domains else []
        for i in range(0, len(domains), 20):
            ids = gmail_client.list_message_ids(service, gmail_client.domains_query(settings, domains[i : i + 20]))
            known = _known_ids(session, ids)
            extra = [(mid, "inbound") for mid in ids if mid not in known and mid not in plan]
            plan.update(dict(extra))
            followed += len(extra)
            run(extra, session, "Following up: ")

        set_state(session, "last_sync_at", started.isoformat())
        set_state(session, "filter_signature", signature)
        session.commit()
    return {"query": query, "matched": len(plan), "new": len(todo) + followed, "followed": followed,
            "domains": len(domains), "counts": counts}


class SyncRunner:
    """Runs one sync at a time in a background thread and keeps the latest status."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self.version = 0
        self.status: dict[str, Any] = {"state": "idle"}

    @property
    def running(self) -> bool:
        return self._lock.locked()

    def start(self, *, full: bool = False, interactive: bool = True) -> bool:
        if not self._lock.acquire(blocking=False):
            return False
        self._update({"state": "running", "phase": "starting", "message": "Starting sync..."})
        threading.Thread(target=self._run, args=(full, interactive), daemon=True).start()
        return True

    def _run(self, full: bool, interactive: bool) -> None:
        try:
            summary = sync(self.settings, self._update, full=full, interactive=interactive)
            self._update({"state": "done", **summary})
        except Exception as exc:  # surfaced to the UI
            self._update({"state": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            self._lock.release()

    def _update(self, status: dict[str, Any]) -> None:
        self.status = {**status, "updated_at": utcnow().isoformat()}
        self.version += 1
