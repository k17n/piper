# P.I.P.E.R. Writing Studio — Feature PRD

| | |
|---|---|
| **Status** | Draft — not built |
| **Parent** | [P.I.P.E.R. PRD](PRD.md), §12 Roadmap |
| **Runs on** | The same local stack: Ollama (chat + embedding models), SQLite, the existing app UI |
| **Privacy** | Fully local. Knowledge files, drafts and memories never leave the machine or enter the repository |

---

## 1. Summary

Writing Studio drafts **cover letters, LinkedIn messages, WhatsApp messages and emails** that are
specific to the user and to the company they are engaging with. It grounds every draft in a personal
**knowledge base** (résumé, strengths, weaknesses, projects, past writing) and in what the tracker
already knows about the company (applications, email threads, notes).

Every writing session is a **thread** — a chat between the user and the assistant tied to a company or
application. Threads are stored, and what they teach (preferred style, facts about the user, facts about
companies, finished pieces the user was happy with) is carried forward into future sessions, so the
assistant gets better at writing for this user over time.

## 2. Problem

- Generic, template-like messages get ignored; tailoring each one by hand takes 20–40 minutes.
- Cloud writing tools require pasting a résumé and private conversations into a third-party service.
- Each channel has different norms (a LinkedIn connection note is limited to 300 characters, a WhatsApp
  message must read like a person typed it, a cover letter needs structure) and people mix them up.
- Context is lost between sessions: yesterday's conversation about a company, or the edits the user
  always makes to drafts, have to be repeated every time.

## 3. Goals and non-goals

**Goals**
1. Produce a usable first draft in under 30 seconds that needs only light editing.
2. Make each piece **unique**: grounded in the user's real strengths and in the specific company,
   never a reused template.
3. Pick the right **format** for the channel, and ask when it isn't clear.
4. Keep every session as a thread and **carry learning forward** across sessions.
5. Never invent facts about the user; make every factual claim traceable to a source.

**Non-goals (v1)**
- Sending anything. The app copies text or opens a pre-filled compose window; the user sends it.
  (Gmail access stays read-only; LinkedIn and WhatsApp are never automated.)
- Scraping LinkedIn profiles or company sites without the user's explicit request.
- Fine-tuning model weights (see §9.4: "learning" in v1 is context and memory, not training).

## 4. Users and core scenarios

**User:** a job seeker who engages with a chosen set of companies through several channels and wants
writing that sounds like them.

| # | Scenario | Channel |
|---|---|---|
| S1 | Applying to a posted role and needing a tailored cover letter | Cover letter |
| S2 | Reaching out to a founder or hiring manager before applying | LinkedIn message or email |
| S3 | Sending a connection request with a note | LinkedIn connection note |
| S4 | Following up with a recruiter met at an event who shared their number | WhatsApp |
| S5 | Following up after an interview, or checking in after silence | Email |
| S6 | Coming back the next day to adjust yesterday's draft, or writing a second message to the same person | Any — continues the existing thread |

## 5. Inputs

### 5.1 Knowledge base (about the user)

A local folder, by default `~/.piper/knowledge/`:

```
knowledge/
  resume.md          core — always included
  positioning.md     core — who the user is, what they want next, voice and tone
  strengths.md       core
  weaknesses.md      used for honest framing and interview prep; rarely quoted in outreach
  projects/*.md      one file per project or case study — retrieved by relevance
  stories/*.md       short STAR-style stories — retrieved by relevance
  writing/*.md       past letters/messages the user liked — style examples
```

- **Formats:** Markdown and plain text in v1. PDF and Word import is a later step and needs two small
  libraries (to be approved before adding).
- **Indexing:** files are split by heading into chunks, each with a stable ID (`projects/payments.md#impact`),
  and embedded with a local model (`nomic-embed-text` via Ollama). Only changed files are re-indexed
  (content hash). Indexing runs in the background when the folder changes.
- **Core vs retrieved:** files marked *core* are always in context. Everything else is retrieved per
  request (top 5–8 chunks by similarity to the company/role/job description, plus keyword matches).
  When the whole knowledge base fits in the context budget, it is included in full and retrieval is skipped.
- **Setup help:** an empty folder is created on first use with template files explaining what to write
  in each, so a new user knows where to start.

### 5.2 Company and opportunity context

Gathered automatically when a thread is linked to a company or application:
- the application record (company, role, stage, source, notes, role type);
- the email threads with that company (fetched live from Gmail, read-only, quoted history removed);
- company facts remembered from earlier writing threads (§9.2);
- a **job description** pasted by the user (optional but strongly encouraged for cover letters);
- *(opt-in)* a job posting or company page URL the user provides, fetched once and stored as text. This
  is the only network access besides Gmail and is off by default.

### 5.3 The request

What the user types: the goal ("ask for a 20-minute chat about the design role"), the recipient
(name, title, relationship), and anything to emphasise or avoid.

## 6. Output formats

The assistant chooses the format from the request and context. **If it is ambiguous, it asks** — one
short question with the likely options as buttons (e.g. "LinkedIn message · Email · WhatsApp"). It asks
at most two clarifying questions before drafting, and never asks for something it already knows.

| Format | Length | Structure | Tone defaults | Notes |
|---|---|---|---|---|
| **Cover letter** | 250–400 words | Greeting · hook specific to the company · 2 evidence paragraphs mapped to the role · why this company · close with call to action | Professional, confident | Optional header (name, contact) from `resume.md`; export to `.md` / `.docx` |
| **LinkedIn connection note** | ≤ 300 characters (hard limit) | Who you are · one specific reason · ask | Warm, brief | Character counter; refuses to exceed the limit |
| **LinkedIn message / InMail** | 60–150 words | Specific opener · relevance · one ask | Conversational, professional | No subject line for messages; short subject for InMail |
| **WhatsApp message** | 1–4 short lines | Greeting by name · context of how you met · one clear ask | Natural, like typed by hand; no formal sign-off | Optional split into 2 messages; no markdown |
| **Email** | 80–200 words | **Subject line** · greeting · purpose in the first sentence · supporting line · ask · sign-off | Matches the relationship (cold, warm, follow-up, thank-you) | "Open in Gmail compose" pre-fills subject and body; app never sends |

Format rules (length limits, required parts, banned phrases) are enforced after generation; a draft that
breaks a hard rule is regenerated or trimmed automatically before it is shown.

## 7. Uniqueness and quality

1. **Specificity requirement:** each draft must reference at least one company-specific detail
   (from the job description, email thread or remembered company facts) and at least one user-specific
   piece of evidence (a project, story or result from the knowledge base).
2. **Anti-template check:** new drafts are compared with the user's earlier drafts (embedding similarity
   and shared-sentence overlap). If a draft is too similar to one sent to another company, the
   assistant rewrites the overlapping parts and tells the user it did.
3. **Banned clichés:** a default list ("I am writing to express my interest", "passionate about",
   "team player"…) plus phrases the user has removed before (§9.2).
4. **Grounding:** every factual claim about the user carries a source chunk ID. Claims without a source
   are listed under **Claims to check** and highlighted in the draft; nothing is silently invented.
5. **Weaknesses** are used only when the user asks (e.g. addressing a gap) and are framed honestly.

## 8. Threads

### 8.1 What a thread is

A thread is one writing conversation, linked to a **company** (and optionally an application and a
recipient). It contains, in order:
- user messages (requests, feedback such as "make it shorter", direct edits);
- assistant messages (clarifying questions, drafts, explanations);
- **draft versions** — each draft is a versioned artifact with its format, sources and quality notes;
- the **final version** the user marked as *Used* (copied/sent), with the date and channel.

Threads can hold several pieces (e.g. a LinkedIn note, then a follow-up email to the same person a week
later) so the full engagement with a company lives in one place.

### 8.2 Behaviour

- Opening a company's thread restores the conversation and its drafts; new requests use everything in it.
- Long threads are summarised automatically (key facts, decisions, current draft) so they fit in context.
- Threads appear in the application detail panel and in a **Studio** view listing all threads by company,
  last activity and pieces sent.
- Marking a piece as *Used* can optionally add an event to the tracker (e.g. outreach on LinkedIn), so
  outreach that never goes through email still shows in the funnel.

## 9. Learning across sessions ("transfer learning")

In v1, learning means **carrying knowledge forward through context and memory**, not changing the
model's weights. Three kinds of memory are built from threads:

### 9.1 Style examples
Final versions marked *Used* (or starred) become style examples. When drafting, the 1–3 most similar
past pieces **of the same format** are included as examples of the user's voice — never copied, and
never for the same company (to protect uniqueness).

### 9.2 Learned preferences and facts
After each session, the assistant proposes short memory entries from what happened, for example:
- *Style:* "Prefers opening with a concrete result, not a greeting line." (learned from repeated edits)
- *Style:* "Removes the word 'leverage'." (learned from deletions)
- *About the user:* "Led a design-system migration across 4 product teams." (stated in chat, not yet in the knowledge base)
- *About a company:* "Northstar's founder cares about field research; mentioned on the 3 Sep call."

Each memory has a type, source thread, date and on/off switch. **New memories are suggested, not saved
silently**: the user approves them in one click, and can edit or delete any memory later in a
**Memory** screen. User facts can be promoted into the knowledge base files.

### 9.3 How memory is used
Every request assembles context in this order, within a token budget:
1. format rules and banned phrases → 2. core knowledge files → 3. active style preferences →
4. company memories and current thread summary → 5. retrieved knowledge chunks → 6. style examples →
7. job description / email context → 8. the request.

### 9.4 Later: real fine-tuning (out of scope for v1)
Once there are enough approved pieces, an optional LoRA adapter could be trained on them. On an 8 GB
GPU this is borderline for a 7B model and would run as an explicit, opt-in job. It is listed as a
research item, not a commitment.

## 10. User experience

- **Entry points:** "Write…" in the application detail panel (company, role and thread prefilled);
  a **Studio** tab in the sidebar; "New thread" for companies not yet in the tracker.
- **Layout:** conversation on the left, current draft on the right with format badge, character/word
  count, source chips per sentence, and *Claims to check*.
- **Quick actions:** Regenerate · Shorter · Warmer · More formal · Regenerate this paragraph ·
  Change format · Copy · Open in Gmail compose (email) · Export (cover letter) · Mark as used.
- **Streaming:** text appears as it is generated; the user can stop generation.
- **Missing inputs:** if the knowledge base is empty, the Studio explains what to add instead of
  producing a generic draft.

## 11. Models and performance

| Purpose | Default | Notes |
|---|---|---|
| Drafting | the configured chat model (`qwen2.5:7b-instruct`) | Optional separate `WRITING_MODEL` (e.g. a 9B model tuned for prose) |
| Embeddings | `nomic-embed-text` | ~300 MB; fits alongside the chat model in 8 GB VRAM |
| Context window | 16k tokens (configurable) | Ollama's default (2–4k) is raised per request |

Targets on a mid-range 8 GB GPU: first token < 3 s, full cover letter < 20 s, LinkedIn/WhatsApp < 8 s,
knowledge re-index of a changed file < 2 s.

## 12. Data model (additions)

- `knowledge_files(path, kind, core, content_hash, indexed_at)`
- `knowledge_chunks(id, path, heading, text, embedding)`
- `writing_threads(id, company, application_id, recipient_name, recipient_role, channel_hint, title, summary, created_at, updated_at)`
- `writing_messages(id, thread_id, role, content, created_at)`
- `drafts(id, thread_id, message_id, format, version, subject, body, sources, claims_to_check, quality_notes, status[draft|used|starred], used_at, used_channel)`
- `memories(id, type[style|user_fact|company_fact], company, content, source_thread_id, status[suggested|active|off], created_at)`
- `job_descriptions(id, application_id, company, role, text, source_url, created_at)`

## 13. API (additions, localhost only)

`GET/POST /api/studio/threads`, `GET /api/studio/threads/{id}`, `POST /api/studio/threads/{id}/messages`
(streams the reply), `POST /api/studio/drafts/{id}/actions` (shorter, warmer, regenerate-paragraph…),
`PATCH /api/studio/drafts/{id}` (edit, mark used/starred), `GET/PATCH/DELETE /api/studio/memories`,
`GET /api/studio/knowledge` (files, index status), `POST /api/studio/knowledge/reindex`.

## 14. Privacy and safety

- Knowledge files, threads, drafts and memories live only in the user's data folder; none of it is
  committed, uploaded or sent anywhere.
- Gmail access stays read-only; "Open in Gmail compose" uses a compose link the user sends themselves.
- URL fetching is opt-in per URL and stored as plain text.
- Memories are user-approved and fully editable/deletable; deleting a thread deletes its memories
  unless the user keeps them.

## 15. Acceptance criteria

1. With a filled knowledge base and a pasted job description, a cover letter is produced in < 20 s that
   names the company, maps at least two requirements to user evidence, and lists zero unsupported claims
   or flags every one of them.
2. A LinkedIn connection note never exceeds 300 characters; a WhatsApp message contains no markdown or
   formal sign-off; an email always has a subject line.
3. When the request does not imply a channel, the assistant asks one question offering the formats.
4. Two letters for different companies with the same role share no sentence longer than 8 words.
5. Reopening a thread the next day continues with its full context; a style preference approved in one
   thread is applied in a new thread for a different company.
6. Turning a memory off removes its effect on the next draft.

## 16. Evaluation

- A fixed test set of fictional profiles and job descriptions, scored on: specificity, grounding
  (unsupported claims), format compliance, uniqueness across companies, and the user's edit distance
  from draft to final (lower is better).
- Compare candidate writing models on the same set before changing the default.

## 17. Milestones

| Phase | Scope |
|---|---|
| **M1 — Grounded drafts** | Knowledge folder + templates, core files in full context, cover letter and email formats, threads with versioned drafts, sources and Claims to check |
| **M2 — All channels** | LinkedIn note/message and WhatsApp formats, format question, hard format rules, Mark as used → tracker event, Gmail compose link |
| **M3 — Retrieval** | Chunking, local embeddings, retrieval for large knowledge bases, anti-template check |
| **M4 — Memory** | Suggested memories, Memory screen, style examples from used pieces, thread summaries |
| **M5 — Extras** | PDF/Word import, opt-in URL fetch, application-question answers and interview prep from the same knowledge base |
| **Research** | Optional LoRA fine-tuning on approved pieces |

## 18. Open questions

1. Should "Mark as used" always create a tracker event, or only for channels the tracker can't see (LinkedIn, WhatsApp)?
2. How many memories should be active before older or conflicting ones are summarised or retired?
3. Is one thread per company right, or one per recipient within a company?
4. Should drafts in other languages be supported in v1?
