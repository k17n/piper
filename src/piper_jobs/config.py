"""Settings, loaded from env vars > ~/.piper/.env > ./.env."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# Job boards, ATS vendors and scheduling tools: always searched, never "followed" as a company domain.
JOB_PLATFORMS = [
    "linkedin.com", "greenhouse.io", "lever.co", "myworkday.com", "workday.com", "ashbyhq.com",
    "smartrecruiters.com", "icims.com", "naukri.com", "instahyre.com", "wellfound.com", "angel.co",
    "workable.com", "recruitee.com", "teamtailor.com", "breezy.hr", "jobvite.com", "zohorecruit.com",
    "keka.com", "darwinbox.in", "cutshort.io", "hirist.tech", "ycombinator.com", "calendly.com",
]
SUBJECT_TERMS = [
    "application", "applying", "interview", "unfortunately", "offer", "assessment", "candidacy",
    "candidature", "shortlisted", '"next steps"', "invitation", '"appointment booked"',
    '"take-home"', '"case study"', '"design challenge"', "assignment",
]
GMAIL_QUERY = f"(from:({' OR '.join(JOB_PLATFORMS)}) OR subject:({' OR '.join(SUBJECT_TERMS)}))"


LEGACY_DATA_DIR = Path.home() / ".jobtracker"  # the folder used before the app was named Piper


def default_data_dir() -> Path:
    if os.environ.get("PIPER_HOME"):
        return Path(os.environ["PIPER_HOME"])
    path = Path.home() / ".piper"
    migrate_legacy_data_dir(LEGACY_DATA_DIR, path)
    return path


def migrate_legacy_data_dir(old: Path, new: Path) -> bool:
    """Move the pre-rename data folder (database, Gmail token, settings) to its new home, once."""
    if new.exists() or not old.is_dir():
        return False
    shutil.move(str(old), str(new))
    return True


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


@dataclass
class Settings:
    data_dir: Path
    llm_provider: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    anthropic_api_key: str = ""
    anthropic_model: str = ""
    ghost_days: int = 30
    sync_interval_hours: float = 6
    backfill_days: int = 180
    gmail_query: str = GMAIL_QUERY
    gmail_extra_query: str = ""  # OR-ed into the main search, e.g. 'from:acme.com OR subject:"portfolio"'
    include_sent_threads: bool = True  # whole threads you sent mail in (direct outreach)
    follow_company_domains: bool = True  # all mail from domains of companies you're talking to
    always_include: list[str] = field(default_factory=list)  # domains / addresses: always searched + kept
    always_ignore: list[str] = field(default_factory=list)  # domains / addresses: always dropped
    never_job_subjects: list[str] = field(default_factory=list)  # your own patterns, from never_job_subjects.txt

    def filter_signature(self, rules_version: str) -> str:
        """Changes whenever the set of emails we'd look at could change → triggers a full re-scan."""
        payload = [self.gmail_query, self.gmail_extra_query, self.include_sent_threads,
                   self.follow_company_domains, sorted(self.always_include), sorted(self.always_ignore),
                   self.never_job_subjects,
                   self.backfill_days, rules_version]
        return hashlib.sha1(json.dumps(payload).encode()).hexdigest()[:16]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobs.db"

    @property
    def token_path(self) -> Path:
        return self.data_dir / "token.json"

    @property
    def credentials_path(self) -> Path:
        local = Path.cwd() / "credentials.json"
        preferred = self.data_dir / "credentials.json"
        return local if local.is_file() and not preferred.is_file() else preferred


def load_settings(data_dir: Path | str | None = None) -> Settings:
    root = Path(data_dir) if data_dir else default_data_dir()
    env = {**_read_env_file(Path.cwd() / ".env"), **_read_env_file(root / ".env"), **os.environ}

    def get(key: str, default):
        raw = env.get(key)
        if raw in (None, ""):
            return default
        if isinstance(default, bool):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        if isinstance(default, list):
            return [x.strip().lower() for x in raw.split(",") if x.strip()]
        return type(default)(raw)

    defaults = Settings(data_dir=root)
    return Settings(
        data_dir=root,
        llm_provider=get("LLM_PROVIDER", defaults.llm_provider).lower(),
        ollama_host=get("OLLAMA_HOST", defaults.ollama_host),
        ollama_model=get("OLLAMA_MODEL", defaults.ollama_model),
        anthropic_api_key=get("ANTHROPIC_API_KEY", ""),
        anthropic_model=get("ANTHROPIC_MODEL", ""),
        ghost_days=get("GHOST_DAYS", defaults.ghost_days),
        sync_interval_hours=get("SYNC_INTERVAL_HOURS", defaults.sync_interval_hours),
        backfill_days=get("BACKFILL_DAYS", defaults.backfill_days),
        gmail_query=get("GMAIL_QUERY", defaults.gmail_query),
        gmail_extra_query=get("GMAIL_EXTRA_QUERY", ""),
        include_sent_threads=get("INCLUDE_SENT_THREADS", defaults.include_sent_threads),
        follow_company_domains=get("FOLLOW_COMPANY_DOMAINS", defaults.follow_company_domains),
        always_include=get("ALWAYS_INCLUDE", []),
        always_ignore=get("ALWAYS_IGNORE", []),
        never_job_subjects=_read_patterns(root / "never_job_subjects.txt"),
    )


def _read_patterns(path: Path) -> list[str]:
    """One regular expression per line (case-insensitive); blank lines and # comments ignored."""
    if not path.is_file():
        return []
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]
