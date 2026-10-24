from datetime import datetime, timedelta

from sqlmodel import select

from jobtracker.db import Application
from jobtracker.resolver import apply_event, normalize_company

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
