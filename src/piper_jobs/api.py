"""FastAPI app: JSON API under /api, the built React SPA at /."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from .config import Settings, load_settings
from .db import Application, Email, Event, ReviewItem, SavedView, get_engine, get_state, set_state, utcnow
from . import gmail_client
from .gmail_client import message_url
from .filters import AppRow, Filters, RangeKey, load_rows
from .pipeline import SyncRunner
from .resolver import (apply_event, normalize_role, recompute_all_categories, recompute_category,
                       recompute_stage, split_merged_confirmations)
from .sankey import build_sankey
from .schema import Source, Stage
from .stats import compute_insights, compute_stats

STATIC_DIR = Path(__file__).parent / "static"


class UIFiles(StaticFiles):
    """The built UI. index.html is always revalidated, so a rebuilt UI is picked up on the next load
    (a cached index.html would point at asset files that no longer exist). Hashed assets never change."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path.replace("\\", "/").startswith("assets/"):  # Windows passes OS separators
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response


class ApplicationPatch(BaseModel):
    stage: Stage | None = None
    notes: str | None = None
    manual_override: bool | None = None  # false clears the override and recomputes
    category: Literal["design", "product", "vc", "other"] | None = None  # sets it by hand
    category_auto: bool | None = None  # true goes back to the automatic role type
    role: str | None = None  # name the role, e.g. for a confirmation that didn't say which one


class ResolveIn(BaseModel):
    action: str = "apply"  # apply | dismiss
    company: str | None = None
    role: str | None = None
    stage: Stage | None = None
    source: Source | None = None
    application_id: int | None = None  # attach to this application (when the email named no role)


class ViewIn(BaseModel):
    name: str
    filters: Filters
    is_default: bool = False


class ViewPatch(BaseModel):
    name: str | None = None
    filters: Filters | None = None
    is_default: bool | None = None


def get_filters(
    range: RangeKey = "90d",
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    sources: list[str] = Query([]),
    stages: list[str] = Query([]),
    categories: list[str] = Query([]),
    q: str | None = None,
    include_ghosted: bool = True,
) -> Filters:
    return Filters(range=range, from_=from_, to=to, sources=sources, stages=stages, categories=categories,
                   q=q, include_ghosted=include_ghosted)


def application_json(row: AppRow, emails: dict[str, Email] | None = None, account: str | None = None) -> dict:
    """`emails` (id → Email) adds each event's subject and a Gmail link."""
    a = row.app
    emails = emails or {}

    def event_json(e: Event) -> dict:
        email = emails.get(e.email_id or "")
        real = email is not None and not email.id.startswith("seed-")
        return {
            "stage": e.stage,
            "occurred_at": e.occurred_at.isoformat(),
            "email_id": email.id if real else None,
            "subject": email.subject if email else None,
            "gmail_url": message_url(email.id, account) if real else None,
        }

    return {
        "id": a.id,
        "company": a.company_display,
        "role": a.role_display,
        "source": a.source,
        "stage": row.stage,
        "current_stage": a.current_stage,
        "manual_override": a.manual_override,
        "category": a.category,
        "category_manual": a.category_manual,
        "first_seen": a.first_seen.isoformat(),
        "last_event_at": a.last_event_at.isoformat(),
        "notes": a.notes,
        "events": [event_json(e) for e in row.events],
    }


def view_json(v: SavedView) -> dict:
    return {"id": v.id, "name": v.name, "filters": Filters.model_validate(v.filters).to_json(),
            "is_default": v.is_default, "updated_at": v.updated_at.isoformat()}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    engine = get_engine(settings.db_path)
    runner = SyncRunner(settings)
    with Session(engine) as session:  # fill in role types (new column) and apply rule updates
        recompute_all_categories(session)
        if not get_state(session, "split_confirmations_v1"):  # one-time repair, see resolver
            split_merged_confirmations(session)
            set_state(session, "split_confirmations_v1", utcnow().isoformat())
            session.commit()

    app = FastAPI(title="P.I.P.E.R.", version="0.1.0")
    app.state.settings = settings
    app.state.runner = runner

    def session_dep():
        with Session(engine) as session:
            yield session

    def rows_for(session: Session, filters: Filters) -> list[AppRow]:
        return load_rows(session, filters, settings)

    # --- read endpoints -------------------------------------------------------
    @app.get("/api/meta")
    def meta(session: Session = Depends(session_dep)):
        earliest_email = session.exec(select(func.min(Email.received_at))).one()
        earliest_app = session.exec(select(func.min(Application.first_seen))).one()
        earliest = min((d for d in (earliest_email, earliest_app) if d), default=None)
        return {
            "data_since": earliest.date().isoformat() if earliest else None,
            "last_sync_at": get_state(session, "last_sync_at"),
            "provider": settings.llm_provider,
            "model": settings.ollama_model if settings.llm_provider == "ollama" else settings.anthropic_model,
            "gmail_connected": settings.token_path.is_file(),
            "ghost_days": settings.ghost_days,
            "sync_interval_hours": settings.sync_interval_hours,
        }

    @app.get("/api/sankey")
    def sankey(filters: Filters = Depends(get_filters), session: Session = Depends(session_dep)):
        return build_sankey(rows_for(session, filters))

    @app.get("/api/stats")
    def stats(filters: Filters = Depends(get_filters), session: Session = Depends(session_dep)):
        return compute_stats(rows_for(session, filters))

    @app.get("/api/insights")
    def insights(filters: Filters = Depends(get_filters), session: Session = Depends(session_dep)):
        return compute_insights(rows_for(session, filters))

    @app.get("/api/applications")
    def applications(
        filters: Filters = Depends(get_filters),
        ids: list[int] = Query([]),
        session: Session = Depends(session_dep),
    ):
        rows = rows_for(session, filters)
        if ids:
            wanted = set(ids)
            rows = [r for r in rows if r.app.id in wanted]
        rows.sort(key=lambda r: r.app.last_event_at, reverse=True)
        emails, account = emails_for(session, rows)
        return [application_json(r, emails, account) for r in rows]

    def emails_for(session: Session, rows: list[AppRow]) -> tuple[dict[str, Email], str | None]:
        ids = list({e.email_id for r in rows for e in r.events if e.email_id})
        found: dict[str, Email] = {}
        for i in range(0, len(ids), 500):
            found.update({m.id: m for m in session.exec(select(Email).where(Email.id.in_(ids[i : i + 500]))).all()})
        return found, get_state(session, "gmail_address")

    @app.get("/api/emails/{email_id}/thread")
    def email_thread(email_id: str, session: Session = Depends(session_dep)):
        """The whole Gmail thread of one email, fetched live (read-only) and never stored."""
        email = session.get(Email, email_id)
        if not email or email.id.startswith("seed-"):
            raise HTTPException(404, "Email not found")
        try:
            service = gmail_client.get_service(settings, interactive=False)
            messages = gmail_client.fetch_thread(service, email.thread_id or email.id)
        except gmail_client.GmailNotConfigured as exc:
            raise HTTPException(409, str(exc)) from exc
        account = get_state(session, "gmail_address")
        return {
            "subject": messages[0].subject if messages else email.subject,
            "gmail_url": message_url(email.id, account),
            "messages": [
                {"id": m.id, "from": m.from_addr, "to": m.to_addr, "date": m.received_at.isoformat(),
                 "outgoing": m.outgoing, "body": m.body, "highlight": m.id == email.id}
                for m in messages
            ],
        }

    @app.patch("/api/applications/{app_id}")
    def patch_application(app_id: int, body: ApplicationPatch, session: Session = Depends(session_dep)):
        a = session.get(Application, app_id)
        if not a:
            raise HTTPException(404, "Application not found")
        if body.notes is not None:
            a.notes = body.notes
        if body.role is not None:
            a.role_display, a.role_norm = body.role.strip(), normalize_role(body.role)
            recompute_category(session, a)
        if body.category is not None:
            a.category, a.category_manual = body.category, True
        elif body.category_auto:
            a.category_manual = False
            recompute_category(session, a)
        if body.stage is not None:
            a.current_stage = body.stage.value
            a.manual_override = True
        elif body.manual_override is False:
            a.manual_override = False
            recompute_stage(session, a)
        session.add(a)
        session.commit()
        session.refresh(a)
        events = session.exec(select(Event).where(Event.application_id == a.id).order_by(Event.occurred_at)).all()
        row = AppRow(app=a, events=list(events), stage=a.current_stage)
        return application_json(row, *emails_for(session, [row]))

    # --- review queue ---------------------------------------------------------
    @app.get("/api/review-queue")
    def review_queue(session: Session = Depends(session_dep)):
        items = session.exec(select(ReviewItem).where(ReviewItem.resolved == False)).all()  # noqa: E712
        account = get_state(session, "gmail_address")
        out = []
        for item in items:
            email = session.get(Email, item.email_id)
            out.append({
                "id": item.id,
                "reason": item.reason,
                "extracted": item.extracted,
                "candidates": [
                    {"id": a.id, "role": a.role_display, "stage": a.current_stage,
                     "first_seen": a.first_seen.isoformat()}
                    for cid in (item.extracted or {}).get("candidates", [])
                    if (a := session.get(Application, cid)) is not None
                ],
                "email": {
                    "id": email.id, "from": email.from_addr, "subject": email.subject,
                    "received_at": email.received_at.isoformat(), "snippet": email.snippet,
                    "body": gmail_client.clean_text(item.excerpt or email.snippet),
                    "gmail_url": None if email.id.startswith("seed-") else message_url(email.id, account),
                } if email else None,
            })
        return out

    @app.post("/api/review-queue/{item_id}/resolve")
    def resolve_review(item_id: int, body: ResolveIn, session: Session = Depends(session_dep)):
        item = session.get(ReviewItem, item_id)
        if not item or item.resolved:
            raise HTTPException(404, "Review item not found")
        email = session.get(Email, item.email_id)
        if body.action == "apply":
            if not body.company or not body.stage:
                raise HTTPException(422, "company and stage are required")
            target = session.get(Application, body.application_id) if body.application_id else None
            if body.application_id and target is None:
                raise HTTPException(404, "Application not found")
            apply_event(session, company=target.company_display if target else body.company, role=body.role,
                        stage=body.stage.value, source=body.source, occurred_at=email.received_at,
                        email_id=email.id, application_id=body.application_id)
            email.llm_status = "ok"
        else:
            email.llm_status = "not_job"
        item.resolved = True
        session.add(item)
        session.add(email)
        session.commit()
        return {"ok": True}

    # --- saved views ----------------------------------------------------------
    def _clear_default(session: Session, keep_id: int | None) -> None:
        for v in session.exec(select(SavedView).where(SavedView.is_default == True)).all():  # noqa: E712
            if v.id != keep_id:
                v.is_default = False
                session.add(v)

    def _name_taken(session: Session, name: str, exclude_id: int | None = None) -> bool:
        existing = session.exec(select(SavedView).where(SavedView.name == name)).first()
        return existing is not None and existing.id != exclude_id

    @app.get("/api/views")
    def list_views(session: Session = Depends(session_dep)):
        return [view_json(v) for v in session.exec(select(SavedView).order_by(SavedView.name)).all()]

    @app.post("/api/views", status_code=201)
    def create_view(body: ViewIn, session: Session = Depends(session_dep)):
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "Name is required")
        if _name_taken(session, name):
            raise HTTPException(409, f"A view named '{name}' already exists")
        view = SavedView(name=name, filters=body.filters.to_json(), is_default=body.is_default)
        session.add(view)
        session.flush()
        if view.is_default:
            _clear_default(session, view.id)
        session.commit()
        session.refresh(view)
        return view_json(view)

    @app.patch("/api/views/{view_id}")
    def patch_view(view_id: int, body: ViewPatch, session: Session = Depends(session_dep)):
        view = session.get(SavedView, view_id)
        if not view:
            raise HTTPException(404, "View not found")
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise HTTPException(422, "Name is required")
            if _name_taken(session, name, view.id):
                raise HTTPException(409, f"A view named '{name}' already exists")
            view.name = name
        if body.filters is not None:
            view.filters = body.filters.to_json()
        if body.is_default is not None:
            view.is_default = body.is_default
            if body.is_default:
                _clear_default(session, view.id)
        view.updated_at = utcnow()
        session.add(view)
        session.commit()
        session.refresh(view)
        return view_json(view)

    @app.delete("/api/views/{view_id}", status_code=204)
    def delete_view(view_id: int, session: Session = Depends(session_dep)):
        view = session.get(SavedView, view_id)
        if not view:
            raise HTTPException(404, "View not found")
        session.delete(view)
        session.commit()

    # --- sync -----------------------------------------------------------------
    @app.post("/api/sync", status_code=202)
    def start_sync(full: bool = False):
        started = runner.start(full=full)
        return {"started": started, "status": runner.status}

    @app.get("/api/sync/status")
    def sync_status():
        return runner.status

    @app.get("/api/sync/stream")
    async def sync_stream(request: Request):
        async def events():
            last = -1
            while not await request.is_disconnected():
                if runner.version != last:
                    last = runner.version
                    yield f"data: {json.dumps(runner.status)}\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})

    # --- UI -------------------------------------------------------------------
    if (STATIC_DIR / "index.html").is_file():
        app.mount("/", UIFiles(directory=STATIC_DIR, html=True), name="ui")
    else:
        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        def ui_missing():
            return ("<h2>UI not built</h2><p>Run <code>cd web &amp;&amp; npm install &amp;&amp; "
                    "npm run build</code>, then restart. API docs: <a href='/docs'>/docs</a></p>")

    return app
