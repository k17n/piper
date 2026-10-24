# P.I.P.E.R. — Product Requirements Document

> **P**ipeline · **I**nterviews · **P**itches · **E**mails · **R**ésumés — a private, local job-search assistant.

| | |
|---|---|
| **Status** | MVP built; this document describes current behaviour and the planned next steps |
| **Platform** | Local desktop app (Windows first; macOS/Linux via the same Python + web stack) |
| **Privacy model** | Fully local: email content is processed on the user's machine by a local LLM |

---

## 1. Problem

Job seekers apply through many channels — LinkedIn Easy Apply, company career sites running different
applicant-tracking systems (Greenhouse, Lever, Workday, Ashby…), recruiters, and direct outreach to
founders or hiring managers. Updates for each application arrive as scattered emails in different formats.
Keeping a spreadsheet up to date is tedious, so most people lose track of where each application stands,
which ones went silent, and how their funnel is actually performing.

## 2. Product summary

Piper reads the user's Gmail (read-only), uses a **local LLM via Ollama** to turn each relevant
email into a structured event (company, role, stage), merges events into one record per application,
and presents the result as an interactive funnel (Sankey), a filterable applications table, a review
queue for uncertain cases, and a per-application timeline with the email conversation.

Everything runs on the user's machine. The only remote service is the Gmail API.

## 3. Target users

- **Primary:** an individual job seeker running many applications at once across job boards, ATS
  portals and direct conversations, who wants an accurate picture without manual data entry.
- **Secondary:** privacy-conscious users who will not send their inbox to a cloud service.

Assumed setup skill: can follow a README to install the app and create a Google OAuth client
(see §12 for the plan to simplify this).

## 4. Goals and non-goals

**Goals**
1. Find every application update in Gmail, including direct conversations outside job boards.
2. Extract company, role and stage reliably with a local model; route uncertain cases to the user.
3. Show the funnel and every application's history in a fast, clear UI.
4. Keep all email content on the user's machine; store only short snippets.
5. Start with one action (`start.bat` / `piper ui`) and keep itself up to date in the background.

**Non-goals**
- Hosting, multi-user accounts or any cloud deployment.
- Scraping LinkedIn or other sites directly — email only.
- Sending, replying to or modifying email.

## 5. Glossary

| Term | Meaning |
|---|---|
| **Event** | One email interpreted as a step for an application (e.g. "interview on 3 Sep"). |
| **Application** | One company + role the user is pursuing, built from its events. |
| **Stage** | `applied`, `viewed`, `assessment`, `interview`, `offer`, `accepted`, `rejected`, `withdrawn`, `ghosted`. |
| **Terminal stage** | `rejected`, `withdrawn`, `accepted` (and `ghosted`, which is derived). |
| **Source** | `linkedin`, `ats`, `recruiter`, `direct`, `referral`, `other`. |
| **Role type** | `design`, `product`, `vc`, `other`. |
| **Review item** | An email the model was unsure about, shown to the user for a decision. |

---

## 6. Functional requirements

Each feature lists what it does and how we know it works. ✅ = built, 🔜 = planned.

### 6.1 Gmail ingestion ✅

- **Access:** OAuth desktop flow with the `gmail.readonly` scope only. The OAuth client file lives in
  the user's data folder; the access token is cached there after the first sign-in.
- **Main search:** messages from known job platforms (LinkedIn, Greenhouse, Lever, Workday, Ashby,
  SmartRecruiters, iCIMS, Naukri, Instahyre, Wellfound, Workable, Recruitee, Teamtailor, Breezy,
  Jobvite, Zoho Recruit, Keka, Darwinbox, Cutshort, Hirist, Y Combinator, Calendly) **or** subjects
  containing hiring words (application, interview, offer, assessment, next steps, invitation,
  appointment booked, take-home, case study, shortlisted…).
- **Conversations:** every thread the user sent an email in during the backfill window is included in
  full. The user's first email in a thread they started counts as outreach (`applied`); their later
  replies are stored but not analysed.
- **Company follow-up:** once a company domain has a job-related email, all mail from that domain is
  included (calendar invites, bookings). Free-mail providers, job platforms and the user's own domain
  are never followed.
- **Incremental sync:** the first sync reads `BACKFILL_DAYS` (default 180); later syncs read mail since
  the last successful sync minus one day. Conversation threads and followed domains always use the
  full window so new replies to older threads are found.
- **Re-scan on filter change:** a signature of all filter settings, rule versions and prompt version is
  stored; when it changes, the next sync searches the full window again and re-checks emails that were
  previously skipped, plus earlier "not a job" verdicts for companies now known.
- **Robustness:** Gmail rate limits (429 / 403 `rateLimitExceeded`) are retried with exponential backoff.
- **Body handling:** plain text preferred, HTML converted when needed (including HTML placed in the
  plain-text part); quoted reply history removed; Google redirect links unwrapped; hard-wrapped lines
  rejoined; truncated to ~4,000 characters.

*Acceptance:* `piper sync --dry-run` lists matched subjects with keep/drop decisions and writes
nothing; running `piper sync` twice in a row makes no LLM calls the second time.

### 6.2 Prefilter (rules before the LLM) ✅

Applied in order:
1. User's `ALWAYS_IGNORE` senders → drop; `ALWAYS_INCLUDE` senders → keep.
2. **Never-job subjects** (built-in list + the user's own `never_job_subjects.txt`): verification codes,
   OTPs, sign-in/security alerts, OAuth notices, IPO applications, credit-card offers, LinkedIn nudges
   ("apply now to…", "your saved job is expiring", "open to work"), incomplete applications.
3. The user's own outreach → keep.
4. **Strong keeps** ("your application was sent to / viewed by", "thank you for applying",
   "application received") → keep.
5. Gmail **Promotions** category → drop.
6. Job-alert senders and digest/marketing subjects → drop. Otherwise keep.

*Acceptance:* unit tests over labelled samples in `data/samples/`; invalid user patterns are matched
literally instead of failing the sync.

### 6.3 Local LLM extraction ✅

- **Provider:** Ollama (default model `qwen2.5:7b-instruct`, fits in 8 GB VRAM), called with a JSON
  schema for structured output and temperature 0; one retry on invalid output.
- **Output:** `is_job_related`, `company` (the hiring company, never the ATS), `role`, `stage`,
  `source`, `confidence`.
- **Prompt:** stage definitions, rules for inferring the company from an email domain, guidance for
  direct conversations and calendar invitations, and few-shot examples (job board, ATS rejection,
  assessment, outreach, conversation, calendar invite, personal invite, job alert).
- **Context:** when an email belongs to a thread or company domain already linked to an application,
  the prompt states "the candidate is already in a hiring process with X", so invites and short
  scheduling emails are read correctly.
- **Outreach:** if the user's own first email is job-related, its stage is forced to `applied`.
- **Routing:**
  - job-related with confidence ≥ 0.5 and company + stage present → event created;
  - job-related but low confidence or missing company/stage → review queue;
  - "not a job" with confidence < 0.6 from a person (not bulk mail) → review queue;
  - unparseable model output → review queue;
  - otherwise "not a job".
- Emails are processed one at a time with progress reported to the UI.

*Acceptance:* ≥ 90% accuracy on stage and company over the labelled samples with the default model.

### 6.4 Entity resolution ✅

- Company names are normalised (lowercase, punctuation removed, "via X" removed, suffixes such as
  inc / llc / ltd / pvt / technologies / labs dropped).
- A new event matches an existing application when the company `token_set_ratio` ≥ 90 (or the names
  are identical ignoring spaces, e.g. "OrbitLabs" = "Orbit Labs") **and** the role `token_sort_ratio`
  ≥ 80 or either role is missing. Different seniority levels ("Senior", "II", "Staff"…) never match.
- An event without a role attaches to the company's most recently active application.

*Acceptance:* "Initrode", "Initrode, Inc." and "Initrode via Greenhouse" merge; two roles at one
company stay separate; senior and non-senior roles stay separate.

### 6.5 Stages and ghosting ✅

- **Current stage:** the highest progress stage reached (`applied < viewed < assessment < interview <
  offer < accepted`); a terminal stage wins if it came at or after that point. A later progress event
  revives an application after a rejection.
- **Manual override:** setting a stage by hand fixes it until the user clears the override.
- **Ghosting:** computed at query time, never stored. An application is shown as `ghosted` when it is
  not in a terminal stage, has no manual override, and its last event is older than `GHOST_DAYS`
  (default 30). A later email reverses it automatically.

### 6.6 Role types ✅

- Each application is classified as **Design**, **Product**, **VC** or **Other** from, in order: the
  role title, the subjects of its emails, the company name (e.g. "…Ventures", "…Capital", "…Fund"), and
  its email domains (e.g. `…invest.com`).
- The user can change the type per application; manual choices persist and can be reset to automatic.

### 6.7 Filters and saved views ✅

- One filter model drives every view: date range (30d / 90d / 6m / All / Custom, on the application's
  first-seen date), role types, sources, stages, text search, include/exclude ghosted.
- Relative ranges stay relative when saved (a "Last 90 days" view keeps rolling).
- **Saved views:** create, rename, overwrite, delete, set one default (loaded on startup); a dot shows
  when current filters differ from the open view.
- Filters, open view and tab are mirrored in the URL so refreshes and bookmarks keep them.
- "Data available since …" shows the earliest synced email.

*Acceptance:* the same filters give consistent totals across the funnel, KPIs and table; exactly one
view can be default.

### 6.8 Dashboard ✅

- **KPI cards** (animated): applications and active count, response rate, interview rate, offer rate,
  median days to first response.
- **Sankey funnel:** one path per application (`source → applied → … → final stage`), gradient links,
  tooltips with counts and percentages, theme-aware colours that update immediately on theme change.
  Clicking a link or node opens a side panel with those applications.

### 6.9 Applications table ✅

- Sortable columns: company, role, type, source, stage, applied date, last update.
- Inline editing: role, stage (sets a manual override, clearable), role type, notes.
- Clicking a company opens the application detail panel.
- **Add application** (for ones with no email): company, role, optional job posting URL, source (incl. Referral), date applied,
  current stage, notes. Later emails from the company attach to it instead of creating a duplicate.
- **Fill from link**: reads company, role, location and source from a job posting URL, only when the
  user clicks it (the one network call besides Gmail; local/private addresses refused). Order:
  schema.org JobPosting data → page title / preview tags (Greenhouse, Lever, LinkedIn formats) → the
  URL itself (ATS company slugs) → the local model on the page text. Fills only empty fields. In the
  detail panel, *Fill role from link* names applications whose emails never said the role.
- **Log an update** in the detail panel: stage, date and a note for things that happened off email;
  it appears on the timeline and moves the stage like an email would.
- **Delete** with an inline confirmation; its emails are kept as *dismissed* so it never comes back.
- Identical role-less confirmations from one sender count as separate applications; role-less
  updates with several open applications at a company go to the review queue to choose which.

### 6.10 Application detail and conversation ✅

- **Timeline:** every event with stage, date and email subject; each links to Gmail.
- **Conversation:** the selected email's full Gmail thread, fetched live (read-only) and never stored,
  shown as message cards (the user's messages offset to the right), with quoted history removed and
  links shortened. The triggering email is highlighted.
- **Order switch:** Newest first (default) / Oldest first, applied to both the timeline and the
  conversation, remembered across sessions.

### 6.11 Review queue ✅

- Shows each uncertain email with reason, sender, date, a readable excerpt (stored only for review
  items), **Read email** expansion and **Open in Gmail**.
- Quick-fix form prefilled with the model's guess (company, role, stage, source) → creates the event;
  or **Not a job email** dismisses it.
- When filter rules change, open review items the new rules would drop are dismissed automatically.
- Bulk and promotional mail never enters the queue.

### 6.12 Sync and scheduling ✅

- Background sync every `SYNC_INTERVAL_HOURS` (default 6) while the app is open, plus once ~30 s after
  start; only runs once Gmail is connected (never opens a sign-in window by itself).
- **Sync now** button; live progress over server-sent events ("Extracting 42/180 · model").
- One sync at a time.

### 6.13 App shell and packaging ✅

- Single Python process: FastAPI on `127.0.0.1` (free port) serving the API and the built React app,
  APScheduler, and a native window via pywebview (`--browser` opens a tab instead).
- **`start.bat` / `start.ps1`:** finds `uv`, starts Ollama if needed and waits for it, installs
  dependencies, rebuilds the UI only when its source changed, opens the app.
- Dark theme by default with a light toggle; theme-aware native dropdowns; layouts that wrap rather
  than overflow.
- `index.html` is served `no-cache` and hashed assets as immutable, so rebuilt UIs never load stale.

### 6.14 Command line ✅

| Command | Purpose |
|---|---|
| `piper ui [--browser] [--port N]` | Open the app |
| `piper sync [--dry-run] [--full]` | Fetch and extract |
| `piper doctor` | Check Ollama, the model and GPU use |
| `piper seed [--force]` | Load fictional sample data |
| `piper stats [--range …]` | Print funnel stats |
| `piper reset [--yes]` | Delete the database and Gmail token |

---

## 7. Configuration

Read from environment variables, then `<data dir>/.env`, then `./.env`.

| Setting | Default | Purpose |
|---|---|---|
| `OLLAMA_MODEL` / `OLLAMA_HOST` | `qwen2.5:7b-instruct` / `http://localhost:11434` | Local model |
| `GHOST_DAYS` | 30 | Silence before an open application is shown as ghosted |
| `SYNC_INTERVAL_HOURS` | 6 | Background sync interval |
| `BACKFILL_DAYS` | 180 | How far back the first sync reads |
| `GMAIL_EXTRA_QUERY` | — | Extra Gmail search OR-ed into the main search |
| `INCLUDE_SENT_THREADS` | true | Include threads the user sent mail in |
| `FOLLOW_COMPANY_DOMAINS` | true | Include all mail from companies in a hiring process |
| `ALWAYS_INCLUDE` / `ALWAYS_IGNORE` | — | Comma-separated domains or addresses |
| `never_job_subjects.txt` (file) | — | The user's own never-job subject patterns, one per line |
| `PIPER_HOME` | `~/.piper` | Data folder |

## 8. Data model (SQLite)

- `emails(id, thread_id, from_addr, to_addr, subject, received_at, processed_at, snippet, llm_status)`
- `events(id, email_id, application_id, stage, occurred_at, confidence, source, note)` (`note`: what happened, for updates logged by hand)
- `applications(id, company_norm, company_display, role_norm, role_display, source, first_seen,
  last_event_at, current_stage, manual_override, category, category_manual, job_url, notes)`
- `review_queue(id, email_id, reason, extracted, excerpt, resolved)`
- `saved_views(id, name, filters, is_default, created_at, updated_at)`
- `sync_state(key, value)` — last sync time, filter signature, Gmail address

New columns are added automatically to existing databases on startup.

## 9. API (localhost only)

`GET /api/meta`, `GET /api/sankey`, `GET /api/stats`, `GET /api/insights`, `GET /api/applications`,
`POST /api/applications`, `PATCH|DELETE /api/applications/{id}`, `POST /api/applications/{id}/events`,
`POST /api/job-link/preview`, `GET /api/emails/{id}/thread`, `GET /api/review-queue`,
`POST /api/review-queue/{id}/resolve`, `GET|POST /api/views`, `PATCH|DELETE /api/views/{id}`,
`POST /api/sync`, `GET /api/sync/status`, `GET /api/sync/stream`. Read endpoints accept the shared
filter parameters. Interactive docs at `/docs`.

## 10. Non-functional requirements

- **Privacy:** server bound to `127.0.0.1`; read-only Gmail scope; only snippets stored (plus excerpts
  for review items); live threads never stored; secrets and data kept outside the repository.
- **Performance:** ~1 s per email extraction on a mid-range GPU; incremental syncs process only new mail.
- **Reliability:** connection errors leave emails unprocessed so they are retried next sync; rate limits
  are retried; one sync at a time.
- **Quality:** backend test suite (pytest) covering prefilter, extraction routing, resolution, stages,
  Sankey integrity, filters, saved views, API, thread parsing and caching headers.

## 11. Architecture

```
piper ui (one Python process)
├── pywebview window ──► http://127.0.0.1:<port>
├── FastAPI ── /api/*  JSON API          ── /  built React SPA
└── APScheduler ──► pipeline.sync()
                     ├── Gmail API (read-only)
                     ├── prefilter (rules)
                     ├── extractor ──► Ollama (localhost:11434)
                     ├── resolver (merge into applications)
                     └── SQLite (~/.piper/jobs.db)
```

Frontend: Vite + React + TypeScript + Tailwind, ECharts (Sankey), TanStack Query.

## 12. Roadmap

| Item | Notes |
|---|---|
| 🔜 **Writing Studio** | Grounded cover letters, LinkedIn, WhatsApp and email drafts from a local knowledge base, stored as threads with memory across sessions — see [PRD-writing-studio.md](PRD-writing-studio.md) |
| 🔜 In-app **Connect Gmail** / "Sign in with Google" button | Removes the command-line step; optional bundled OAuth client for small groups (Google limits unverified apps to 100 test users with weekly re-sign-in) |
| 🔜 Kanban board | Stage columns; dragging a card sets a manual override |
| 🔜 Insights view | Activity heatmap and response rate by source (`/api/insights` exists) |
| 🔜 ⌘K command palette | Jump to a company, switch views, trigger a sync |
| 🔜 `piper eval` | Accuracy per field on labelled samples, to compare models |
| 🔜 Anthropic provider | Optional cloud model behind `LLM_PROVIDER=anthropic` |
| 🔜 Per-stage ghosting thresholds | e.g. shorter silence limits after interviews and offers |
| 🔜 Upcoming interviews | Parse calendar invites for dates |
| 🔜 Résumé generator | Tailored résumé versions per role from the Writing Studio knowledge base |
| 🔜 Interview prep | Likely questions and matching stories from each company's thread and the knowledge base |
| 🔜 Applying with you | Prepare applications for roles the user chooses; the user always reviews before anything is sent |
| 🔜 Export | CSV / Markdown |
| 🔜 One-click installer | Package with PyInstaller |

## 13. Open questions

- Should LinkedIn "application viewed" notices reset the ghosting clock?
- What is the right distribution model for non-technical users given Google's restricted-scope
  verification requirements?
