from datetime import datetime, timedelta

from sqlmodel import select

from piper_jobs.db import Application
from piper_jobs.resolver import apply_event, normalize_company

T0 = datetime(2026, 5, 1)


def test_normalize_company():
    assert normalize_company("Initrode") == "initrode"
    assert normalize_company("Initrode, Inc.") == "initrode"
    assert normalize_company("Initrode via Greenhouse") == "initrode"
    assert normalize_company("Acme Technologies Pvt. Ltd.") == "acme"


def test_initrode_variants_merge(session):
    for i, name in enumerate(["Initrode", "Initrode, Inc.", "Initrode via Greenhouse"]):
        apply_event(session, company=name, role="Software Engineer", stage="applied",
                    source="ats", occurred_at=T0 + timedelta(days=i))
    apps = session.exec(select(Application)).all()
    assert len(apps) == 1
    assert apps[0].company_display == "Initrode"


def test_spacing_variants_merge(session):
    a = apply_event(session, company="Orbit Labs", role=None, stage="interview", source="direct", occurred_at=T0)
    b = apply_event(session, company="OrbitLabs", role=None, stage="assessment", source="direct",
                    occurred_at=T0 + timedelta(days=2))
    assert a.id == b.id


def test_two_roles_same_company_stay_separate(session):
    apply_event(session, company="Initrode", role="Backend Engineer", stage="applied",
                source="linkedin", occurred_at=T0)
    apply_event(session, company="Initrode", role="Product Designer", stage="applied",
                source="linkedin", occurred_at=T0)
    assert len(session.exec(select(Application)).all()) == 2


def test_seniority_levels_stay_separate(session):
    apply_event(session, company="Initrode", role="Software Engineer", stage="applied",
                source="linkedin", occurred_at=T0)
    apply_event(session, company="Initrode", role="Senior Software Engineer", stage="applied",
                source="linkedin", occurred_at=T0)
    apply_event(session, company="Initrode", role="Software Engineer, Payments", stage="applied",
                source="linkedin", occurred_at=T0)
    assert len(session.exec(select(Application)).all()) == 3


def test_role_wording_variants_merge(session):
    a = apply_event(session, company="Northwind", role="Backend Engineer - Payments", stage="applied",
                    source="linkedin", occurred_at=T0)
    b = apply_event(session, company="Northwind", role="Backend Engineer (Payments)", stage="interview",
                    source="ats", occurred_at=T0 + timedelta(days=4))
    assert a.id == b.id and b.current_stage == "interview"


def test_missing_role_attaches_to_most_recent(session):
    old = apply_event(session, company="Initrode", role="Backend Engineer", stage="applied",
                      source="linkedin", occurred_at=T0)
    new = apply_event(session, company="Initrode", role="Data Engineer", stage="applied",
                      source="linkedin", occurred_at=T0 + timedelta(days=5))
    got = apply_event(session, company="Initrode", role=None, stage="rejected",
                      source="ats", occurred_at=T0 + timedelta(days=9))
    assert got.id == new.id != old.id
    assert got.current_stage == "rejected"


def test_manual_override_is_respected(session):
    a = apply_event(session, company="Umbrella Health", role="SWE", stage="applied", source="ats", occurred_at=T0)
    a.manual_override, a.current_stage = True, "offer"
    apply_event(session, company="Umbrella Health", role="SWE", stage="rejected", source="ats",
                occurred_at=T0 + timedelta(days=3))
    assert a.current_stage == "offer"


def _email(session, id, sender, day, subject="Thanks for applying"):
    from piper_jobs.db import Email

    session.add(Email(id=id, from_addr=sender, subject=subject, received_at=T0 + timedelta(days=day)))
    session.flush()


def test_identical_roleless_confirmations_are_separate_applications(session):
    """Applying to three roles back to back: the company sends the same email three times."""
    for i, day in enumerate([0, 25, 25]):
        _email(session, f"c{i}", "Wonka Labs <no-reply@wonkalabs.example>", day)
        apply_event(session, company="Wonka Labs", role=None, stage="applied", source="ats",
                    occurred_at=T0 + timedelta(days=day, minutes=i), email_id=f"c{i}")
    assert len(session.exec(select(Application)).all()) == 3


def test_linkedin_notice_and_company_confirmation_are_one_application(session):
    _email(session, "li", "LinkedIn <jobs-noreply@linkedin.com>", 0, "Your application was sent to Wonka Labs")
    apply_event(session, company="Wonka Labs", role="Product Designer", stage="applied", source="linkedin",
                occurred_at=T0, email_id="li")
    _email(session, "co", "Wonka Labs <no-reply@wonkalabs.example>", 0)
    apply_event(session, company="Wonka Labs", role=None, stage="applied", source="ats",
                occurred_at=T0 + timedelta(hours=2), email_id="co")
    apps = session.exec(select(Application)).all()
    assert len(apps) == 1 and apps[0].role_display == "Product Designer"


def test_split_merged_confirmations_repairs_old_data(session):
    from piper_jobs.db import Event
    from piper_jobs.resolver import split_merged_confirmations

    app = apply_event(session, company="Wonka Labs", role=None, stage="applied", source="ats", occurred_at=T0)
    app.notes, app.manual_override, app.current_stage = "keep me", True, "rejected"
    for i in range(3):  # what older versions did: three identical confirmations on one application
        _email(session, f"m{i}", "Wonka Labs <no-reply@wonkalabs.example>", i)
        session.add(Event(email_id=f"m{i}", application_id=app.id, stage="applied", occurred_at=T0 + timedelta(days=i)))
    session.commit()

    assert split_merged_confirmations(session) == 2
    apps = session.exec(select(Application).order_by(Application.id)).all()
    assert len(apps) == 3
    assert (apps[0].notes, apps[0].current_stage) == ("keep me", "rejected")  # your edits stay put
    assert split_merged_confirmations(session) == 0  # idempotent
