import json
from datetime import datetime
from pathlib import Path

import pytest

from piper_jobs.gmail_client import extract_body, html_to_text
from piper_jobs.prefilter import should_process
from piper_jobs.schema import RawEmail

SAMPLES = json.loads((Path(__file__).parents[1] / "data/samples/emails.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["subject"][:40] for s in SAMPLES])
def test_samples(sample):
    email = RawEmail("x", None, sample["from"], sample["subject"], datetime(2026, 1, 1), sample["body"])
    keep, reason = should_process(email)
    assert keep == sample["keep"], reason


@pytest.mark.parametrize("subject,keep", [
    ("Alex R, apply now to ‘Lead Product Designer at Brightloop’", False),
    ("Alex R, apply to Staff Product Designer at Ōmni Health and more", False),
    ("Alex R, your job’s expiring on Oct 21: Staff Product Designer at Fernway", False),
    ("Your Product Owner application is incomplete", False),
    ("Final reminder to complete your job application", False),
    ("Your IPO application for Acme Steel is submitted", False),
    ("Alex R, please verify your new device", False),
    ("Take action to confirm your identity", False),
    ("Security alert: new sign-in on Windows", False),
    ("Your 6-digit verification code from Testly", False),
    ("Your OTP for login is 482910", False),
    ("[GitHub] A third-party OAuth application has been added to your account", False),
    ("Alex R, your application was sent to Globex", True),
    ("Thank you for applying to Initech - Product Design Lead, Payroll", True),
    ("Re: Application for Product Manager Role (Ref: ABC-12345)", True),
    ("Taylor just messaged you", True),
])
def test_never_job_subjects(subject, keep):
    # body says "application received" to prove the never-job list wins over strong keeps
    email = RawEmail("x", None, "noreply@example.com", subject, datetime(2026, 1, 1), "Application received.")
    assert should_process(email)[0] == keep


def test_strong_keep_beats_linkedin_sender():
    email = RawEmail("x", None, "jobalerts-noreply@linkedin.com", "Update",
                     datetime(2026, 1, 1), "Your application was viewed by Initrode")
    assert should_process(email)[0]


def test_html_body_fallback():
    import base64

    html = "<html><head><style>p{}</style></head><body><p>Hello</p><p>World</p></body></html>"
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")}},
    ]}
    assert extract_body(payload) == "Hello\nWorld"
    assert "p{}" not in html_to_text(html)


def _payload(mime, text):
    import base64

    return {"mimeType": mime, "body": {"data": base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")}}


def test_extract_body_strips_wrapped_quote_header():
    # the real Gmail shape: "On ... <addr>" then "wrote:" on its own line, then "> " lines
    text = ("Sure. Sounds good.\n\nBest,\nAR\n\nOn Mon, Aug 24, 2026 at 4:43 PM Jordan Lee "
            "<jordan@northstar.bio>\nwrote:\n\n> Hi Alex,\n> Thanks")
    assert extract_body(_payload("text/plain", text)) == "Sure. Sounds good.\n\nBest,\nAR"


def test_extract_body_three_line_quote_header():
    text = "Thursday works.\n\nOn Mon, Aug 24, 2026 at 4:43 PM\nJordan Lee <d@x.tech>\nwrote:\n> old"
    assert extract_body(_payload("text/plain", text)) == "Thursday works."


def test_html_in_plain_part_is_converted():
    text = '<p style="font-size: 16px">\nHi Alex,<br/><br/>\nCongrats on becoming certified.<br/>\n</p>'
    body = extract_body(_payload("text/plain", text))
    assert "<" not in body and "Hi Alex," in body and "Congrats on becoming certified." in body


def test_google_redirect_links_are_unwrapped():
    text = "My calendly is here ( https://www.google.com/url?q=https://calendly.com/jamie/chat&source=gmail&ust=1&sa=E )"
    assert "( https://calendly.com/jamie/chat )" in extract_body(_payload("text/plain", text))


def test_crlf_quote_header_and_hard_wraps():
    text = ("Hi Alex,\r\n\r\nAs a next step, I've looped in our founder, Sam Ortiz, who is cced on\r\n"
            "this email.\r\n\r\nBest,\r\nJordan\r\n\r\nOn Mon, Aug 24, 2026 at 4:43 PM Jordan Lee <\r\n"
            "jordan@northstar.bio> wrote:\r\n\r\n> earlier")
    assert extract_body(_payload("text/plain", text)) == (
        "Hi Alex,\n\nAs a next step, I've looped in our founder, Sam Ortiz, who is cced on this email."
        "\n\nBest,\nJordan"
    )


def test_user_never_job_patterns_file(tmp_path):
    from piper_jobs.config import load_settings

    (tmp_path / "never_job_subjects.txt").write_text(
        "# my own rules\n\ncompany newsletter\nweekly (digest|roundup)\n[unclosed\n", encoding="utf-8")
    settings = load_settings(tmp_path)
    assert settings.never_job_subjects == ["company newsletter", "weekly (digest|roundup)", "[unclosed"]

    def keep(subject):
        email = RawEmail("x", None, "a@b.com", subject, datetime(2026, 1, 1), "Thanks for applying")
        return should_process(email, never=settings.never_job_subjects)[0]

    assert not keep("Company Newsletter: October")
    assert not keep("Your weekly roundup")
    assert not keep("Re: [unclosed bracket")  # an invalid pattern is matched literally instead of crashing
    assert keep("Thanks for applying to Acme")
