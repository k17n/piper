# P.I.P.E.R. Analytics — Feature PRD

| | |
|---|---|
| **Status** | Built |
| **Parent** | [P.I.P.E.R. PRD](PRD.md), §12 Roadmap ("Insights view") |
| **Runs on** | The existing stack: SQLite → FastAPI → React + ECharts. No new services, no new network calls |
| **Privacy** | Unchanged. Every number is computed locally from data already in the database |

---

## 1. Summary

A new **Analytics** tab answers the questions the Dashboard does not: *how much am I applying, to what,
and what is working?* The Dashboard shows where applications ended up (funnel, KPIs). Analytics shows
the **effort and mix over time** — applications per day, the types of roles, where they come from — and
how those choices relate to responses.

## 2. Problem

- The funnel says "12% got an interview" but not whether the user is applying 1 job a day or 10, whether
  that pace is slipping, or whether they have drifted from the roles they actually want.
- Mix questions ("am I mostly applying to Design or Product? LinkedIn or direct?") need a manual
  spreadsheet today.
- `GET /api/insights` already returns per-day counts and per-source rates, but nothing in the UI uses it.

## 3. Goals and non-goals

**Goals**
1. Show **how many applications per day** (and per week / month), with pace and streak.
2. Show **what types of jobs** are being applied to: role type, seniority, source, and the most common
   role titles and companies.
3. Show **what works**: response and interview rates broken down by those same dimensions, with sample
   sizes so small numbers are not over-read.
4. Obey the **same filters and saved views** as every other tab; totals must agree with the Dashboard
   and table for the same filters.
5. Stay glanceable: one scroll, charts first, no configuration needed.

**Non-goals (v1)**
- Predictions, scoring, or advice ("you should apply more on Tuesdays").
- Goal tracking and notifications (listed under §9 as a follow-up).
- Location / remote analytics — location is not stored on applications today (§9).
- Exporting charts.

## 4. Definitions

| Term | Definition |
|---|---|
| **Applied date** | `applications.first_seen` — the date shown in the Applications table's *Applied* column. For emailed applications it is the first email; for manual ones, the date entered. Bucketed in the user's **local** time zone |
| **Application** | One row in `applications`, after the shared filters are applied (the date range filters on Applied date, as everywhere else) |
| **Responded** | Reached `assessment`, `interview`, `offer`, `accepted` or `rejected` (same as `RESPONSE_STAGES` in `stats.py`) |
| **Interviewed** | Reached `interview`, `offer` or `accepted` |
| **Active day** | A day with at least one application |
| **Streak** | Consecutive days, ending today (or yesterday, so an unfinished day does not break it), with at least one application |
| **Seniority** | Derived from the role title; see §6.3 |

## 5. User scenarios

1. *"Am I keeping up?"* — opens Analytics, sees 41 applications in 30 days, a 7-day average of 1.4/day,
   and a 5-day streak. The daily bars show a dead week in the middle.
2. *"What am I actually applying to?"* — sees 58% Product, 31% Design, 8% VC, and that 70% are Senior.
3. *"Is LinkedIn worth it?"* — LinkedIn is 64% of volume but has a 6% response rate against 21% for
   direct outreach (n = 14). The sample-size note stops over-reading it.
4. *"Which days do I apply?"* — the weekday chart shows almost nothing at weekends.

## 6. Functional requirements

All widgets use the shared filter bar (date range, role types, sources, stages, search, ghosted). The
tab shows the filter bar exactly like Dashboard and Applications do.

### 6.1 Summary tiles

Six tiles across the top, using the existing KPI card style:

| Tile | Value | Sub-text |
|---|---|---|
| Applications | count in range | vs. previous period of the same length (▲/▼ %), when the range is not *All* |
| Per active day | applications ÷ active days | "on N active days" |
| Daily average | applications ÷ days in range | the 7-day average for the last 7 days beside it |
| Current streak | days | "longest: N" |
| Best day | max in one day | its date |
| This week | applications since Monday | vs. last week |

### 6.2 Applications over time (primary chart)

- Bar chart of applications per **day**, with a **7-day moving average** line over it.
- **Granularity switch:** Day · Week · Month. Day is the default for ranges ≤ 90 days, Week otherwise.
- Days with no applications appear as zero bars (the series is zero-filled, not sparse).
- Tooltip: date, count, and the company/role of each application that day (capped at 5, "+N more").
- Clicking a bar opens the existing side panel (`AppSheet`) with that day's applications.

### 6.3 What I apply to

| Widget | Chart | Detail |
|---|---|---|
| **Role type mix** | Horizontal bars or donut | Design / Product / VC / Other, count and %. Uses the existing per-application `category` (including manual choices) |
| **Role type over time** | 100% stacked bars per week | Shows drift in focus; hidden when the range has fewer than 3 weeks |
| **Source mix** | Horizontal bars | linkedin / ats / recruiter / direct / referral / other |
| **Seniority mix** | Horizontal bars | Intern · Junior · Mid · Senior · Staff / Principal · Lead · Head / Director+ · Unspecified. Derived by rules from the role title (e.g. "Sr", "Senior", "II", "Staff", "Lead", "Head of", "Director"); no level in the title → Unspecified. "Manager" alone is a job, not a level, so only "Design / Engineering / UX Manager" and "Group Product Manager" count as Lead. Rules live in `categories.py` beside role-type rules, with unit tests |
| **Top role titles** | Ranked list, top 8 | Titles normalised (seniority and punctuation removed) and counted, e.g. "Product Designer ×9" |
| **Top companies** | Ranked list, top 8 | Companies with more than one application, count, and their latest stage |

Each bar or list row is clickable and opens the side panel with those applications.

### 6.4 When I apply

- **Calendar heatmap:** one cell per day (GitHub-style), colour by count, for the filtered range
  (capped to the last 52 weeks). Hover shows the date and count.
- **Day-of-week bars:** total applications per weekday (Mon–Sun), so weekend gaps are obvious.

### 6.5 What works

- **Conversion by dimension:** a table with one row per value for **source**, **role type** and
  **seniority** (a segmented control switches the dimension). Columns: *Applied · Responded % ·
  Interviewed % · Offers · Median days to first response*.
- **Small samples:** rows with fewer than 5 applications show their rates in muted text with a "small
  sample" tooltip. Rates are never shown as bare percentages without the count beside them.
- **Weekly cohorts:** a line chart of response rate for applications grouped by the week they were
  applied, so a recent dip caused by replies that have not arrived yet is not mistaken for a trend.
  The most recent 2 weeks are drawn dashed and labelled "still maturing".
- **Time to first response:** histogram (≤ 2 d, 3–7 d, 8–14 d, 15–30 d, > 30 d) with the median marked.

### 6.6 Pipeline health

- **Open applications by age:** applications that are not terminal, grouped by days since their last
  event (0–7, 8–14, 15–21, 22+). Anything older than `GHOST_DAYS` is already shown as ghosted, so the
  last bucket is the set about to tip over.
- **Outcome split:** share of applications that are active, rejected, ghosted, withdrawn, accepted.

### 6.7 Empty and low-data states

- No applications in range: the same `Empty` component as the Dashboard, with the same hint.
- Fewer than 7 applications: all charts render; the moving average and cohort chart are hidden, with a
  one-line note ("Needs a week of data").
- Every widget handles zero without NaN / divide-by-zero (`_rate` already does).

### 6.8 Behaviour shared with the rest of the app

- Dark and light themes via the existing CSS variables; charts update immediately on theme change, as
  the Sankey does.
- The tab is mirrored in the URL (`?tab=analytics`) with filters and open saved view.
- Charts use a colour for role types and sources that is **the same everywhere** (Dashboard, table
  badges, Analytics), taken from the existing palette in `web/src/lib`.
- Layout: a two-column grid on wide screens, one column below `md`. Nothing causes horizontal page
  scroll.

## 7. Technical design

### 7.1 Backend

- New pure function `compute_analytics(rows: list[AppRow], now: datetime, tz: tzinfo) -> dict` in a new
  `src/piper_jobs/analytics.py`. It takes the rows `load_rows` already returns — **no new queries and no
  schema change**.
- New endpoint `GET /api/analytics?<shared filters>&granularity=day|week|month&tz_offset=<minutes>`
  with the same `Filters` dependency as `/api/stats`. The browser sends its UTC offset so day buckets
  match the user's day; the server never guesses a time zone.
- `GET /api/insights` stays for compatibility and is reimplemented on top of the same helpers.
- `categories.py` gains `seniority(role) -> str` and `normalize_title(role) -> str`.

Response shape:

```json
{
  "range": {"from": "2026-08-01", "to": "2026-10-30"},
  "summary": {
    "total": 41, "previous_total": 33, "active_days": 29, "per_active_day": 1.41,
    "daily_average": 0.45, "last_7d_average": 1.4,
    "streak": 5, "longest_streak": 9,
    "best_day": {"date": "2026-09-12", "count": 6},
    "this_week": 4, "last_week": 7
  },
  "series": [{"date": "2026-10-28", "count": 2, "ids": [12, 15], "apps": [{"id": 12, "company": "Initrode", "role": "Product Designer"}]}],
  "daily": [{"date": "2026-10-28", "count": 2, "ids": [12, 15]}],
  "mix": {
    "category": [{"key": "product", "count": 24, "ids": [12]}],
    "source": [{"key": "linkedin", "count": 26, "ids": [12]}],
    "seniority": [{"key": "senior", "count": 29, "ids": [12]}]
  },
  "category_by_week": [{"week": "2026-10-26", "design": 3, "product": 5, "vc": 0, "other": 1}],
  "top_titles": [{"title": "product designer", "count": 9, "ids": [12]}],
  "top_companies": [{"company": "Initrode", "count": 3, "stage": "interview", "ids": [12]}],
  "weekday": [{"day": 0, "count": 8, "ids": [12]}],
  "conversion": {
    "source":    [{"key": "linkedin", "total": 26, "responded": 0.06, "interviewed": 0.04, "offers": 0, "median_days": 6.1}],
    "category":  [],
    "seniority": []
  },
  "cohorts": [{"week": "2026-10-19", "total": 7, "responded": 0.29, "maturing": false}],
  "response_time": {"buckets": [{"key": "<=2d", "count": 3}], "median": 5.0},
  "open_by_age": [{"key": "0-7d", "count": 6, "ids": [12]}],
  "outcomes": [{"key": "active", "count": 22, "ids": [12]}]
}
```

Series are zero-filled by the server. Rates are 0–1 floats rounded to 4 places, matching `/api/stats`.
`tz_offset` is minutes **ahead of** UTC (UTC+2 is `120`). `outcomes` keys: active, rejected, ghosted,
withdrawn, accepted. `daily` is always per day (it feeds the heatmap) whatever `granularity` is.

### 7.2 Frontend

- `Tab` in `lib/urlState.ts` gains `"analytics"`; `NAV` in `App.tsx` gains
  `{ tab: "analytics", label: "Analytics", icon: "▤" }` between Dashboard and Applications.
- New `web/src/components/analytics/` folder, one small component per widget (`SummaryTiles`,
  `AppsOverTime`, `MixBars`, `CategoryOverTime`, `Heatmap`, `ConversionTable`, `Cohorts`, `ResponseTime`,
  `PipelineHealth`) so each can be understood and tested alone. `AnalyticsTab.tsx` only lays them out.
- `api.analytics(filters, granularity)` in `lib/api.ts`; the query is enabled only on the analytics tab
  (as `stats` and `sankey` are for the Dashboard).
- ECharts (via `echarts-for-react`, as the Sankey uses it) draws the bar and line charts. Plain bars
  and the calendar heatmap are CSS, so they follow the theme without redrawing.
- Every aggregate that can be clicked carries the `ids` of its applications, so the existing side panel
  (`AppSheet`, which takes `Selection { title, ids }`) opens with no change.
- The API computes the "previous period" count by running the same filters shifted back by the range
  length; the pure aggregation function receives it as `previous_total`.

### 7.3 Performance

Aggregation is in memory over the same rows the Dashboard loads; a few thousand applications compute in
well under 100 ms. No caching beyond TanStack Query's.

## 8. Testing and acceptance

**Backend (pytest, `tests/test_analytics.py`)** with fixed `now` and fabricated rows:
- Per-day series is zero-filled and sums to the total.
- Day buckets respect `tz_offset` (an application at 23:30 UTC lands on the next day for UTC+2).
- Streak: ends today, ends yesterday, broken by a gap, empty.
- Week buckets start Monday; month buckets by calendar month.
- Mix counts sum to the total; manual `category` overrides are honoured.
- Seniority and title normalisation over a labelled list ("Sr. Product Designer", "Product Designer II",
  "Head of Product", no role).
- Conversion rates match `compute_stats` for the same rows (**consistency check**: the all-rows
  `responded`/`interviewed` figures equal the Dashboard's response and interview rates).
- Empty input returns the full shape with zeros, not errors.

**API:** `/api/analytics` honours every shared filter and rejects an invalid `granularity` with 422.

**Frontend:** typecheck and build pass; manual check in light and dark theme with `piper seed` data and
with an empty database.

**Acceptance**
- The summary total equals the Dashboard's *Applications* tile and the table's row count for the same filters.
- The sum of every mix chart equals that total.
- Changing a role type in the table updates the Analytics mix on the next load.
- No widget shows `NaN`, `Infinity` or a bare percentage for a group under 5 without the marker.

## 9. Out of scope / follow-ups

| Item | Notes |
|---|---|
| **Goals** | A daily or weekly target (stored in `sync_state`/settings) drawn as a line on the over-time chart, with a "this week 4 / 7" tile. Natural first follow-up |
| **Location and remote** | Needs a `location` column on `applications`, filled from *Fill from link* (`job_page.py` already extracts it) and the model prompt. Unlocks city, country and remote/on-site mix |
| **Time of day** | Hour of the first email; only meaningful for LinkedIn / ATS confirmations, so low value alone |
| **Company size / industry** | Not available from email; would need a lookup, which conflicts with the local-only principle |
| **Compare ranges** | Overlay "previous period" on the over-time chart |
| **Export** | CSV of each table, with the roadmap's Export item |

## 10. Open questions

None open. Settled in the build: **Applied date** uses `first_seen` (matches the table), *Withdrawn*
applications count toward applications per day (the effort happened), and the small-sample marker
applies below 5 applications.
