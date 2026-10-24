# Job Application Tracker

A fully local app that reads your job-application emails from Gmail (LinkedIn Easy Apply + ATS
emails), uses a **local LLM via Ollama** to extract each application's stage, and shows your funnel
as an interactive Sankey chart.

Email content never leaves your machine: Gmail is read with the `gmail.readonly` scope, the LLM
runs in Ollama, the server binds to `127.0.0.1`, and all data lives in `~/.jobtracker/`.

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 20+, and [Ollama](https://ollama.com/download).

```bash
uv sync
cd web && npm install && npm run build && cd ..

ollama pull qwen2.5:7b-instruct   # ~4.7 GB, fits fully in 8 GB VRAM
uv run jobtracker doctor          # checks Ollama, the model and GPU use

uv run jobtracker seed            # optional: sample data to explore the UI
uv run jobtracker ui              # native window (add --browser for a browser tab)
```

## Start the app

Double-click **`start.bat`** (or run `.\start.ps1` in PowerShell; add `--browser` for a browser tab).
It finds `uv`, starts Ollama if it isn't running, installs dependencies on first run, rebuilds the
UI only when its source changed, and opens the app. Close the window to quit.

## Connect Gmail

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create a project
   (e.g. "Job Tracker").
2. **APIs & Services → Library**: search for **Gmail API** and click **Enable**.
3. **APIs & Services → OAuth consent screen** (Google Auth Platform → Branding/Audience):
   - User type: **External**. Fill in the app name and your email.
   - **Audience → Test users**: add your own Gmail address. While the app is in "Testing" only
     test users can sign in, and that is all you need.
   - **Data access → Add scopes**: add `https://www.googleapis.com/auth/gmail.readonly`.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**.
   - Download the JSON and save it as `~/.jobtracker/credentials.json`
     (on Windows: `C:\Users\<you>\.jobtracker\credentials.json`).
5. Run `uv run jobtracker sync --dry-run`. A browser window opens; sign in and allow read-only
   access. Google warns that the app is unverified; click **Continue** (it is your own app).
   The token is cached in `~/.jobtracker/token.json`.
6. The dry run lists the matching subjects and whether the prefilter keeps or drops each. When it
   looks right, run `uv run jobtracker sync` (or click **Sync now** in the app).

Note: in "Testing" mode Google expires refresh tokens after 7 days, so you may need to sign in
again weekly. Publishing the app (no verification needed for personal use) removes that limit.

## Commands

| Command | What it does |
|---|---|
| `jobtracker ui [--browser] [--port N]` | Start the app. Syncs every `SYNC_INTERVAL_HOURS` while open, plus once shortly after start (only once Gmail is connected). |
| `jobtracker sync [--dry-run] [--full]` | Fetch and extract. Later syncs only fetch mail since the last sync; `--full` re-runs the whole backfill. Already-processed emails are never sent to the LLM again. |
| `jobtracker doctor` | Check Ollama, the model and GPU use. |
| `jobtracker seed [--force]` | Add sample applications and two saved views. |
| `jobtracker stats [--range 30d\|90d\|180d\|all]` | Print funnel stats. |
| `jobtracker reset [--yes]` | Delete the database and Gmail token. |

## Configuration

Copy `.env.example` to `~/.jobtracker/.env` (or `./.env`). Environment variables win over both.

| Variable | Default | |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Any instruct model that fits your VRAM. |
| `OLLAMA_HOST` | `http://localhost:11434` | |
| `GHOST_DAYS` | `30` | No event for this long (and not finished) → shown as ghosted. |
| `SYNC_INTERVAL_HOURS` | `6` | Background sync interval while the app is open. |
| `BACKFILL_DAYS` | `180` | How far back the first sync reads. The date filter can't go further back than this. |
| `INCLUDE_SENT_THREADS` | `true` | Include whole threads you sent mail in (direct outreach and conversations). |
| `FOLLOW_COMPANY_DOMAINS` | `true` | Include all mail from companies you're in a hiring process with (calendar invites, bookings). |
| `ALWAYS_INCLUDE` / `ALWAYS_IGNORE` | | Comma-separated domains or addresses to always keep / always drop. |
| `GMAIL_EXTRA_QUERY` | | Extra Gmail search added to the main one, e.g. `from:acme.com`. |

**Your own rules:** put subject patterns that are never job emails in `~/.jobtracker/never_job_subjects.txt`,
one regular expression per line (case-insensitive, `#` for comments). They're applied before the model
sees anything, and changing them re-checks previously skipped mail on the next sync.

All personal data — the Gmail token, the OAuth client file, the database and these settings — lives in
`~/.jobtracker/` (or `JOBTRACKER_HOME`), never in the repository.

## Documentation

The full product description, requirements and roadmap are in [docs/PRD.md](docs/PRD.md).

## Development

```bash
uv run pytest                     # backend tests
uv run jobtracker ui --browser --port 8000
cd web && npm run dev             # Vite dev server with /api proxied to :8000
```

Low-confidence or unparseable extractions go to the **Review** page, where you can fix or dismiss
them. Changing an application's stage by hand sets a manual override that later emails won't
change; "Clear override" in the table goes back to the automatic stage.
