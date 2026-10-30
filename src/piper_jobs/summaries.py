"""The written summary: a small cache of model replies, and the service that decides when to ask the model."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from .config import Settings
from .db import InsightSummary, utcnow
from .insights import MIN_APPLICATIONS, PROMPT_VERSION, build_facts, build_messages, facts_hash, is_grounded, ungrounded_numbers

log = logging.getLogger(__name__)

MAX_ENTRIES = 50


def get_cached(session: Session, key: str) -> str | None:
    row = session.get(InsightSummary, key)
    if row is None:
        return None
    text = row.text  # read before the commit expires the row
    row.last_used_at = utcnow()
    session.add(row)
    session.commit()
    return text


def save(session: Session, key: str, text: str, model: str, prompt_version: int) -> None:
    now = utcnow()
    row = session.get(InsightSummary, key)
    if row:
        row.text, row.model, row.prompt_version, row.last_used_at = text, model, prompt_version, now
        session.add(row)
    else:
        session.add(InsightSummary(hash=key, text=text, model=model, prompt_version=prompt_version,
                                   created_at=now, last_used_at=now))
    session.commit()
    prune_excess(session)


def delete_cached(session: Session, key: str) -> None:
    row = session.get(InsightSummary, key)
    if row:
        session.delete(row)
        session.commit()


def prune_excess(session: Session, keep: int = MAX_ENTRIES) -> None:
    """Keep the most recently used entries."""
    rows = session.exec(select(InsightSummary).order_by(InsightSummary.last_used_at.desc(), InsightSummary.created_at.desc())).all()
    for row in rows[keep:]:
        session.delete(row)
    session.commit()


def prune_stale(session: Session, model: str, prompt_version: int) -> None:
    """Drop summaries written by another model or an older prompt."""
    rows = session.exec(
        select(InsightSummary).where((InsightSummary.model != model) | (InsightSummary.prompt_version != prompt_version))
    ).all()
    for row in rows:
        session.delete(row)
    session.commit()


DEBOUNCE_SECONDS = 10  # the same facts must be requested this long before the model is asked
RETRY_AFTER_SECONDS = 300  # after a failed or ungrounded reply
VARIANT_TEMPERATURE = 0.6  # "write it again" must not return the same words
GENERATE_TIMEOUT_SECONDS = 120  # a hung Ollama must not block summaries forever
_MAX_TRACKED = 100


def ollama_generate(settings: Settings) -> Callable[[list[dict], float], str]:
    def generate(messages: list[dict], temperature: float) -> str:
        import ollama

        reply = ollama.Client(host=settings.ollama_host, timeout=GENERATE_TIMEOUT_SECONDS).chat(
            model=settings.ollama_model, messages=messages, options={"temperature": temperature}
        )
        return reply.message.content or ""

    return generate


def _spawn_thread(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True).start()


class SummaryService:
    """Serves cached summaries and generates missing ones in the background, one at a time.

    `status` is meant to be polled: the first request for a set of facts starts the quiet period, and the
    request that arrives after it (outside a sync) starts the model."""

    def __init__(
        self,
        settings: Settings,
        engine: Engine,
        is_syncing: Callable[[], bool],
        generate: Callable[[list[dict], float], str] | None = None,
        spawn: Callable[[Callable[[], None]], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.engine = engine
        self.is_syncing = is_syncing
        self.generate = generate or ollama_generate(settings)
        self.spawn = spawn or _spawn_thread
        self.clock = clock
        self.debounce = DEBOUNCE_SECONDS
        self._lock = threading.Lock()
        self._first_seen: dict[str, float] = {}
        self._failed: dict[str, float] = {}
        self._variant: set[str] = set()
        self._running: str | None = None
        self._regenerate: set[str] = set()

    @property
    def model(self) -> str:
        return self.settings.ollama_model

    def status(self, analytics: dict) -> dict:
        facts = build_facts(analytics)
        if analytics["summary"]["total"] < MIN_APPLICATIONS:
            return {"status": "insufficient_data", "text": None, "facts": facts}
        key = facts_hash(facts, self.model)
        with Session(self.engine) as session:
            text = get_cached(session, key)
        if text:
            return {"status": "ready", "text": text, "facts": facts}
        now = self.clock()
        syncing = self.is_syncing()
        with self._lock:
            failed_at = self._failed.get(key)
            if failed_at is not None and now - failed_at < RETRY_AFTER_SECONDS:
                return {"status": "fallback", "text": None, "facts": facts}
            if len(self._first_seen) > _MAX_TRACKED:
                self._first_seen.clear()
            first = self._first_seen.setdefault(key, now)
            start = self._running is None and not syncing and now - first >= self.debounce
            temperature = VARIANT_TEMPERATURE if key in self._variant else 0.0
            if start:
                self._running = key
        if start:
            try:
                self.spawn(lambda: self._generate(key, facts, temperature))
            except Exception:  # e.g. no thread could be started: show the facts instead of failing the request
                log.warning("Could not start the summary", exc_info=True)
                with self._lock:
                    self._running = None
                    self._first_seen.pop(key, None)  # a fresh quiet period before the next try
                    self._remember_failure(key, now)
                return {"status": "fallback", "text": None, "facts": facts}
        return {"status": "pending", "text": None, "facts": facts}

    def _remember_failure(self, key: str, now: float) -> None:
        """Caller holds the lock."""
        if len(self._failed) > _MAX_TRACKED:
            self._failed = {k: t for k, t in self._failed.items() if now - t < RETRY_AFTER_SECONDS}
            if len(self._failed) > _MAX_TRACKED:
                self._failed.clear()
        self._failed[key] = now

    def refresh(self, analytics: dict) -> dict:
        """Forget the cached text for these facts and ask again now, with different wording."""
        facts = build_facts(analytics)
        if analytics["summary"]["total"] >= MIN_APPLICATIONS:
            key = facts_hash(facts, self.model)
            with Session(self.engine) as session:
                delete_cached(session, key)
            with self._lock:
                self._failed.pop(key, None)
                self._variant.add(key)
                self._first_seen[key] = self.clock() - self.debounce
                if self._running == key:
                    self._regenerate.add(key)  # the run in progress will use the old wording; go again after it
        return self.status(analytics)

    def _generate(self, key: str, facts: list[str], temperature: float) -> None:
        regenerate = False
        try:
            messages = build_messages(facts)
            text = self.generate(messages, temperature).strip()
            if not is_grounded(text, facts):
                bad = ungrounded_numbers(text, facts)
                log.warning("The summary used numbers that are not in the facts (%s), asking once more: %s",
                            ", ".join(sorted(bad)), text)
                messages = [*messages, {"role": "assistant", "content": text}, {"role": "user", "content": (
                    f"That used numbers that are not in the facts: {', '.join(sorted(bad))}. "
                    "Write it again using only numbers copied exactly from the facts.")}]
                text = self.generate(messages, temperature).strip()
                if not is_grounded(text, facts):
                    raise ValueError("the summary used numbers that are not in the facts")
            with Session(self.engine) as session:
                save(session, key, text, self.model, PROMPT_VERSION)
        except Exception as exc:  # the model being down must never break the page: show the facts instead
            log.warning("Could not write the summary: %s", exc, exc_info=True)
            with self._lock:
                self._remember_failure(key, self.clock())
        finally:
            with self._lock:
                self._running = None
                regenerate = key in self._regenerate
                self._regenerate.discard(key)
                if regenerate:
                    self._failed.pop(key, None)
                    self._first_seen[key] = self.clock() - self.debounce
                else:
                    self._first_seen.pop(key, None)
                    self._variant.discard(key)
        if regenerate:
            try:
                with Session(self.engine) as session:
                    delete_cached(session, key)
            except Exception:
                log.warning("Could not clear the summary for rewriting", exc_info=True)
