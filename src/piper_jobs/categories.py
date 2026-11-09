"""Role type of an application (design / product / vc / other), from its role, email subjects and company."""

from __future__ import annotations

import re
from collections.abc import Iterable

CATEGORIES = ["design", "product", "vc", "other"]

# Checked in this order, so "Product Design Lead" is design, not product.
_ROLE_RULES: list[tuple[str, re.Pattern]] = [
    ("design", re.compile(
        r"\b(design(er|ers)?|ux|ui|ui/ux|user experience|interaction|visual|creative|art director|"
        r"brand(ing)?|illustrat\w*|motion|human factors|ux research\w*|design research\w*|accessibility)\b", re.I)),
    ("vc", re.compile(
        r"\b(venture|vc|investment|investor|invest\w*|entrepreneur[- ]in[- ]residence|eir|scout|"
        r"portfolio (associate|manager)|fund)\b", re.I)),
    ("product", re.compile(
        r"\b(product (manager|management|owner|lead|head|director|ops|operations|strategy|analyst|associate)|"
        r"head of product|vp,? product|director,? product|pm|apm|gpm|tpm|cpo|program manag\w*)\b", re.I)),
]

# Investment firms, by company name or email domain (roles there are often unstated).
_VC_COMPANY = re.compile(r"\b(ventures?|capital|vc|partners)\b|\d+vc\b|funds?\b|invest", re.I)
_VC_DOMAIN = re.compile(r"(venture|capital|fund|invest|vc\.)", re.I)


def classify(
    role: str | None, company: str | None, subjects: Iterable[str] = (), domains: Iterable[str] = ()
) -> str:
    for text in [role or "", *subjects]:
        for category, rx in _ROLE_RULES:
            if text and rx.search(text):
                return category
    if company and _VC_COMPANY.search(company):
        return "vc"
    if any(_VC_DOMAIN.search(d) for d in domains):
        return "vc"
    return "other"


SENIORITY_LEVELS = ["intern", "junior", "mid", "senior", "staff", "lead", "head", "unspecified"]

# Checked in this order, so "Senior Director" is head, not senior. "Manager" alone is a job, not a level.
_SENIORITY_RULES: list[tuple[str, re.Pattern]] = [
    ("intern", re.compile(r"\b(intern|internship|trainee|apprentice)\b", re.I)),
    ("head", re.compile(r"\b(head of|director|vp|vice president|svp|evp|chief|cpo|cto|cdo|general manager)\b", re.I)),
    ("staff", re.compile(r"\b(staff|principal|distinguished|fellow)\b", re.I)),
    ("lead", re.compile(r"\b(lead|gpm|group product manager|(engineering|design|ux) manager)\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr)\b|\biii\b", re.I)),
    ("mid", re.compile(r"\b(mid|intermediate)\b|\bii\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr|associate|entry|graduate|apm)\b|\bi\b", re.I)),
]

_LEVEL_WORDS = {"intern", "junior", "jr", "senior", "sr", "staff", "principal", "lead", "mid",
                "i", "ii", "iii", "iv", "1", "2", "3", "4"}


def seniority(role: str | None) -> str:
    """Level from the role title; `unspecified` when the title carries no level."""
    for level, rx in _SENIORITY_RULES:
        if role and rx.search(role):
            return level
    return "unspecified"


def normalize_title(role: str | None) -> str:
    """Role title without level words or punctuation, so 'Sr. Designer' and 'Designer II' count together."""
    words = re.sub(r"[^\w\s]", " ", (role or "").lower()).split()
    return " ".join(w for w in words if w not in _LEVEL_WORDS)
