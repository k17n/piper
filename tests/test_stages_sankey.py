from datetime import datetime, timedelta

from jobtracker.filters import Filters, load_rows
from jobtracker.resolver import apply_event
from jobtracker.sankey import build_sankey, path_for
from jobtracker.stages import compute_current_stage, effective_stage

T0 = datetime(2026, 5, 1)
d = lambda n: T0 + timedelta(days=n)  # noqa: E731


def test_highest_progress_stage():
    assert compute_current_stage([("applied", d(0)), ("interview", d(5)), ("viewed", d(6))]) == "interview"


def test_terminal_wins_when_later():
    assert compute_current_stage([("applied", d(0)), ("interview", d(5)), ("rejected", d(9))]) == "rejected"


def test_progress_after_terminal_revives():
    assert compute_current_stage([("applied", d(0)), ("rejected", d(2)), ("interview", d(9))]) == "interview"


def test_ghosting_is_query_time_only():
    now = d(40)
    assert effective_stage("viewed", d(5), False, now, 30) == "ghosted"
    assert effective_stage("viewed", d(15), False, now, 30) == "viewed"
    assert effective_stage("rejected", d(0), False, now, 30) == "rejected"
    assert effective_stage("interview", d(0), True, now, 30) == "interview"


def _seed(session):
    journeys = {
        ("A", "linkedin"): ["applied", "viewed", "rejected"],
        ("B", "linkedin"): ["applied", "interview", "offer", "accepted"],
        ("C", "ats"): ["applied"],  # ghosted later
        ("D", "ats"): ["applied", "assessment", "interview"],
        ("E", "recruiter"): ["interview", "rejected"],  # no explicit applied
    }
    for (company, source), stages in journeys.items():
        for i, stage in enumerate(stages):
            apply_event(session, company=f"Company {company}", role="Engineer", stage=stage,
                        source=source, occurred_at=d(i * 3))
    session.commit()


def test_sankey_one_path_per_app_and_values_balance(session, settings):
    _seed(session)
    rows = load_rows(session, Filters(range="all"), settings, now=d(20))
    data = build_sankey(rows)

    # each application contributes exactly one path: flow out of source nodes == #apps
    sources = {n["name"] for n in data["nodes"] if n["kind"] == "source"}
    assert sum(l["value"] for l in data["links"] if l["source"] in sources) == len(rows) == 5

    # every link value equals the number of application ids it carries
    for link in data["links"]:
        assert link["value"] == len(link["application_ids"])

    # flow is conserved at intermediate nodes: inflow >= outflow
    for node in {n["name"] for n in data["nodes"]} - sources:
        inflow = sum(l["value"] for l in data["links"] if l["target"] == node)
        outflow = sum(l["value"] for l in data["links"] if l["source"] == node)
        assert inflow >= outflow

    # each app id appears exactly once per path depth leaving its source
    first_hop = [i for l in data["links"] if l["source"] in sources for i in l["application_ids"]]
    assert len(first_hop) == len(set(first_hop)) == 5


def test_paths(session, settings):
    _seed(session)
    rows = {r.app.company_display: r for r in load_rows(session, Filters(range="all"), settings, now=d(20))}
    assert path_for(rows["Company A"]) == ["LinkedIn", "Applied", "Viewed", "Rejected"]
    assert path_for(rows["Company B"]) == ["LinkedIn", "Applied", "Interview", "Offer", "Accepted"]
    assert path_for(rows["Company E"]) == ["Recruiter", "Applied", "Interview", "Rejected"]
    late = {r.app.company_display: r for r in load_rows(session, Filters(range="all"), settings, now=d(60))}
    assert path_for(late["Company C"]) == ["Company site / ATS", "Applied", "Ghosted"]
