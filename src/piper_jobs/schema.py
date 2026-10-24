"""Core types: the Stage enum, the LLM's JobEvent output, and a fetched email."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, get_args

from pydantic import BaseModel, Field


class Stage(StrEnum):
    applied = "applied"
    viewed = "viewed"
    assessment = "assessment"
    interview = "interview"
    offer = "offer"
    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"
    ghosted = "ghosted"


PROGRESS: list[Stage] = [
    Stage.applied,
    Stage.viewed,
    Stage.assessment,
    Stage.interview,
    Stage.offer,
    Stage.accepted,
]
RANK: dict[Stage, int] = {s: i for i, s in enumerate(PROGRESS)}
TERMINAL: set[Stage] = {Stage.rejected, Stage.withdrawn, Stage.ghosted, Stage.accepted}

Source = Literal["linkedin", "ats", "recruiter", "direct", "referral", "other"]
SOURCES: tuple[str, ...] = get_args(Source)


class JobEvent(BaseModel):
    is_job_related: bool
    company: str | None
    role: str | None
    stage: Stage | None
    source: Source | None
    confidence: float = Field(ge=0, le=1)


@dataclass
class RawEmail:
    id: str
    thread_id: str | None
    from_addr: str
    subject: str
    received_at: datetime  # naive UTC
    body: str
    to_addr: str = ""
    outgoing: bool = False  # sent by the user (Gmail SENT label)
    promotional: bool = False  # Gmail filed it under Promotions
    bulk: bool = False  # mailing-list / bulk mail (List-Unsubscribe or Precedence: bulk)
    context: str = ""  # what we already know, e.g. "already in a hiring process with Northstar"

    @property
    def snippet(self) -> str:
        return self.body[:300]
