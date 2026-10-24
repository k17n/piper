"""Stage state machine: current stage from event history, plus query-time ghosting."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from .schema import RANK, TERMINAL, Stage


def compute_current_stage(events: Iterable[tuple[str, datetime]]) -> str:
    """Highest progress stage reached; a terminal stage wins if it came at or after it."""
    best: Stage | None = None
    best_at: datetime | None = None
    terminal: Stage | None = None
    terminal_at: datetime | None = None
    for raw, at in sorted(events, key=lambda e: e[1]):
        stage = Stage(raw)
        if stage in TERMINAL and stage is not Stage.accepted:
            terminal, terminal_at = stage, at
        if stage in RANK and (best is None or RANK[stage] > RANK[best]):
            best, best_at = stage, at
    if terminal is not None and (best_at is None or terminal_at >= best_at):
        return terminal.value
    return (best or Stage.applied).value


def effective_stage(
    current_stage: str,
    last_event_at: datetime,
    manual_override: bool,
    now: datetime,
    ghost_days: int,
) -> str:
    """Add `ghosted` at query time; never stored. Manual overrides are left alone."""
    if manual_override or Stage(current_stage) in TERMINAL:
        return current_stage
    if now - last_event_at > timedelta(days=ghost_days):
        return Stage.ghosted.value
    return current_stage
