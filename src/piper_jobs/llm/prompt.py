"""Shared system prompt and few-shot examples for every extractor."""

from __future__ import annotations

import json

from ..schema import RawEmail

# Bump when the prompt changes meaningfully: the next sync re-checks emails it now reads differently.
PROMPT_VERSION = 2

SYSTEM_PROMPT = """You extract job-application updates from the candidate's emails. Reply with JSON only.

Each email shows its Direction: "received" (sent to the candidate) or "sent by the candidate".
Some emails start with a Context line saying the candidate is already in a hiring process with a company. Calendar invitations, bookings and short scheduling emails from that company's people are then part of that hiring process: is_job_related is true and stage is interview, unless the email clearly says otherwise.

Fields:
- is_job_related: true if the email is about a job the candidate applied to, is talking to a company about, or is being recruited for. This includes direct conversations with founders, hiring managers or recruiters (scheduling calls, "next steps", follow-ups) and calendar invitations or bookings for such calls. Job alerts, job recommendations, digests, newsletters, marketing, social and personal invitations are false.
- company: the HIRING company. Never the ATS or job board (Greenhouse, Lever, Workday, Ashby, SmartRecruiters, iCIMS, LinkedIn, Naukri, Instahyre, Calendly). Drop suffixes like "via LinkedIn". If no name is written, use the sender's (or, for sent emails, the recipient's) email domain: sam@northstar.bio -> "Northstar".
- role: the job title, or null if not stated.
- stage: one of
  applied    - application submitted / received confirmation, including "we will review your application", and the candidate's own outreach to a company about a role
  viewed     - ONLY when the email says the employer already viewed it (e.g. LinkedIn "was viewed by")
  assessment - online test, take-home assignment, case study, design challenge
  interview  - any call or meeting with the company: interview invites, scheduling, calendar invitations, "next steps" conversations, follow-ups after a call
  offer      - an offer is extended
  accepted   - the candidate accepted an offer
  rejected   - the company declined ("unfortunately", "not moving forward")
  withdrawn  - the candidate withdrew
  Use null if is_job_related is false.
- source: linkedin (LinkedIn emails), ats (Greenhouse/Lever/Workday/etc.), recruiter (an agency recruiter reaching out), direct (the company's own people or mail, and the candidate's own outreach), other.
- confidence: 0-1, how sure you are about is_job_related, company AND stage together. Use a low value when unsure."""

FEW_SHOTS: list[tuple[dict[str, str], dict]] = [
    (
        {
            "from": "LinkedIn <jobs-noreply@linkedin.com>",
            "subject": "Your application was sent to Initrode",
            "body": "Your application was sent to Initrode. Software Engineer, Payments - Initrode - Remote. Applied on LinkedIn.",
        },
        {"is_job_related": True, "company": "Initrode", "role": "Software Engineer, Payments", "stage": "applied", "source": "linkedin", "confidence": 0.97},
    ),
    (
        {
            "from": "Acme Robotics Recruiting <no-reply@greenhouse.io>",
            "subject": "Update on your application",
            "body": "Hi, thank you for your interest in the Backend Engineer role at Acme Robotics. Unfortunately, we have decided not to move forward with your candidacy at this time.",
        },
        {"is_job_related": True, "company": "Acme Robotics", "role": "Backend Engineer", "stage": "rejected", "source": "ats", "confidence": 0.95},
    ),
    (
        {
            "from": "Globex via Workday <globex@myworkday.com>",
            "subject": "Next step: online assessment",
            "body": "Congratulations, you have been invited to complete a HackerRank coding assessment for the Platform Engineer position at Globex Corporation within 5 days.",
        },
        {"is_job_related": True, "company": "Globex", "role": "Platform Engineer", "stage": "assessment", "source": "ats", "confidence": 0.94},
    ),
    (
        {
            "direction": "sent by the candidate",
            "from": "Alex <alex@example.com>",
            "to": "Maya Rao <maya@lumenhealth.ai>",
            "subject": "Product designer interested in Lumen",
            "body": "Hi Maya, I'm a product designer with 8 years in health tech. I loved your launch and would love to explore design roles at Lumen. Portfolio attached.",
        },
        {"is_job_related": True, "company": "Lumen Health", "role": "Product Designer", "stage": "applied", "source": "direct", "confidence": 0.9},
    ),
    (
        {
            "from": "Divya Rao <divya@northstar.bio>",
            "subject": "Re: Next Steps w/ Northstar",
            "body": "Thanks for the chat yesterday, Alex! Next step is a conversation with our CTO. Does Thursday 4pm work?",
        },
        {"is_job_related": True, "company": "Northstar", "role": None, "stage": "interview", "source": "direct", "confidence": 0.88},
    ),
    (
        {
            "from": "Divya Rao <divya@northstar.bio>",
            "subject": "Invitation: Alex / Arjun @ Thu Sep 24, 2026 4pm - 5pm",
            "body": "You have been invited to the following event. Alex / Arjun. Join with Google Meet. Organizer: divya@northstar.bio",
        },
        {"is_job_related": True, "company": "Northstar", "role": None, "stage": "interview", "source": "direct", "confidence": 0.8},
    ),
    (
        {
            "context": "The candidate is already in a hiring process with Northstar (northstar.bio).",
            "from": "Arjun Iyer <arjun@northstar.bio>",
            "subject": "Invitation: Alex <> Arjun @ Wed Oct 7, 2026 14:00 - 14:45",
            "body": "Alex <> Arjun. Wednesday Oct 7, 2026. Join with Google Meet. Reply for alex@example.com: Yes / No / Maybe. Invitation from Google Calendar.",
        },
        {"is_job_related": True, "company": "Northstar", "role": None, "stage": "interview", "source": "direct", "confidence": 0.85},
    ),
    (
        {
            "from": "Rahul <rahul.k@gmail.com>",
            "subject": "Invitation: Dinner at The Corner Bistro @ Sat Sep 26, 2026 8pm",
            "body": "You have been invited to the following event. Dinner at The Corner Bistro. Organizer: rahul.k@gmail.com",
        },
        {"is_job_related": False, "company": None, "role": None, "stage": None, "source": None, "confidence": 0.9},
    ),
    (
        {
            "from": "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
            "subject": "30+ new jobs for Software Engineer",
            "body": "Jobs you may be interested in: Software Engineer at Initech, Backend Developer at Hooli...",
        },
        {"is_job_related": False, "company": None, "role": None, "stage": None, "source": None, "confidence": 0.95},
    ),
]


def format_email(
    from_addr: str, subject: str, body: str, *, to_addr: str = "", direction: str = "received", context: str = ""
) -> str:
    to_line = f"To: {to_addr}\n" if to_addr else ""
    context_line = f"Context: {context}\n" if context else ""
    return f"{context_line}Direction: {direction}\nFrom: {from_addr}\n{to_line}Subject: {subject}\n\n{body}"


def build_messages(email: RawEmail) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for example, answer in FEW_SHOTS:
        messages.append({"role": "user", "content": format_email(
            example["from"], example["subject"], example["body"],
            to_addr=example.get("to", ""), direction=example.get("direction", "received"),
            context=example.get("context", ""))})
        messages.append({"role": "assistant", "content": json.dumps(answer)})
    direction = "sent by the candidate" if email.outgoing else "received"
    messages.append({"role": "user", "content": format_email(
        email.from_addr, email.subject, email.body, to_addr=email.to_addr, direction=direction,
        context=email.context)})
    return messages
