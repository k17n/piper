"""Read-only Gmail access: OAuth desktop flow, query building, paginated fetch, body extraction."""

from __future__ import annotations

import base64
import calendar
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parseaddr
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote

from .config import Settings
from .schema import RawEmail

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MAX_BODY = 4000
RETRIES = 8  # exponential backoff on 429 / 403 rateLimitExceeded (per-minute quota)


class GmailNotConfigured(RuntimeError):
    pass


def get_service(settings: Settings, interactive: bool = True):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if settings.token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(settings.token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not interactive:
                raise GmailNotConfigured("Gmail is not connected yet. Run `jobtracker sync` once.")
            if not settings.credentials_path.is_file():
                raise GmailNotConfigured(
                    f"No OAuth client found at {settings.credentials_path}. "
                    "See README → 'Connect Gmail'."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(settings.credentials_path), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        settings.token_path.parent.mkdir(parents=True, exist_ok=True)
        settings.token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def date_clause(settings: Settings, after: datetime | None = None) -> str:
    if after is None:
        return f"newer_than:{settings.backfill_days}d"
    return f"after:{calendar.timegm(after.timetuple())}"


def build_query(settings: Settings, after: datetime | None = None) -> str:
    """The main search: job platforms + hiring words, plus the user's own include rules."""
    parts = [settings.gmail_query]
    if settings.gmail_extra_query:
        parts.append(f"({settings.gmail_extra_query})")
    if settings.always_include:
        parts.append(f"from:({' OR '.join(settings.always_include)})")
    return f"{date_clause(settings, after)} ({' OR '.join(parts)})"


def domains_query(settings: Settings, domains: list[str]) -> str:
    return f"{date_clause(settings)} from:({' OR '.join(domains)})"


def list_messages(service, query: str) -> list[dict[str, str]]:
    """[{id, threadId}] for every message matching the query (all pages)."""
    found: list[dict[str, str]] = []
    token = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=500, pageToken=token)
            .execute(num_retries=RETRIES)
        )
        found.extend(resp.get("messages", []))
        token = resp.get("nextPageToken")
        if not token:
            return found


def my_address(service) -> str:
    return service.users().getProfile(userId="me").execute(num_retries=RETRIES)["emailAddress"]


def message_url(message_id: str, account: str | None) -> str:
    """Opens the message in Gmail, in the right account when several are signed in."""
    who = f"?authuser={account}" if account else ""
    return f"https://mail.google.com/mail/u/{who}#all/{message_id}"


def list_message_ids(service, query: str) -> list[str]:
    return [m["id"] for m in list_messages(service, query)]


@dataclass
class ThreadInfo:
    id: str
    message_ids: list[str]  # oldest first
    sent_ids: set[str] = field(default_factory=set)
    dates: dict[str, datetime] = field(default_factory=dict)

    @property
    def started_by_me(self) -> bool:
        return bool(self.message_ids) and self.message_ids[0] in self.sent_ids


def list_sent_threads(service, settings: Settings) -> list[ThreadInfo]:
    """Every thread you sent mail in within the backfill window (cheap: ids and labels only).

    Always uses the full window, so new replies to an older conversation are still found.
    """
    thread_ids = dict.fromkeys(m["threadId"] for m in list_messages(service, f"in:sent {date_clause(settings)}"))
    threads: list[ThreadInfo] = []
    for tid in thread_ids:
        th = service.users().threads().get(userId="me", id=tid, format="minimal").execute(num_retries=RETRIES)
        msgs = sorted(th.get("messages", []), key=lambda m: int(m.get("internalDate", 0)))
        threads.append(ThreadInfo(
            id=tid,
            message_ids=[m["id"] for m in msgs],
            sent_ids={m["id"] for m in msgs if "SENT" in m.get("labelIds", [])},
            dates={m["id"]: _ts(m) for m in msgs},
        ))
    return threads


def _ts(msg: dict[str, Any]) -> datetime:
    return datetime.fromtimestamp(int(msg.get("internalDate", 0)) / 1000, tz=timezone.utc).replace(tzinfo=None)


def fetch_email(service, message_id: str) -> RawEmail:
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute(num_retries=RETRIES)
    return parse_message(msg)


def fetch_thread(service, thread_id: str) -> list[RawEmail]:
    """All messages of a thread, oldest first, with quoted history stripped from each."""
    th = service.users().threads().get(userId="me", id=thread_id, format="full").execute(num_retries=RETRIES)
    return sorted((parse_message(m) for m in th.get("messages", [])), key=lambda e: e.received_at)


def parse_message(msg: dict[str, Any]) -> RawEmail:
    payload = msg.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    labels = msg.get("labelIds", [])
    return RawEmail(
        id=msg["id"],
        thread_id=msg.get("threadId"),
        from_addr=headers.get("from", ""),
        subject=headers.get("subject", ""),
        received_at=_ts(msg),
        body=extract_body(payload),
        to_addr=headers.get("to", ""),
        outgoing="SENT" in labels,
        promotional="CATEGORY_PROMOTIONS" in labels,
        bulk="list-unsubscribe" in headers or headers.get("precedence", "").lower() in ("bulk", "list"),
    )


def sender_email(from_header: str) -> str:
    return parseaddr(from_header)[1].lower()


def sender_domain(from_header: str) -> str:
    addr = sender_email(from_header)
    return addr.rsplit("@", 1)[1] if "@" in addr else ""


def _walk(part: dict[str, Any]):
    yield part
    for child in part.get("parts", []) or []:
        yield from _walk(child)


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def extract_body(payload: dict[str, Any]) -> str:
    plain: list[str] = []
    html: list[str] = []
    for part in _walk(payload):
        data = (part.get("body") or {}).get("data")
        if not data:
            continue
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            plain.append(_decode(data))
        elif mime == "text/html":
            html.append(_decode(data))
    text = "\n".join(plain)
    if not text.strip():
        text = "\n".join(html)
    return clean_text(text)[:MAX_BODY]


# Some senders put HTML in the text/plain part; three or more tags means it isn't really plain text.
_HTML_TAG = re.compile(r"</?(p|br|div|span|table|tr|td|a|b|strong|li|ul|ol|h\d)\b[^>]*>", re.I)
# Gmail rewrites links as https://www.google.com/url?q=<real url>&sa=...
_GOOGLE_REDIRECT = re.compile(r"https?://www\.google\.com/url\?q=([^&\s]+)[^\s)]*")


def clean_text(text: str) -> str:
    """Readable message text: HTML converted, redirect links unwrapped, quoted history removed,
    hard-wrapped lines rejoined."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(_HTML_TAG.findall(text)) >= 3:
        text = html_to_text(text)
    text = _GOOGLE_REDIRECT.sub(lambda m: unquote(m.group(1)), text)
    text = strip_quoted(text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = _unwrap(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_LIST_ITEM = re.compile(r"^([-*•>]|\d+[.)]) ")


def _unwrap(text: str) -> str:
    """Plain-text mail is hard-wrapped at ~72-78 columns; join a long line with the line after it
    unless that one starts a list item. Short lines (greetings, sign-offs) keep their breaks."""
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        prev = out[-1] if out else ""
        if prev and line and len(prev) >= 60 and not _LIST_ITEM.match(line) and not prev.endswith(":"):
            out[-1] = f"{prev} {line}"
        else:
            out.append(line)
    return "\n".join(out)


# Where a reply's quoted history starts: "On <date> <person> wrote:" (wrapped over up to 3 lines),
# Outlook's "-----Original Message-----" or "From: ... Sent: ..." headers.
_QUOTE_START = re.compile(
    r"^[ \t]*(On [^\n]{0,200}(\n[^\n]{0,200}){0,2}?wrote:[ \t]*$|-{2,}\s*Original Message\s*-{2,}|From: [^\n]+\n\s*Sent: )",
    re.M | re.I,
)


def strip_quoted(text: str) -> str:
    """Keep only the new part of a reply, so each message is judged on what it adds."""
    match = _QUOTE_START.search(text)
    if match and match.start() > 0:
        text = text[: match.start()]
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">")).rstrip()


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "section"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "".join(parser.parts)
