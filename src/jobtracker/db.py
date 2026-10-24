"""SQLite storage via SQLModel. All datetimes are stored as naive UTC."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import NaiveDatetime
from sqlalchemy import JSON, Column, event
from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, create_engine


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Email(SQLModel, table=True):
    __tablename__ = "emails"
    id: str = Field(primary_key=True)
    thread_id: str | None = None
    from_addr: str = ""
    to_addr: str = ""
    subject: str = ""
    received_at: NaiveDatetime
    processed_at: NaiveDatetime | None = None
    snippet: str = ""
    llm_status: str = "pending"  # skipped | not_job | ok | review | outgoing


class Application(SQLModel, table=True):
    __tablename__ = "applications"
    id: int | None = Field(default=None, primary_key=True)
    company_norm: str = Field(index=True)
    company_display: str
    role_norm: str = ""
    role_display: str = ""
    source: str = "other"
    first_seen: NaiveDatetime
    last_event_at: NaiveDatetime
    current_stage: str = "applied"
    manual_override: bool = False
    category: str = "other"  # design | product | vc | other
    category_manual: bool = False  # set by you: later emails won't change it
    notes: str = ""


class Event(SQLModel, table=True):
    __tablename__ = "events"
    id: int | None = Field(default=None, primary_key=True)
    email_id: str | None = Field(default=None, foreign_key="emails.id")
    application_id: int = Field(foreign_key="applications.id", index=True)
    stage: str
    occurred_at: NaiveDatetime
    confidence: float = 1.0
    source: str | None = None


class ReviewItem(SQLModel, table=True):
    __tablename__ = "review_queue"
    id: int | None = Field(default=None, primary_key=True)
    email_id: str = Field(foreign_key="emails.id")
    reason: str
    extracted: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    excerpt: str = ""  # the email text, kept only for review items so it can be read in the app
    resolved: bool = False


class SyncState(SQLModel, table=True):
    __tablename__ = "sync_state"
    key: str = Field(primary_key=True)
    value: str


class SavedView(SQLModel, table=True):
    __tablename__ = "saved_views"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    filters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    is_default: bool = False
    created_at: NaiveDatetime = Field(default_factory=utcnow)
    updated_at: NaiveDatetime = Field(default_factory=utcnow)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    if type(dbapi_conn).__module__.startswith("sqlite3"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


_engines: dict[str, Engine] = {}


def get_engine(db_path: Path) -> Engine:
    key = str(Path(db_path).resolve())
    if key not in _engines:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(engine)
        _add_missing_columns(engine)
        _engines[key] = engine
    return _engines[key]


# Columns added after a table first shipped: (table, column, SQL type + default).
_ADDED_COLUMNS = [
    ("review_queue", "excerpt", "TEXT NOT NULL DEFAULT ''"),
    ("emails", "to_addr", "VARCHAR NOT NULL DEFAULT ''"),
    ("applications", "category", "VARCHAR NOT NULL DEFAULT 'other'"),
    ("applications", "category_manual", "BOOLEAN NOT NULL DEFAULT 0"),
]


def _add_missing_columns(engine: Engine) -> None:
    with engine.begin() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def dispose_engine(db_path: Path) -> None:
    engine = _engines.pop(str(Path(db_path).resolve()), None)
    if engine is not None:
        engine.dispose()


def get_state(session: Session, key: str) -> str | None:
    row = session.get(SyncState, key)
    return row.value if row else None


def set_state(session: Session, key: str, value: str) -> None:
    row = session.get(SyncState, key)
    if row:
        row.value = value
    else:
        session.add(SyncState(key=key, value=value))
