"""Read a job posting's details (company, role, location…) from its URL.

Only runs when the user asks for it (it is the one network call besides Gmail). Tries, in order:
structured JobPosting data (schema.org JSON-LD), the page title / preview tags, the URL itself,
and finally the local model on the page text.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from html import unescape
from urllib.parse import urlparse

from .gmail_client import html_to_text

MAX_BYTES = 3_000_000
TIMEOUT = 12
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

# ATS hosts where the company is the first path segment (or the subdomain), e.g. jobs.lever.co/acme/123
_PATH_COMPANY_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com",
                       "breezy.hr", "wellfound.com")
_SUBDOMAIN_COMPANY_HOSTS = ("myworkdayjobs.com", "recruitee.com", "teamtailor.com", "bamboohr.com",
                            "zohorecruit.com", "keka.com", "darwinbox.in", "freshteam.com")
_ATS_HOSTS = _PATH_COMPANY_HOSTS + _SUBDOMAIN_COMPANY_HOSTS + ("icims.com", "jobvite.com", "workday.com")


class JobPageError(Exception):
    """The link can't be read (invalid, blocked, unreachable, or not a web page)."""


@dataclass
class JobDetails:
    url: str
    company: str = ""
    role: str = ""
    location: str = ""
    source: str = "direct"
    posted_on: str = ""
    description: str = ""
    found_by: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return asdict(self)


def normalize_url(raw: str) -> str:
    """A web link or nothing: adds https:// when the scheme is missing, rejects anything else."""
    url = raw.strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or "." not in parsed.netloc:
        raise ValueError("The job posting URL should be a web link, e.g. https://jobs.example.com/123")
    return url


def _check_public_host(host: str) -> None:
    """Never fetch from this machine or the local network, whatever the link says."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise JobPageError(f"Couldn't find {host}. Check the link.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise JobPageError("Links to this computer or the local network can't be read.")


def fetch(url: str) -> str:
    _check_public_host(urlparse(url).hostname or "")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8",
                                                   "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            final_host = urlparse(response.geturl()).hostname or ""
            _check_public_host(final_host)  # a redirect must not land on a local address either
            if "html" not in (response.headers.get("Content-Type") or "html"):
                raise JobPageError("That link isn't a web page.")
            body = response.read(MAX_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
    except JobPageError:
        raise
    except urllib.error.HTTPError as exc:
        hint = " The site may require signing in (LinkedIn often does)." if exc.code in (401, 403, 999) else ""
        raise JobPageError(f"The site answered with an error ({exc.code}).{hint}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise JobPageError(f"Couldn't reach the site ({getattr(exc, 'reason', exc)}).") from exc
    return body.decode(charset, errors="replace")


# --- parsing --------------------------------------------------------------------------------------

_JSON_LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
_META = re.compile(r"<meta\s+[^>]*>", re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def _job_postings(node) -> list[dict]:
    if isinstance(node, list):
        return [p for item in node for p in _job_postings(item)]
    if not isinstance(node, dict):
        return []
    kinds = node.get("@type")
    kinds = kinds if isinstance(kinds, list) else [kinds]
    found = [node] if "JobPosting" in kinds else []
    return found + _job_postings(node.get("@graph", []))


def _name(value) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("name", "")
    return unescape(str(value or "")).strip()


def _location(posting: dict) -> str:
    if str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        return "Remote"
    places = posting.get("jobLocation") or []
    places = places if isinstance(places, list) else [places]
    labels = []
    for place in places:
        address = place.get("address", {}) if isinstance(place, dict) else {}
        if isinstance(address, str):
            labels.append(address)
            continue
        parts = [address.get("addressLocality"), address.get("addressRegion"), _name(address.get("addressCountry"))]
        label = ", ".join(dict.fromkeys(p for p in parts if p))
        if label:
            labels.append(label)
    return "; ".join(dict.fromkeys(labels))[:200]


def from_structured_data(html: str, details: JobDetails) -> None:
    for block in _JSON_LD.findall(html):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        for posting in _job_postings(data):
            details.role = details.role or _name(posting.get("title"))
            details.company = details.company or _name(posting.get("hiringOrganization"))
            details.location = details.location or _location(posting)
            details.posted_on = details.posted_on or str(posting.get("datePosted", ""))[:10]
            if not details.description and posting.get("description"):
                details.description = html_to_text(unescape(str(posting["description"])))[:4000].strip()
            details.found_by.append("structured data")
            return


def _meta(html: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for tag in _META.findall(html):
        key = re.search(r'(?:property|name)=["\']([^"\']+)["\']', tag, re.I)
        content = re.search(r'content=["\']([^"\']*)["\']', tag, re.I)
        if key and content:
            values.setdefault(key.group(1).lower(), unescape(content.group(1)).strip())
    return values


# "Job Application for Senior Designer at Acme" · "Senior Designer at Acme" · "Acme hiring Senior Designer in Berlin"
# "Acme - Senior Designer" (Lever puts the company first)
_TITLE_PATTERNS = [
    (re.compile(r"^(?:job application for\s+)?(?P<role>.+?)\s+at\s+(?P<company>[^|–—-]+?)(?:\s*[|–—-].*)?$", re.I), None),
    (re.compile(r"^(?P<company>.+?)\s+hiring\s+(?P<role>.+?)(?:\s+in\s+(?P<location>[^|]+?))?(?:\s*\|.*)?$", re.I), None),
    (re.compile(r"^(?P<company>[^–—|-]+?)\s+[–—-]\s+(?P<role>[^|]+?)(?:\s*\|.*)?$"), "lever.co"),
]


_NOT_ROLES = {"careers", "jobs", "job", "work", "working", "life", "join us", "open positions", "openings"}


def _match_title(title: str, host: str) -> dict | None:
    for pattern, only_host in _TITLE_PATTERNS:
        if only_host and not host.endswith(only_host):
            continue
        match = pattern.match(title)
        if match and (match.groupdict().get("role") or "").strip().lower() not in _NOT_ROLES:
            return {k: (v or "").strip() for k, v in match.groupdict().items()}
    return None


def from_page_title(html: str, details: JobDetails, host: str) -> None:
    meta = _meta(html)
    title_tag = _TITLE.search(html)
    candidates = [unescape(title_tag.group(1)) if title_tag else "", meta.get("og:title", ""), meta.get("twitter:title", "")]
    candidates = [re.sub(r"\s+", " ", c).strip() for c in candidates if c and c.strip()]
    on_ats = any(host.endswith(h) for h in _ATS_HOSTS)

    groups = next((g for g in (_match_title(c, host) for c in candidates) if g), None)
    if groups:
        details.role = details.role or groups.get("role", "")
        details.company = details.company or groups.get("company", "")
        details.location = details.location or groups.get("location", "")
        details.found_by.append("page title")
    elif on_ats and meta.get("og:title") and len(meta["og:title"]) <= 100:
        # ATS pages often put just the job title in the preview tag (e.g. Greenhouse job boards)
        details.role = details.role or meta["og:title"]
        details.found_by.append("page title")

    if host.endswith("greenhouse.io") and not details.location:
        location = meta.get("og:description", "")
        if location and len(location) <= 80 and "." not in location:
            details.location = location  # Greenhouse uses the preview description for the location
    if not details.company and meta.get("og:site_name") and "linkedin" not in meta["og:site_name"].lower():
        details.company = meta["og:site_name"]
    if not details.description and meta.get("og:description") and len(meta["og:description"]) > 80:
        details.description = meta["og:description"][:1000]


def _slug_to_name(slug: str) -> str:
    return " ".join(w.capitalize() for w in re.split(r"[-_]+", slug) if w)


def from_url(url: str, details: JobDetails) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.endswith("linkedin.com"):
        details.source = "linkedin"
    elif any(host.endswith(h) for h in _ATS_HOSTS):
        details.source = "ats"
    if details.company:
        return
    segments = [s for s in parsed.path.split("/") if s]
    if any(host.endswith(h) for h in _PATH_COMPANY_HOSTS) and segments:
        skip = {"jobs", "job", "j", "o", "embed", "boards", "company", "companies"}
        slug = next((s for s in segments if s.lower() not in skip), "")
        if slug and not slug.isdigit():
            details.company = _slug_to_name(slug)
            details.found_by.append("link")
    elif any(host.endswith(h) for h in _SUBDOMAIN_COMPANY_HOSTS):
        details.company = _slug_to_name(host.split(".")[0])
        details.found_by.append("link")


def parse(url: str, html: str) -> JobDetails:
    details = JobDetails(url=url)
    host = (urlparse(url).hostname or "").lower()
    from_structured_data(html, details)
    if not (details.company and details.role):
        from_page_title(html, details, host)
    from_url(url, details)
    return details


def read_job_page(raw_url: str, model_fallback=None) -> JobDetails:
    """Fetch and parse a job posting. `model_fallback(text) -> dict` fills gaps from the page text."""
    try:
        url = normalize_url(raw_url)
    except ValueError as exc:
        raise JobPageError(str(exc)) from exc
    if not url:
        raise JobPageError("Paste a job posting link first.")
    _check_public_host(urlparse(url).hostname or "")
    html = fetch(url)
    details = parse(url, html)
    if model_fallback and not (details.company and details.role):
        text = details.description or html_to_text(html)[:6000]
        try:
            guess = model_fallback(text)
        except Exception:  # the local model is a best-effort extra
            guess = {}
        details.company = details.company or (guess.get("company") or "")
        details.role = details.role or (guess.get("role") or "")
        details.location = details.location or (guess.get("location") or "")
        if guess:
            details.found_by.append("local model")
    if not (details.company or details.role):
        raise JobPageError("Couldn't find job details on that page. Fill them in by hand.")
    return details
