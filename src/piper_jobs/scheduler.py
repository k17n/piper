from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from .config import Settings
from .pipeline import SyncRunner

STARTUP_DELAY = timedelta(seconds=30)


def start_scheduler(runner: SyncRunner, settings: Settings) -> BackgroundScheduler:
    """Sync every SYNC_INTERVAL_HOURS while the app is open, plus once shortly after start.

    Background syncs never open the OAuth browser flow: they only run once Gmail is connected.
    """

    def job() -> None:
        if settings.token_path.is_file():
            runner.start(interactive=False)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        job,
        "interval",
        hours=settings.sync_interval_hours,
        next_run_time=datetime.now() + STARTUP_DELAY,
        id="gmail-sync",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
