import pytest

from jobtracker.categories import classify


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
