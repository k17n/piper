import pytest

from piper_jobs.categories import SENIORITY_LEVELS, classify, normalize_title, seniority


@pytest.mark.parametrize("role,company,subjects,expected", [
    ("Senior Product Designer", "Solari", [], "design"),
    ("Product Design Lead, Growth", "Initech", [], "design"),
    ("Head of Product Design", "Vantage AI", [], "design"),
    ("Human Factors Researcher", "Ōmni Health", [], "design"),
    ("UI/UX Designer", "Soundwave", [], "design"),
    ("Product Manager I", "Shopwise", [], "product"),
    ("Associate Product Manager", "Neurafield", [], "product"),
    ("Product Owner", "Acme", [], "product"),
    ("Program Management & Operations", "Acme", [], "product"),
    ("Investment Analyst", "Lumina Invest", [], "vc"),
    ("Entrepreneur in Residence", "Hooli", [], "vc"),
    (None, "Lumina Invest", [], "vc"),
    (None, "42VC", [], "vc"),
    (None, "Harbor Fund", [], "vc"),
    (None, "Acme", ["Application: Senior Product Designer II | Remote"], "design"),
    (None, "Quillstack", ["Your interview is scheduled — Product Manager at Quillstack"], "product"),
    (None, "Northstar", ["Next Steps w/ Northstar"], "other"),
    ("Entrepreneur-in-Residence / Founder's Office", "Brightpath", [], "vc"),
    ("Senior Product Associate", "Globex Bank", [], "product"),
    ("Technical Program Manager (TPM)", "Initech", [], "product"),
    ("Accessibility Specialist", "Globex Bank", [], "design"),
    (None, "Bluefund", [], "vc"),
    ("Chief of Staff", "Oakridge", [], "other"),
    ("Software Engineer", "Initrode", [], "other"),
])
def test_classify(role, company, subjects, expected):
    assert classify(role, company, subjects) == expected


@pytest.mark.parametrize("role,expected", [
    ("Sr. Product Designer", "senior"),
    ("Senior Product Manager", "senior"),
    ("Product Designer III", "senior"),
    ("Product Designer II", "mid"),
    ("Mid-level UX Designer", "mid"),
    ("Product Designer I", "junior"),
    ("Associate Product Manager", "junior"),
    ("Jr Designer", "junior"),
    ("Design Intern", "intern"),
    ("Staff Designer", "staff"),
    ("Principal Product Manager", "staff"),
    ("Design Lead", "lead"),
    ("Engineering Manager", "lead"),
    ("Head of Product", "head"),
    ("Senior Director of Design", "head"),
    ("VP Product", "head"),
    ("Product Designer", "unspecified"),
    ("Product Manager", "unspecified"),
    ("", "unspecified"),
    (None, "unspecified"),
])
def test_seniority(role, expected):
    assert seniority(role) == expected
    assert expected in SENIORITY_LEVELS


@pytest.mark.parametrize("role,expected", [
    ("Sr. Product Designer", "product designer"),
    ("Product Designer II", "product designer"),
    ("Senior  Product-Designer", "product designer"),
    ("Head of Product", "head of product"),
    (None, ""),
    ("", ""),
])
def test_normalize_title(role, expected):
    assert normalize_title(role) == expected
