"""The shared filter model used by every read endpoint and by saved views."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from .config import Settings
from .db import Application, Event, utcnow
from .stages import effective_stage

RangeKey = Literal["30d", "90d", "180d", "all", "custom"]
RANGE_DAYS = {"30d": 30, "90d": 90, "180d": 180}


class Filters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    range: RangeKey = "90d"
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None
    sources: list[str] = []
    stages: list[str] = []
    categories: list[str] = []  # role types: design | product | vc | other; empty = all
    q: str | None = None
    include_ghosted: bool = True

    def date_bounds(self, today: date) -> tuple[date | None, date | None]:
        if self.range == "custom":
            return self.from_, self.to
        if self.range == "all":
            return None, None
        return today - timedelta(days=RANGE_DAYS[self.range]), None

    def to_json(self) -> dict:
        return self.model_dump(by_alias=True, mode="json")


@dataclass
class AppRow:
    app: Application
    events: list[Event]
    stage: str  # effective stage (includes query-time ghosting)
    reached: set[str] = field(default_factory=set)


def load_rows(
    session: Session, filters: Filters, settings: Settings, now: datetime | None = None
) -> list[AppRow]:
    now = now or utcnow()
    start, end = filters.date_bounds(now.date())
    q = (filters.q or "").strip().lower()

    events_by_app: dict[int, list[Event]] = defaultdict(list)
    for ev in session.exec(select(Event).order_by(Event.occurred_at)).all():
        events_by_app[ev.application_id].append(ev)

    rows: list[AppRow] = []
    for app in session.exec(select(Application)).all():
        day = app.first_seen.date()
        if (start and day < start) or (end and day > end):
            continue
        if filters.sources and app.source not in filters.sources:
            continue
        if filters.categories and app.category not in filters.categories:
            continue
        if q and q not in app.company_display.lower() and q not in app.role_display.lower():
            continue
        stage = effective_stage(
            app.current_stage, app.last_event_at, app.manual_override, now, settings.ghost_days
        )
        if filters.stages and stage not in filters.stages:
            continue
        if not filters.include_ghosted and stage == "ghosted":
            continue
        events = events_by_app.get(app.id, [])
        reached = {e.stage for e in events} | {app.current_stage, stage}
        rows.append(AppRow(app=app, events=events, stage=stage, reached=reached))
    return rows
