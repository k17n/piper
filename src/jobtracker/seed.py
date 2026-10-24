"""`jobtracker seed`: realistic fake data so the UI works before Gmail is connected."""

from __future__ import annotations

import random
from datetime import timedelta

from sqlmodel import Session, select

from .db import Email, ReviewItem, SavedView, get_state, set_state, utcnow
from .filters import Filters
from .resolver import apply_event

# Fictional companies, so sample data never looks like anyone's real search.
COMPANIES = [
    "Acme Analytics", "Northwind", "Globex", "Initech", "Hooli", "Umbrella Health", "Soylent Foods",
    "Vandelay Imports", "Wonka Labs", "Stark Robotics", "Wayne Logistics", "Tyrell Systems", "Cyberdyne",
    "Aperture Science", "Black Mesa", "Massive Dynamic", "Oscorp", "Gringotts Pay", "Monarch Travel",
    "Pied Piper", "Nakatomi Trading", "Duff Media", "Krusty Kitchens", "Sterling Cooper", "Dunder Paper",
    "Bluth Homes", "Prestige Worldwide", "Gekko Capital", "Rekall", "Weyland Freight", "Virtucon",
    "Zorg Industries", "Ollivander Tools", "Ghostbusters Co",
]
ROLES = [
    "Software Engineer", "Backend Engineer", "Full Stack Developer", "Senior Software Engineer",
    "Platform Engineer", "Data Engineer", "Frontend Engineer", "SDE II",
]
SOURCES = ["linkedin"] * 5 + ["ats"] * 3 + ["recruiter", "direct"]


def _journey(rng: random.Random) -> list[str]:
    path = ["applied"]
    if rng.random() < 0.55:
        path.append("viewed")
    roll = rng.random()
    if roll < 0.35:
        return path + ["rejected"]
    if roll < 0.55:
        return path  # no reply yet / ghosted
    if rng.random() < 0.5:
        path.append("assessment")
        if rng.random() < 0.35:
            return path + ["rejected"]
    path.append("interview")
    roll = rng.random()
    if roll < 0.45:
        return path + ["rejected"]
    if roll < 0.55:
        return path + ["withdrawn"]
    if roll < 0.75:
        return path
    path.append("offer")
    return path + (["accepted"] if rng.random() < 0.5 else [])


def seed(session: Session, *, n: int = 70, force: bool = False) -> int:
    if get_state(session, "seeded") and not force:
        return 0
    rng = random.Random(42)
    now = utcnow()
    pairs = rng.sample([(c, r) for c in COMPANIES for r in ROLES], n)
    for company, role in pairs:
        source = rng.choice(SOURCES)
        at = now - timedelta(days=rng.randint(0, 175), hours=rng.randint(0, 23))
        for stage in _journey(rng):
            if at > now:
                break
            apply_event(session, company=company, role=role, stage=stage,
                        source=source, occurred_at=at, confidence=0.9)
            at += timedelta(days=rng.randint(1, 12), hours=rng.randint(0, 12))

    for k, (subject, reason) in enumerate([
        ("Quick chat about an opportunity?", "Low confidence"),
        ("Your candidate portal update", "Missing company or stage"),
    ]):
        email_id = f"seed-review-{k}"
        session.add(Email(id=email_id, from_addr="talent@example.com", subject=subject,
                          received_at=now - timedelta(days=k + 1), processed_at=now,
                          snippet="Hi! I came across your profile and wanted to talk about a backend role…",
                          llm_status="review"))
        session.flush()
        session.add(ReviewItem(email_id=email_id, reason=reason,
                               extracted={"company": None, "role": "Backend Engineer", "stage": None}))

    for name, filters, default in [
        ("Last 90 days", Filters(range="90d"), True),
        ("LinkedIn · interviews+", Filters(range="all", sources=["linkedin"],
                                           stages=["interview", "offer", "accepted"]), False),
    ]:
        if session.exec(select(SavedView).where(SavedView.name == name)).first():
            continue
        session.add(SavedView(name=name, filters=filters.to_json(), is_default=default))

    set_state(session, "seeded", now.isoformat())
    session.commit()
    return n
