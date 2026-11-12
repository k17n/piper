"""Fixed-format emails read with rules instead of the model.

LinkedIn's "Your application was sent to X" is the most common confirmation, and its body is mostly
tracking links and job suggestions, which the local model reads as a job alert. The format never
changes, so the company and role are read straight from it.
"""

from __future__ import annotations

import re

from .gmail_client import sender_domain
from .schema import JobEvent, RawEmail, Stage

LINKEDIN_SENT_TO = re.compile(r"your application was sent to\s+(?P<company>.+?)\s*$", re.I)


def _is_linkedin(from_addr: str) -> bool:
    domain = sender_domain(from_addr)
    return domain == "linkedin.com" or domain.endswith(".linkedin.com")


def is_linkedin_confirmation(from_addr: str, subject: str) -> bool:
    return _is_linkedin(from_addr) and bool(LINKEDIN_SENT_TO.search(subject))


def _linkedin_role(body: str, company: str) -> str | None:
    """The role is the first line after the "sent to" heading: heading, role, company, location."""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if LINKEDIN_SENT_TO.search(line):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if nxt and nxt.lower() != company.lower() and not re.match(r"(https?://|view job)", nxt, re.I):
                return nxt
            return None
    return None


def known_template(email: RawEmail) -> JobEvent | None:
    """A JobEvent for a fixed-format email, or None if the email isn't one we know."""
    if email.outgoing or not _is_linkedin(email.from_addr):
        return None
    m = LINKEDIN_SENT_TO.search(email.subject)
    if not m:
        return None
    company = m.group("company")
    return JobEvent(
        is_job_related=True,
        company=company,
        role=_linkedin_role(email.body, company),
        stage=Stage.applied,
        source="linkedin",
        confidence=0.97,
    )
