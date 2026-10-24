"""Reading job details from posting pages (fictional pages in the formats real sites use)."""

import pytest

from piper_jobs import job_page
from piper_jobs.job_page import JobPageError, normalize_url, parse, read_job_page


@pytest.fixture
def offline(monkeypatch):
    """No network in tests: names count as public; IP literals still go through the real check."""
    import ipaddress

    real_check = job_page._check_public_host

    def check(host):
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return
        real_check(host)

    monkeypatch.setattr(job_page, "_check_public_host", check)


@pytest.fixture
def client(settings):
    from fastapi.testclient import TestClient

    from piper_jobs.api import create_app

    with TestClient(create_app(settings)) as c:
        yield c

JSON_LD_PAGE = """<html><head><title>Careers</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [{"@type": "Organization", "name": "Ignore me"},
 {"@type": "JobPosting", "title": "Senior Product Designer",
  "hiringOrganization": {"@type": "Organization", "name": "Wonka Labs"},
  "jobLocation": [{"@type": "Place", "address": {"addressLocality": "Berlin", "addressCountry": {"name": "Germany"}}}],
  "datePosted": "2026-10-01T09:00:00Z",
  "description": "&lt;p&gt;Design &lt;b&gt;delightful&lt;/b&gt; things.&lt;/p&gt;"}]}
</script></head><body></body></html>"""


def test_structured_job_data():
    d = parse("https://boards.greenhouse.io/wonkalabs/jobs/123", JSON_LD_PAGE)
    assert (d.role, d.company, d.location, d.posted_on, d.source) == (
        "Senior Product Designer", "Wonka Labs", "Berlin, Germany", "2026-10-01", "ats")
    assert d.description == "Design delightful things." and d.found_by == ["structured data"]


def test_remote_jobs():
    html = ('<script type="application/ld+json">{"@type": "JobPosting", "title": "UX Researcher", '
            '"hiringOrganization": "Hooli", "jobLocationType": "TELECOMMUTE"}</script>')
    d = parse("https://hooli.example/careers/9", html)
    assert (d.role, d.company, d.location, d.source) == ("UX Researcher", "Hooli", "Remote", "direct")


@pytest.mark.parametrize("url,title,role,company,location", [
    ("https://boards.greenhouse.io/acme/jobs/1", "Job Application for Staff Designer at Acme Robotics",
     "Staff Designer", "Acme Robotics", ""),
    ("https://jobs.lever.co/initech/abc", "Initech - Product Manager, Growth", "Product Manager, Growth", "Initech", ""),
    ("https://www.linkedin.com/jobs/view/42", "Globex hiring Design Lead in Lisbon, Portugal | LinkedIn",
     "Design Lead", "Globex", "Lisbon, Portugal"),
])
def test_page_title_patterns(url, title, role, company, location):
    d = parse(url, f'<html><head><meta property="og:title" content="{title}"></head></html>')
    assert (d.role, d.company, d.location) == (role, company, location)


def test_careers_page_title_is_not_a_role():
    d = parse("https://acme.example/careers", "<title>Careers at Acme</title>")
    assert d.role == ""


@pytest.mark.parametrize("url,company", [
    ("https://jobs.lever.co/pied-piper/123", "Pied Piper"),
    ("https://jobs.ashbyhq.com/vandelay/abc-def", "Vandelay"),
    ("https://umbrella.wd5.myworkdayjobs.com/en-US/careers/job/123", "Umbrella"),
])
def test_company_from_link(url, company):
    d = parse(url, "<html></html>")
    assert d.company == company and d.source == "ats" and d.found_by == ["link"]


def test_local_and_private_addresses_are_refused():
    with pytest.raises(JobPageError):  # refused as "not a web link" before any lookup
        read_job_page("http://localhost:8000/x")
    for url in ("http://127.0.0.1/admin", "http://192.168.1.10/jobs", "http://10.0.0.5/jobs"):
        with pytest.raises(JobPageError, match="this computer or the local network"):
            read_job_page(url)


def test_url_rules():
    assert normalize_url("jobs.example.com/1") == "https://jobs.example.com/1"
    with pytest.raises(ValueError):
        normalize_url("javascript:alert(1)")
    with pytest.raises(JobPageError, match="Paste a job posting link"):
        read_job_page("  ")


def test_model_fallback_and_nothing_found(monkeypatch, offline):
    monkeypatch.setattr(job_page, "fetch", lambda url: "<html><body>We need a Data Engineer at Oscorp.</body></html>")
    d = read_job_page("https://oscorp.example/jobs/7",
                      model_fallback=lambda text: {"company": "Oscorp", "role": "Data Engineer", "location": ""})
    assert (d.company, d.role, d.found_by) == ("Oscorp", "Data Engineer", ["local model"])
    with pytest.raises(JobPageError, match="Couldn't find job details"):
        read_job_page("https://oscorp.example/jobs/7", model_fallback=lambda text: {})


def test_preview_endpoint(client, monkeypatch, offline):
    monkeypatch.setattr(job_page, "fetch", lambda url: JSON_LD_PAGE)
    r = client.post("/api/job-link/preview", json={"url": "boards.greenhouse.io/wonkalabs/jobs/123"})
    assert r.status_code == 200
    assert (r.json()["company"], r.json()["role"], r.json()["url"]) == (
        "Wonka Labs", "Senior Product Designer", "https://boards.greenhouse.io/wonkalabs/jobs/123")
    assert client.post("/api/job-link/preview", json={"url": "http://127.0.0.1/x"}).status_code == 422


def test_greenhouse_job_board_page():
    """Shape of Greenhouse's current job boards: no structured data, bare role in og:title."""
    html = ('<title>Job Application for Commercial Counsel at Greenhouse</title>'
            '<meta property="og:title" content="Commercial Counsel"/>'
            '<meta property="og:description" content="Eastern Timezone"/>')
    d = parse("https://job-boards.greenhouse.io/acme/jobs/8126988?gh_jid=8126988", html)
    assert (d.role, d.company, d.location, d.source) == ("Commercial Counsel", "Greenhouse", "Eastern Timezone", "ats")

    bare = parse("https://job-boards.greenhouse.io/acme/jobs/1", '<meta property="og:title" content="Staff Designer"/>')
    assert (bare.role, bare.company) == ("Staff Designer", "Acme")
