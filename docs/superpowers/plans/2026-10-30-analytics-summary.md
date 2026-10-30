# Analytics Written Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the "Insights" card to the Analytics tab: a short written summary produced by the local model, cached by a hash of the facts it is based on (spec: [PRD-analytics.md §6.9](../../PRD-analytics.md)).

**Architecture:** A pure module (`insights.py`) turns the analytics numbers into a list of fact lines, hashes them, builds the model prompt and checks that the reply only uses numbers from the facts. A small store (`summaries.py`) keeps replies in a new SQLite table with a 50-entry least-recently-used limit. A `SummaryService` decides, per request, whether to serve the cache, wait out a 10-second quiet period, hold off during a sync, or call Ollama in a background thread. Two endpoints expose it; an `InsightsCard` polls while a summary is pending.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, `ollama` client, pytest; React 19 + TypeScript, TanStack Query.

## Global Constraints

- The model writes, the app calculates: the prompt contains only the fact lines; every number in the reply must appear in the facts, otherwise the reply is not used (status `fallback`).
- Local only: no network call except the existing local Ollama host (`settings.ollama_host`, `settings.ollama_model`).
- Fewer than 10 applications in the view (`MIN_APPLICATIONS`) → status `insufficient_data`, no model call.
- Conversion facts only for groups with 5 or more applications (`MIN_GROUP`).
- Generation starts only after the same facts have been requested for 10 seconds (`DEBOUNCE_SECONDS`), never while a sync is running, and one generation runs at a time.
- Cache key = SHA-256 of model name + prompt version + fact lines. Keep the 50 most recently used entries (`MAX_ENTRIES`). Delete entries of another model or prompt version at startup.
- The one schema addition is the table `insight_summaries(hash, text, model, prompt_version, created_at, last_used_at)`; it stores generated text only.
- API statuses: `ready`, `pending`, `insufficient_data`, `fallback`. A failed generation is not retried for 300 seconds (`RETRY_AFTER_SECONDS`).
- Match surrounding code (short docstrings, no heavy comments). Run Python with `uv run`; frontend commands from `web/`.

## File Structure

| File | Responsibility |
|---|---|
| `src/piper_jobs/insights.py` (create) | `build_facts`, `facts_hash`, `build_messages`, `is_grounded`, constants — pure, no I/O |
| `src/piper_jobs/db.py` (modify) | `InsightSummary` table |
| `src/piper_jobs/summaries.py` (create) | Cache store functions and `SummaryService` |
| `src/piper_jobs/api.py` (modify) | `analytics_data` helper, `GET /api/analytics/summary`, `POST /api/analytics/summary/refresh`, startup prune |
| `tests/conftest.py` (modify) | `sample_analytics` fixture |
| `tests/test_insights.py`, `tests/test_summaries.py`, `tests/test_summary_api.py` (create) | Tests |
| `web/src/lib/api.ts` (modify) | `InsightSummary` type, two client calls |
| `web/src/components/analytics/InsightsCard.tsx` (create) | The card |
| `web/src/components/analytics/AnalyticsTab.tsx` (modify) | Render the card under the tiles |
| `docs/PRD.md`, `docs/PRD-analytics.md` (modify) | Mark built; data model and API lists |

---

### Task 1: Facts, hash, prompt and grounding check

**Files:**
- Create: `src/piper_jobs/insights.py`
- Create: `tests/test_insights.py`
- Modify: `tests/conftest.py` (append the `sample_analytics` fixture)

**Interfaces:**
- Produces:
  - `PROMPT_VERSION = 1`, `MIN_APPLICATIONS = 10`, `MIN_GROUP = 5`
  - `build_facts(analytics: dict) -> list[str]` — takes the dict from `compute_analytics`
  - `facts_hash(facts: list[str], model: str, prompt_version: int = PROMPT_VERSION) -> str`
  - `build_messages(facts: list[str]) -> list[dict]` — Ollama chat messages (`system`, `user`)
  - `numbers_in(text: str) -> set[str]`, `is_grounded(summary: str, facts: list[str]) -> bool`
  - Test fixture `sample_analytics(total=24, **over) -> dict`

- [ ] **Step 1: Add the fixture** — append to `tests/conftest.py`

```python
@pytest.fixture
def sample_analytics():
    """A hand-built `compute_analytics` result: 24 applications, a clear LinkedIn-vs-ATS gap."""

    def make(total: int = 24, **over) -> dict:
        g = lambda key, count: {"key": key, "count": count, "ids": []}  # noqa: E731
        data = {
            "range": {"from": "2026-10-01", "to": "2026-10-30"},
            "summary": {
                "total": total, "previous_total": 18, "active_days": 15, "per_active_day": 1.6,
                "daily_average": 0.8, "last_7d_average": 1.1, "streak": 3, "longest_streak": 6,
                "best_day": {"date": "2026-10-12", "count": 4}, "this_week": 5, "last_week": 7,
            },
            "mix": {
                "category": [g("design", 6), g("product", 14), g("vc", 0), g("other", 4)],
                "source": [g("linkedin", 16), g("ats", 8)],
                "seniority": [g("senior", 10), g("unspecified", 14)],
            },
            "conversion": {
                "source": [
                    {"key": "linkedin", "total": 16, "responded": 0.0625, "interviewed": 0.0, "offers": 0, "median_days": None},
                    {"key": "ats", "total": 8, "responded": 0.375, "interviewed": 0.25, "offers": 0, "median_days": 4.0},
                ],
                "category": [
                    {"key": "product", "total": 14, "responded": 0.2143, "interviewed": 0.1429, "offers": 0, "median_days": 5.0},
                    {"key": "design", "total": 4, "responded": 0.5, "interviewed": 0.25, "offers": 0, "median_days": 3.0},
                ],
                "seniority": [],
            },
            "cohorts": [
                {"week": "2026-10-19", "total": 8, "responded": 0.25, "maturing": False},
                {"week": "2026-10-26", "total": 5, "responded": 0.0, "maturing": True},
            ],
            "response_time": {"buckets": [], "median": 4.5},
            "open_by_age": [g("0-7d", 5), g("15-21d", 3), g("22d+", 1)],
        }
        data.update(over)
        return data

    return make
```

(`pytest` is already imported at the top of `tests/conftest.py`.)

- [ ] **Step 2: Write the failing tests** — create `tests/test_insights.py`

```python
from piper_jobs.insights import (
    PROMPT_VERSION, build_facts, build_messages, facts_hash, is_grounded, numbers_in,
)


def test_facts_describe_pace_mix_and_conversion(sample_analytics):
    facts = build_facts(sample_analytics())
    assert facts[0] == "Applications from 2026-10-01 to 2026-10-30: 24 (previous period of the same length: 18)"
    assert "Role types: Product 58% (14), Design 25% (6), Other 17% (4)" in facts
    assert "Sources: LinkedIn 67% (16), Company site / ATS 33% (8)" in facts
    assert "Source LinkedIn: 16 applied, 6% replied, 0% interviewed" in facts
    assert "Highest reply rate by source: Company site / ATS; lowest: LinkedIn" in facts
    assert "Median time to a first reply: 4.5 days" in facts
    assert "The most recent 1 week of applications may still be waiting for replies" in facts
    assert "Open applications quiet for over two weeks: 4" in facts


def test_small_groups_are_left_out_of_conversion(sample_analytics):
    facts = build_facts(sample_analytics())
    assert not any(f.startswith("Role type Design") for f in facts)  # only 4 applications
    assert any(f.startswith("Role type Product") for f in facts)
    assert not any(f.startswith("Highest reply rate by role type") for f in facts)  # needs two big groups


def test_facts_skip_what_does_not_apply(sample_analytics):
    a = sample_analytics(response_time={"buckets": [], "median": None}, cohorts=[], open_by_age=[])
    a["summary"]["previous_total"] = None
    facts = build_facts(a)
    assert facts[0] == "Applications from 2026-10-01 to 2026-10-30: 24"
    assert not any(f.startswith(("Median", "The most recent", "Open applications")) for f in facts)


def test_facts_hash_depends_on_facts_model_and_prompt_version(sample_analytics):
    facts = build_facts(sample_analytics())
    key = facts_hash(facts, "qwen")
    assert key == facts_hash(list(facts), "qwen")
    assert key != facts_hash(facts, "llama")
    assert key != facts_hash(facts, "qwen", PROMPT_VERSION + 1)
    assert key != facts_hash([*facts, "one more"], "qwen")


def test_numbers_in():
    assert numbers_in("58% of 24, median 4.5 days") == {"58", "24", "4.5"}


def test_is_grounded_accepts_only_numbers_from_the_facts(sample_analytics):
    facts = build_facts(sample_analytics())
    assert is_grounded("You sent 24 applications, 58% of them Product.", facts)
    assert not is_grounded("You sent 26 applications.", facts)
    assert not is_grounded("   ", facts)


def test_messages_list_every_fact():
    messages = build_messages(["first 1", "second 2"])
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "- first 1\n- second 2" in messages[1]["content"]
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_insights.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'piper_jobs.insights'`.

- [ ] **Step 4: Implement** — create `src/piper_jobs/insights.py`

```python
"""Facts behind the written summary, and the checks around the model's reply. Pure: no I/O."""

from __future__ import annotations

import hashlib
import re

PROMPT_VERSION = 1  # bump when the prompt changes: older cached summaries are then discarded
MIN_APPLICATIONS = 10  # below this there is nothing worth summarising
MIN_GROUP = 5  # smaller groups are too small to compare

CATEGORY_LABEL = {"design": "Design", "product": "Product", "vc": "VC", "other": "Other"}
SOURCE_LABEL = {
    "linkedin": "LinkedIn", "ats": "Company site / ATS", "recruiter": "Recruiter",
    "direct": "Direct", "referral": "Referral", "other": "Other",
}
SENIORITY_LABEL = {
    "intern": "Intern", "junior": "Junior", "mid": "Mid", "senior": "Senior", "staff": "Staff / Principal",
    "lead": "Lead", "head": "Head / Director+", "unspecified": "Unspecified",
}

SYSTEM_PROMPT = (
    "You write a short summary of a person's job search for them. You are given facts, one per line. "
    "Write two to four plain sentences. Use only numbers that appear in the facts, copied exactly. "
    "Do not give advice or make predictions. If the most recent weeks may still be waiting for replies, "
    "say that recent reply rates may not be final. No bullet points, no headings."
)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _pct(rate: float) -> str:
    return f"{round(rate * 100)}%"


def _shares(groups: list[dict], labels: dict[str, str], top: int = 3) -> str | None:
    total = sum(g["count"] for g in groups)
    ranked = sorted((g for g in groups if g["count"]), key=lambda g: (-g["count"], g["key"]))[:top]
    if not total:
        return None
    return ", ".join(f"{labels.get(g['key'], g['key'])} {_pct(g['count'] / total)} ({g['count']})" for g in ranked)


def build_facts(a: dict) -> list[str]:
    s = a["summary"]
    first = f"Applications from {a['range']['from'] or 'the start'} to {a['range']['to']}: {s['total']}"
    if s["previous_total"] is not None:
        first += f" (previous period of the same length: {s['previous_total']})"
    facts = [
        first,
        f"Pace: {s['daily_average']} a day on average, {s['per_active_day']} on the {s['active_days']} days "
        f"with an application; current streak {s['streak']} days, longest {s['longest_streak']}",
        f"This week: {s['this_week']}, last week: {s['last_week']}",
    ]
    for title, key, labels in (("Role types", "category", CATEGORY_LABEL), ("Sources", "source", SOURCE_LABEL),
                               ("Seniority", "seniority", SENIORITY_LABEL)):
        if text := _shares(a["mix"][key], labels):
            facts.append(f"{title}: {text}")
    for title, key, labels in (("Source", "source", SOURCE_LABEL), ("Role type", "category", CATEGORY_LABEL)):
        groups = [g for g in a["conversion"][key] if g["total"] >= MIN_GROUP]
        for g in groups:
            facts.append(f"{title} {labels.get(g['key'], g['key'])}: {g['total']} applied, "
                         f"{_pct(g['responded'])} replied, {_pct(g['interviewed'])} interviewed")
        if len(groups) >= 2:
            best = max(groups, key=lambda g: g["responded"])
            worst = min(groups, key=lambda g: g["responded"])
            if best["responded"] != worst["responded"]:
                facts.append(f"Highest reply rate by {title.lower()}: {labels.get(best['key'], best['key'])}; "
                             f"lowest: {labels.get(worst['key'], worst['key'])}")
    if (median := a["response_time"]["median"]) is not None:
        facts.append(f"Median time to a first reply: {median} days")
    if maturing := sum(1 for c in a["cohorts"] if c["maturing"]):
        facts.append(f"The most recent {maturing} week{'s' if maturing != 1 else ''} of applications "
                     "may still be waiting for replies")
    if quiet := sum(b["count"] for b in a["open_by_age"] if b["key"] in ("15-21d", "22d+")):
        facts.append(f"Open applications quiet for over two weeks: {quiet}")
    return facts


def facts_hash(facts: list[str], model: str, prompt_version: int = PROMPT_VERSION) -> str:
    raw = "\n".join([model, str(prompt_version), *facts])
    return hashlib.sha256(raw.encode()).hexdigest()


def build_messages(facts: list[str]) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Facts:\n" + "\n".join(f"- {f}" for f in facts)},
    ]


def numbers_in(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def is_grounded(summary: str, facts: list[str]) -> bool:
    """The reply is non-empty and uses no number that is not in the facts."""
    return bool(summary.strip()) and numbers_in(summary) <= numbers_in("\n".join(facts))
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_insights.py -q`
Expected: 7 passed. (`round(37.5)` is 38 and `round(66.67)` is 67 in Python; the LinkedIn/ATS shares in the first test were computed from these.)

- [ ] **Step 6: Commit**

```bash
git add src/piper_jobs/insights.py tests/test_insights.py tests/conftest.py
git commit -m "feat(insights): facts, cache key, prompt and grounding check for the written summary"
```

---

### Task 2: Summary table and cache store

**Files:**
- Modify: `src/piper_jobs/db.py` (new table class, after `SavedView`)
- Create: `src/piper_jobs/summaries.py` (store functions only in this task)
- Create: `tests/test_summaries.py`

**Interfaces:**
- Consumes: `utcnow`, `get_engine` from `db.py`; `settings`/`session` fixtures from `tests/conftest.py`.
- Produces:
  - `InsightSummary` table model (`hash` primary key, `text`, `model`, `prompt_version`, `created_at`, `last_used_at`).
  - `MAX_ENTRIES = 50`
  - `get_cached(session, key) -> str | None` (updates `last_used_at`)
  - `save(session, key, text, model, prompt_version) -> None` (replaces an existing entry, then prunes)
  - `delete_cached(session, key) -> None`
  - `prune_excess(session, keep=MAX_ENTRIES) -> None`
  - `prune_stale(session, model, prompt_version) -> None`

- [ ] **Step 1: Write the failing tests** — create `tests/test_summaries.py`

```python
from datetime import timedelta

from sqlmodel import select

from piper_jobs.db import InsightSummary, utcnow
from piper_jobs.summaries import (
    MAX_ENTRIES, delete_cached, get_cached, prune_excess, prune_stale, save,
)


def test_save_then_get_returns_text_and_marks_it_used(session):
    save(session, "k", "hello", "qwen", 1)
    row = session.get(InsightSummary, "k")
    row.last_used_at = utcnow() - timedelta(days=3)
    session.add(row)
    session.commit()
    assert get_cached(session, "k") == "hello"
    assert session.get(InsightSummary, "k").last_used_at > utcnow() - timedelta(minutes=1)


def test_get_missing_returns_none(session):
    assert get_cached(session, "nope") is None


def test_saving_again_replaces_the_text(session):
    save(session, "k", "first", "qwen", 1)
    save(session, "k", "second", "qwen", 1)
    assert get_cached(session, "k") == "second"
    assert len(session.exec(select(InsightSummary)).all()) == 1


def test_delete_cached(session):
    save(session, "k", "hello", "qwen", 1)
    delete_cached(session, "k")
    delete_cached(session, "never-saved")  # no error
    assert get_cached(session, "k") is None


def test_prune_excess_keeps_the_most_recently_used(session):
    now = utcnow()
    for i in range(MAX_ENTRIES + 5):
        session.add(InsightSummary(hash=f"k{i}", text="t", model="m", prompt_version=1,
                                   created_at=now, last_used_at=now - timedelta(minutes=i)))
    session.commit()
    prune_excess(session)
    kept = {r.hash for r in session.exec(select(InsightSummary)).all()}
    assert len(kept) == MAX_ENTRIES
    assert "k0" in kept and f"k{MAX_ENTRIES + 4}" not in kept


def test_saving_prunes_beyond_the_limit(session):
    now = utcnow()
    for i in range(MAX_ENTRIES):
        session.add(InsightSummary(hash=f"k{i}", text="t", model="m", prompt_version=1,
                                   created_at=now, last_used_at=now - timedelta(hours=1, minutes=i)))
    session.commit()
    save(session, "fresh", "new", "m", 1)
    assert len(session.exec(select(InsightSummary)).all()) == MAX_ENTRIES
    assert get_cached(session, "fresh") == "new"


def test_prune_stale_removes_other_models_and_prompt_versions(session):
    save(session, "keep", "t", "qwen", 2)
    save(session, "old-model", "t", "llama", 2)
    save(session, "old-prompt", "t", "qwen", 1)
    prune_stale(session, "qwen", 2)
    assert {r.hash for r in session.exec(select(InsightSummary)).all()} == {"keep"}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_summaries.py -q`
Expected: FAIL — `ImportError: cannot import name 'InsightSummary'` (or no module `summaries`).

- [ ] **Step 3: Add the table** — in `src/piper_jobs/db.py`, after the `SavedView` class:

```python
class InsightSummary(SQLModel, table=True):
    __tablename__ = "insight_summaries"
    hash: str = Field(primary_key=True)  # of the facts + model + prompt version
    text: str
    model: str
    prompt_version: int
    created_at: NaiveDatetime = Field(default_factory=utcnow)
    last_used_at: NaiveDatetime = Field(default_factory=utcnow)
```

(`create_all` adds the new table to existing databases on startup; no entry in `_ADDED_COLUMNS` is needed.)

- [ ] **Step 4: Implement the store** — create `src/piper_jobs/summaries.py`

```python
"""The written summary: a small cache of model replies, and the service that decides when to ask the model."""

from __future__ import annotations

from sqlmodel import Session, select

from .db import InsightSummary, utcnow

MAX_ENTRIES = 50


def get_cached(session: Session, key: str) -> str | None:
    row = session.get(InsightSummary, key)
    if row is None:
        return None
    row.last_used_at = utcnow()
    session.add(row)
    session.commit()
    return row.text


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
    rows = session.exec(select(InsightSummary).order_by(InsightSummary.last_used_at.desc())).all()
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
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_summaries.py -q`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add src/piper_jobs/db.py src/piper_jobs/summaries.py tests/test_summaries.py
git commit -m "feat(insights): summary cache table with a 50-entry least-recently-used limit"
```

---

### Task 3: SummaryService

**Files:**
- Modify: `src/piper_jobs/summaries.py` (append the service)
- Modify: `tests/test_summaries.py` (append service tests)

**Interfaces:**
- Consumes: Task 1 (`build_facts`, `facts_hash`, `build_messages`, `is_grounded`, `MIN_APPLICATIONS`, `PROMPT_VERSION`), Task 2 store functions, `Settings` (`ollama_host`, `ollama_model`).
- Produces:
  - Constants `DEBOUNCE_SECONDS = 10`, `RETRY_AFTER_SECONDS = 300`, `VARIANT_TEMPERATURE = 0.6`.
  - `ollama_generate(settings) -> Callable[[list[dict], float], str]`.
  - `SummaryService(settings, engine, is_syncing, generate=None, spawn=None, clock=time.monotonic)` with public attributes `generate`, `spawn`, `clock`, `debounce` (assignable in tests), and:
    - `status(analytics: dict) -> dict` → `{"status": "ready" | "pending" | "insufficient_data" | "fallback", "text": str | None, "facts": list[str]}`
    - `refresh(analytics: dict) -> dict` — same shape; drops the cached text for these facts, skips the quiet period, and asks for different wording.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_summaries.py`

Add these imports at the top of the file (merge with the existing ones):

```python
import pytest

from piper_jobs.db import get_engine
from piper_jobs.insights import MIN_APPLICATIONS, PROMPT_VERSION, build_facts, facts_hash
from piper_jobs.summaries import DEBOUNCE_SECONDS, RETRY_AFTER_SECONDS, SummaryService
```

Then append:

```python
class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Recorder:
    """A fake model: records calls, replies with a grounded sentence unless told otherwise."""

    def __init__(self, reply="You sent 24 applications.", error=None):
        self.reply, self.error, self.temperatures = reply, error, []

    def __call__(self, messages, temperature):
        self.temperatures.append(temperature)
        if self.error:
            raise self.error
        return self.reply

    @property
    def calls(self):
        return len(self.temperatures)


@pytest.fixture
def make_service(settings):
    def make(model, syncing=lambda: False):
        clock = Clock()
        svc = SummaryService(settings, get_engine(settings.db_path), is_syncing=syncing, generate=model,
                             spawn=lambda fn: fn(), clock=clock)
        return svc, clock

    return make


def test_too_few_applications_calls_no_model(make_service, sample_analytics):
    model = Recorder()
    svc, clock = make_service(model)
    result = svc.status(sample_analytics(total=MIN_APPLICATIONS - 1))
    clock.now += 60
    svc.status(sample_analytics(total=MIN_APPLICATIONS - 1))
    assert result["status"] == "insufficient_data" and result["text"] is None
    assert model.calls == 0


def test_waits_for_the_quiet_period_then_generates(make_service, sample_analytics):
    model = Recorder()
    svc, clock = make_service(model)
    a = sample_analytics()
    first = svc.status(a)
    assert first["status"] == "pending" and first["facts"] == build_facts(a)
    clock.now += DEBOUNCE_SECONDS - 1
    assert svc.status(a)["status"] == "pending" and model.calls == 0
    clock.now += 2
    assert svc.status(a)["status"] == "pending" and model.calls == 1  # started now
    done = svc.status(a)
    assert done["status"] == "ready" and done["text"] == "You sent 24 applications."
    assert model.calls == 1


def test_a_cached_summary_calls_no_model(make_service, sample_analytics, session, settings):
    a = sample_analytics()
    save(session, facts_hash(build_facts(a), settings.ollama_model), "Cached text.", settings.ollama_model, PROMPT_VERSION)
    model = Recorder()
    svc, _ = make_service(model)
    assert svc.status(a) == {"status": "ready", "text": "Cached text.", "facts": build_facts(a)}
    assert model.calls == 0


def test_nothing_is_generated_during_a_sync(make_service, sample_analytics):
    model, syncing = Recorder(), [True]
    svc, clock = make_service(model, syncing=lambda: syncing[0])
    a = sample_analytics()
    svc.status(a)
    clock.now += 60
    assert svc.status(a)["status"] == "pending" and model.calls == 0
    syncing[0] = False
    svc.status(a)
    assert model.calls == 1  # no new quiet period once the sync is over


def test_a_reply_with_unknown_numbers_is_not_used(make_service, sample_analytics):
    model = Recorder(reply="You sent 99 applications.")
    svc, clock = make_service(model)
    a = sample_analytics()
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS
    svc.status(a)  # generates; the reply fails the check
    result = svc.status(a)
    assert result["status"] == "fallback" and result["text"] is None and result["facts"] == build_facts(a)
    svc.status(a)
    assert model.calls == 1  # not retried straight away
    clock.now += RETRY_AFTER_SECONDS + 1
    assert svc.status(a)["status"] == "pending"  # allowed to try again, after a new quiet period


def test_a_model_error_falls_back(make_service, sample_analytics):
    svc, clock = make_service(Recorder(error=ConnectionError("ollama is not running")))
    a = sample_analytics()
    svc.status(a)
    clock.now += DEBOUNCE_SECONDS
    svc.status(a)
    assert svc.status(a)["status"] == "fallback"


def test_changed_facts_get_their_own_summary(make_service, sample_analytics):
    model = Recorder(reply="You sent 24 applications.")
    svc, clock = make_service(model)
    a, b = sample_analytics(), sample_analytics()
    b["summary"]["this_week"] = 9
    for data in (a, b):
        svc.status(data)
        clock.now += DEBOUNCE_SECONDS
        svc.status(data)
        assert svc.status(data)["status"] == "ready"
    assert model.calls == 2


def test_refresh_asks_again_with_different_wording(make_service, sample_analytics, session, settings):
    a = sample_analytics()
    save(session, facts_hash(build_facts(a), settings.ollama_model), "Old text.", settings.ollama_model, PROMPT_VERSION)
    model = Recorder(reply="You sent 24 jobs.")
    svc, _ = make_service(model)
    svc.refresh(a)  # no quiet period
    assert model.temperatures == [0.6]
    assert svc.status(a) == {"status": "ready", "text": "You sent 24 jobs.", "facts": build_facts(a)}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_summaries.py -q`
Expected: the store tests pass; the new tests FAIL with `ImportError: cannot import name 'SummaryService'`.

- [ ] **Step 3: Implement** — in `src/piper_jobs/summaries.py` replace the imports block at the top with the following, and append the service below the store functions.

```python
import logging
import threading
import time
from collections.abc import Callable

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from .config import Settings
from .db import InsightSummary, utcnow
from .insights import MIN_APPLICATIONS, PROMPT_VERSION, build_facts, build_messages, facts_hash, is_grounded

log = logging.getLogger(__name__)
```

```python
DEBOUNCE_SECONDS = 10  # the same facts must be requested this long before the model is asked
RETRY_AFTER_SECONDS = 300  # after a failed or ungrounded reply
VARIANT_TEMPERATURE = 0.6  # "write it again" must not return the same words
_MAX_TRACKED = 100


def ollama_generate(settings: Settings) -> Callable[[list[dict], float], str]:
    def generate(messages: list[dict], temperature: float) -> str:
        import ollama

        reply = ollama.Client(host=settings.ollama_host).chat(
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
        with self._lock:
            failed_at = self._failed.get(key)
            if failed_at is not None and now - failed_at < RETRY_AFTER_SECONDS:
                return {"status": "fallback", "text": None, "facts": facts}
            if len(self._first_seen) > _MAX_TRACKED:
                self._first_seen.clear()
            first = self._first_seen.setdefault(key, now)
            start = self._running is None and not self.is_syncing() and now - first >= self.debounce
            if start:
                self._running = key
        if start:
            self.spawn(lambda: self._generate(key, facts))
        return {"status": "pending", "text": None, "facts": facts}

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
        return self.status(analytics)

    def _generate(self, key: str, facts: list[str]) -> None:
        try:
            temperature = VARIANT_TEMPERATURE if key in self._variant else 0.0
            text = self.generate(build_messages(facts), temperature).strip()
            if not is_grounded(text, facts):
                raise ValueError("the summary used numbers that are not in the facts")
            with Session(self.engine) as session:
                save(session, key, text, self.model, PROMPT_VERSION)
        except Exception as exc:  # the model being down must never break the page: show the facts instead
            log.warning("Could not write the summary: %s", exc)
            with self._lock:
                self._failed[key] = self.clock()
        finally:
            with self._lock:
                self._running = None
                self._first_seen.pop(key, None)
                self._variant.discard(key)
```

Note: a summary that finishes after the facts have changed is saved under its own hash, so it is never shown against different numbers (spec §6.9).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_summaries.py -q`
Expected: 15 passed. If `test_a_reply_with_unknown_numbers_is_not_used` fails at the last assertion, remember `_generate` pops `_first_seen` in `finally`, so after the retry window the next `status` starts a new quiet period and returns `pending`.

- [ ] **Step 5: Commit**

```bash
git add src/piper_jobs/summaries.py tests/test_summaries.py
git commit -m "feat(insights): SummaryService with quiet period, sync hold-off and fallback"
```

---

### Task 4: Endpoints and startup clean-up

**Files:**
- Modify: `src/piper_jobs/api.py`
- Create: `tests/test_summary_api.py`

**Interfaces:**
- Consumes: Task 3 `SummaryService`; Task 2 `prune_stale`; Task 1 `PROMPT_VERSION`; the existing `/api/analytics` route body, `get_filters`, `session_dep`, `runner`, `engine`.
- Produces:
  - Refactor: a local helper `analytics_data(session, filters, granularity, tz_offset) -> dict` inside `create_app`, used by `/api/analytics` unchanged in behaviour.
  - `app.state.summaries: SummaryService`
  - `GET /api/analytics/summary?<shared filters>&tz_offset=` → status dict
  - `POST /api/analytics/summary/refresh?<shared filters>&tz_offset=` → status dict
  - At app creation, `prune_stale(session, settings.ollama_model, PROMPT_VERSION)` runs once.

- [ ] **Step 1: Write the failing tests** — create `tests/test_summary_api.py`

```python
import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from piper_jobs.api import create_app
from piper_jobs.db import InsightSummary, get_engine, utcnow
from piper_jobs.insights import PROMPT_VERSION
from piper_jobs.resolver import apply_event


@pytest.fixture
def client(settings):
    now = utcnow()
    with Session(get_engine(settings.db_path)) as s:
        for i in range(12):
            apply_event(s, company=f"Company{i}", role="Product Designer", stage="applied",
                        source="linkedin", occurred_at=now - timedelta(days=i + 1))
        s.commit()
    with TestClient(create_app(settings)) as c:
        temperatures = []

        def generate(messages, temperature):
            temperatures.append(temperature)
            total = re.search(r"Applications from .*?: (\d+)", messages[-1]["content"]).group(1)
            return f"You sent {total} applications."

        svc = c.app.state.summaries
        svc.generate, svc.spawn, svc.debounce = generate, (lambda fn: fn()), 0
        c.temperatures = temperatures
        yield c


def test_summary_is_generated_once_then_served_from_the_cache(client):
    params = {"range": "all"}
    first = client.get("/api/analytics/summary", params=params).json()
    assert first["status"] == "pending" and first["facts"]
    ready = client.get("/api/analytics/summary", params=params).json()
    assert ready["status"] == "ready" and ready["text"] == "You sent 12 applications."
    client.get("/api/analytics/summary", params=params)
    assert client.temperatures == [0.0]


def test_too_few_applications_in_the_view(client):
    data = client.get("/api/analytics/summary", params={"range": "all", "q": "Company1"}).json()
    assert data["status"] == "insufficient_data"  # Company1, Company10, Company11
    assert client.temperatures == []


def test_refresh_writes_it_again_with_different_wording(client):
    params = {"range": "all"}
    client.get("/api/analytics/summary", params=params)
    client.get("/api/analytics/summary", params=params)
    client.post("/api/analytics/summary/refresh", params=params)
    assert client.temperatures == [0.0, 0.6]
    assert client.get("/api/analytics/summary", params=params).json()["status"] == "ready"


def test_invalid_tz_offset_is_rejected(client):
    assert client.get("/api/analytics/summary", params={"tz_offset": 99999}).status_code == 422


def test_startup_removes_summaries_of_other_models(settings):
    with Session(get_engine(settings.db_path)) as s:
        s.add(InsightSummary(hash="old", text="t", model="some-other-model", prompt_version=PROMPT_VERSION))
        s.add(InsightSummary(hash="new", text="t", model=settings.ollama_model, prompt_version=PROMPT_VERSION))
        s.commit()
    with TestClient(create_app(settings)):
        pass
    with Session(get_engine(settings.db_path)) as s:
        assert s.get(InsightSummary, "old") is None
        assert s.get(InsightSummary, "new") is not None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_summary_api.py -q`
Expected: FAIL — `AttributeError: 'State' object has no attribute 'summaries'` / 404.

- [ ] **Step 3: Implement** — in `src/piper_jobs/api.py`:

Add the imports:

```python
from .insights import PROMPT_VERSION
from .summaries import SummaryService, prune_stale
```

Right after `app.state.runner = runner` (inside `create_app`), add:

```python
    with Session(engine) as s:
        prune_stale(s, settings.ollama_model, PROMPT_VERSION)
    app.state.summaries = SummaryService(settings, engine, lambda: runner.running)
```

(`engine` is the SQLAlchemy engine `create_app` already builds for `session_dep`; read the top of `create_app` for its exact name.)

Replace the existing `/api/analytics` route with a shared helper plus three routes:

```python
    def analytics_data(session: Session, filters: Filters, granularity: str, tz_offset: int) -> dict:
        now = utcnow()
        # The window comes from the UTC date, like every other endpoint, so totals agree across tabs.
        start, end = filters.date_bounds(now.date())
        previous = previous_filters(filters, now.date())
        previous_total = len(rows_for(session, previous)) if previous else None
        return compute_analytics(rows_for(session, filters), now, tz_offset, granularity, start, end, previous_total)

    @app.get("/api/analytics")
    def analytics(
        filters: Filters = Depends(get_filters),
        granularity: Literal["day", "week", "month"] = "day",
        tz_offset: int = Query(0, ge=-840, le=840),  # minutes ahead of UTC, so days match the user's
        session: Session = Depends(session_dep),
    ):
        return analytics_data(session, filters, granularity, tz_offset)

    @app.get("/api/analytics/summary")
    def analytics_summary(
        filters: Filters = Depends(get_filters),
        tz_offset: int = Query(0, ge=-840, le=840),
        session: Session = Depends(session_dep),
    ):
        return app.state.summaries.status(analytics_data(session, filters, "day", tz_offset))

    @app.post("/api/analytics/summary/refresh")
    def analytics_summary_refresh(
        filters: Filters = Depends(get_filters),
        tz_offset: int = Query(0, ge=-840, le=840),
        session: Session = Depends(session_dep),
    ):
        return app.state.summaries.refresh(analytics_data(session, filters, "day", tz_offset))
```

If the existing `/api/analytics` body already uses `now.date()` for the window, keep exactly that behaviour inside `analytics_data`; do not change the numbers it returns.

- [ ] **Step 4: Run the whole backend suite**

Run: `uv run pytest -q`
Expected: all pass, including `tests/test_analytics_api.py` (the refactor must not change `/api/analytics`).

- [ ] **Step 5: Commit**

```bash
git add src/piper_jobs/api.py tests/test_summary_api.py
git commit -m "feat(insights): summary endpoints and startup clean-up"
```

---

### Task 5: Insights card

**Files:**
- Modify: `web/src/lib/api.ts`
- Create: `web/src/components/analytics/InsightsCard.tsx`
- Modify: `web/src/components/analytics/AnalyticsTab.tsx`

**Interfaces:**
- Consumes: Task 4 endpoints; existing `Section`, `Button`, `filterParams`, `http`.
- Produces: `InsightSummary` type; `api.analyticsSummary(f, tzOffset?)`, `api.refreshAnalyticsSummary(f, tzOffset?)`; `InsightsCard({ filters })`.

- [ ] **Step 1: Client** — in `web/src/lib/api.ts` add next to the other analytics types:

```ts
export interface InsightSummary {
  status: "ready" | "pending" | "insufficient_data" | "fallback";
  text: string | null;
  facts: string[];
}
```

and in the `api` object after `analytics`:

```ts
  analyticsSummary: (f: Filters, tzOffset = -new Date().getTimezoneOffset()) => {
    const p = filterParams(f);
    p.set("tz_offset", String(tzOffset));
    return http<InsightSummary>(`/api/analytics/summary?${p}`);
  },
  refreshAnalyticsSummary: (f: Filters, tzOffset = -new Date().getTimezoneOffset()) => {
    const p = filterParams(f);
    p.set("tz_offset", String(tzOffset));
    return http<InsightSummary>(`/api/analytics/summary/refresh?${p}`, { method: "POST" });
  },
```

- [ ] **Step 2: The card** — create `web/src/components/analytics/InsightsCard.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Filters } from "../../lib/api";
import { Button } from "../ui";
import { Section } from "./Section";

const POLL_MS = 3000;

function Facts({ facts }: { facts: string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
      {facts.map((f) => (
        <li key={f}>{f}</li>
      ))}
    </ul>
  );
}

/** A short written summary of the view, from the local model. While it is being written, or if it
 * cannot be, the plain numbers it is based on are shown instead. */
export function InsightsCard({ filters }: { filters: Filters }) {
  const queryClient = useQueryClient();
  const queryKey = ["analytics", "summary", filters]; // starts with "analytics", so data changes refresh it
  const { data } = useQuery({
    queryKey,
    queryFn: () => api.analyticsSummary(filters),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? POLL_MS : false),
  });
  const refresh = useMutation({
    mutationFn: () => api.refreshAnalyticsSummary(filters),
    onSuccess: (result) => queryClient.setQueryData(queryKey, result),
  });

  if (!data) {
    return (
      <Section title="Insights">
        <div className="h-12" />
      </Section>
    );
  }
  const action =
    data.status === "ready" ? (
      <Button onClick={() => refresh.mutate()} title="Write it again with different wording" className="h-7 px-2">
        ↻
      </Button>
    ) : undefined;
  return (
    <Section
      title="Insights"
      hint={data.status === "ready" ? "Written by your local model from the numbers on this page" : undefined}
      right={action}
    >
      {data.status === "ready" && <p className="text-sm leading-relaxed text-ink">{data.text}</p>}
      {data.status === "insufficient_data" && (
        <p className="text-sm text-ink-2">A summary appears once there are at least 10 applications in this view.</p>
      )}
      {data.status === "pending" && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted">Writing a summary…</p>
          <Facts facts={data.facts} />
        </div>
      )}
      {data.status === "fallback" && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted">A summary could not be written just now, so here are the numbers.</p>
          <Facts facts={data.facts} />
        </div>
      )}
    </Section>
  );
}
```

- [ ] **Step 3: Show it** — in `AnalyticsTab.tsx` add `import { InsightsCard } from "./InsightsCard";` and render `<InsightsCard filters={filters} />` directly under `<SummaryTiles s={data?.summary} />`.

- [ ] **Step 4: Build**

Run (from `web/`): `npm run build`
Expected: `tsc` clean and the Vite build succeeds. If `Button` does not accept `className`, drop that prop (look at `web/src/components/ui.tsx`).

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(insights): Insights card on the Analytics tab"
```

---

### Task 6: Docs and a check against the real model

**Files:**
- Modify: `docs/PRD-analytics.md`, `docs/PRD.md`

- [ ] **Step 1: Spec wording** — in `docs/PRD-analytics.md` §6.9:
  - change the heading to `### 6.9 Written summary`;
  - replace "the result is discarded rather than shown against the wrong numbers" with "the result is saved under its own facts and is only ever shown for those facts";
  - add one sentence: "If the model cannot be reached, the card shows the facts (`fallback`) and does not retry for 5 minutes."

- [ ] **Step 2: Main PRD** — in `docs/PRD.md`: add `insight_summaries(hash, text, model, prompt_version, created_at, last_used_at)` to the §8 data model list; add `GET /api/analytics/summary` and `POST /api/analytics/summary/refresh` to §9; extend §6.15 with one sentence about the written summary.

- [ ] **Step 3: Try it for real** (never touch the real `~/.piper`)

PowerShell:

```powershell
$env:PIPER_HOME = "$env:TEMP\piper-summary-demo"
uv run piper seed --force
uv run piper doctor
uv run piper ui --browser --port 8766
```

Open the Analytics tab and check:
1. The card first shows "Writing a summary…" with the numbers, then within a few seconds the written text.
2. Reloading the page shows the text immediately (cache hit).
3. Switching the range to 30d and back to the original shows each summary instantly the second time.
4. ↻ replaces the text with different wording.
5. Every number in the text appears in the numbers above (shown while pending). If a reply is rejected, the card falls back to the bullet list; note how often that happens with the default model.
6. Stop Ollama, change the range to a new one: the card ends in "A summary could not be written just now" with the numbers.

- [ ] **Step 4: Commit**

```bash
git add docs
git commit -m "docs: document the written summary"
```

---

## Self-review (spec coverage, §6.9)

| Spec line | Task |
|---|---|
| Model writes, app calculates; facts only | 1 |
| Number check, plain-bullet fallback | 1 (`is_grounded`), 3 (fallback), 5 (UI) |
| Under 10 applications: no model call | 3 |
| Automatic and cached, hash of facts + model + prompt version | 1, 2, 3 |
| Shown instantly when cached; facts shown while pending | 3, 5 |
| No generation during a sync; resumes after | 3 |
| 10-second quiet period; one summary per burst | 3 |
| Refresh control, different wording | 3, 4, 5 |
| Entries of another model/prompt deleted at startup; 50 most recent kept | 2, 4 |
| New table; API shape and statuses | 2, 4 |
| Result for changed facts never shown for other numbers | 3 (keyed by hash) |
