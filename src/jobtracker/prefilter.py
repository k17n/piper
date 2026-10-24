"""Cheap rule-based filter that runs before the LLM to drop alerts, digests and marketing."""

from __future__ import annotations

import re
from email.utils import parseaddr
from functools import lru_cache

from .schema import RawEmail

# Bump when the rules below change: the next sync re-checks emails that were skipped before.
RULES_VERSION = 5

# Checked before anything else, on the subject: never an application update, whatever the body says.
NEVER_JOB_SUBJECT = [
    r"verify your new device",
    r"confirm your identity",
    r"security alert",
    r"new sign-?in",
    r"sign-?in attempt",
    r"verification code",
    r"\b\d-digit code\b",
    r"\b(otp|one[- ]time (pass(word|code)|code))\b",
    r"^\[github\]",
    r"oauth application",
    r"\bipo application",
    r"\b(e?mba|executive mba)\b",
    r"credit card",
    r"application deadline",
    r"submit your application before",
    r"^welcome to\b",
    # LinkedIn nudges and promos
    r"\bapply now to\b",
    r"\bapply to .+ and more\b",
    r"^.{0,40}, apply to\b",
    r"job.s expiring",
    r"saved job is expiring",
    r"open to work",
    # applications that were started but never submitted
    r"application is incomplete",
    r"complete your (job )?application",
]

# Checked next, anywhere in subject or body: these are always real application updates.
STRONG_KEEP = [
    r"your application was sent to",
    r"your application was viewed by",
    r"thanks? (you )?for (applying|your application|your interest in)",
    r"(we('ve| have)? )?received your application",
    r"application (received|submitted|confirmation)",
]

DROP_FROM = [
    r"jobalerts-noreply@linkedin\.com",
    r"jobs-listings@linkedin\.com",
    r"news(letters?)?@",
    r"marketing@",
    r"invitations@linkedin\.com",
    r"groups-noreply@linkedin\.com",
]

DROP_SUBJECT = [
    r"jobs? you may be interested in",
    r"job alert",
    r"\bnew jobs?\b",
    r"\d+\+? (new )?jobs?\b",
    r"jobs? for you",
    r"recommended (jobs?|for you)",
    r"top job picks",
    r"\bis hiring\b",
    r"\bare hiring\b",
    r"newsletter",
    r"webinar",
    r"\d+% off",
    r"who viewed your profile",
    r"appeared in \d+ searches",
    r"your weekly",
    r"premium",
]

_never = [re.compile(p, re.I) for p in NEVER_JOB_SUBJECT]
_keep = [re.compile(p, re.I) for p in STRONG_KEEP]
_drop_from = [re.compile(p, re.I) for p in DROP_FROM]
_drop_subject = [re.compile(p, re.I) for p in DROP_SUBJECT]


def _sender_matches(from_addr: str, patterns: list[str]) -> str | None:
    """Patterns are addresses ("a@b.com") or domains ("b.com", also matching sub.b.com)."""
    addr = parseaddr(from_addr)[1].lower()
    domain = addr.rsplit("@", 1)[-1]
    for p in patterns:
        if addr == p or domain == p or domain.endswith("." + p):
            return p
    return None


@lru_cache(maxsize=8)
def _compile_user_patterns(patterns: tuple[str, ...]) -> list[re.Pattern]:
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p, re.I))
        except re.error:  # a typo in the user's file shouldn't stop syncing; match it literally
            compiled.append(re.compile(re.escape(p), re.I))
    return compiled


def should_process(
    email: RawEmail, *, include: list[str] = (), ignore: list[str] = (), never: list[str] = ()
) -> tuple[bool, str]:
    """Return (keep, reason). `include` / `ignore` are the user's ALWAYS_INCLUDE / ALWAYS_IGNORE;
    `never` holds the user's own never-job subject patterns (see Settings.never_job_subjects)."""
    if hit := _sender_matches(email.from_addr, list(ignore)):
        return False, f"always ignore: {hit}"
    if hit := _sender_matches(email.from_addr, list(include)):
        return True, f"always include: {hit}"
    for rx in _never + _compile_user_patterns(tuple(never)):
        if rx.search(email.subject):
            return False, f"never job: {rx.pattern}"
    if email.outgoing:
        return True, "your outreach"
    text = f"{email.subject}\n{email.body[:2000]}"
    for rx in _keep:
        if rx.search(text):
            return True, f"strong keep: {rx.pattern}"
    if email.promotional:
        return False, "promotional (Gmail Promotions)"
    for rx in _drop_from:
        if rx.search(email.from_addr):
            return False, f"drop sender: {rx.pattern}"
    for rx in _drop_subject:
        if rx.search(email.subject):
            return False, f"drop subject: {rx.pattern}"
    return True, "default keep"
