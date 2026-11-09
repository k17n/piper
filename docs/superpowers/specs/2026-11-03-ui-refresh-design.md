# UI refresh: design

Branch `fix/ui-improvements`. Goal: a calm, precise interface in the manner of Linear and Stripe, in light and dark, with charts that look as good as the rest of the page. Look and feel only: no new features, no API changes.

## Today

- The CSS names Inter but never loads it, so Windows falls back to Segoe UI.
- Icons are Unicode glyphs (◧ ▤ ☰ ◎ ☀ ☾ ✎), which render differently on every system.
- Warm-grey palette, plain blue accent, solid borders, a blur on every card.
- ECharts with near-default styling. ECharts stays: it is the only option here that draws the funnel Sankey.

## Decisions

| Area | Choice |
| --- | --- |
| Direction | Graphite neutrals with one indigo accent |
| Sans | Geist Sans variable, self-hosted via `@fontsource-variable/geist` |
| Mono | Geist Mono variable, only for numbers, dates and IDs |
| Icons | `lucide-react`, 1.5 px stroke, 16 px in controls, 18 px in the sidebar |
| Charts | Keep ECharts, restyle |
| Command palette | Out of scope (decided with the user) |

## Tokens

Defined as CSS variables on `:root` and `.dark`, exposed to Tailwind through `@theme inline` as today. Names stay the same so components keep working; only values change, plus three additions.

| Token | Light | Dark |
| --- | --- | --- |
| `--bg` | `#FAFAFB` | `#09090B` |
| `--surface` | `#FFFFFF` | `#101013` |
| `--surface-2` | `#F4F4F6` | `#17171B` |
| `--border` | `#E7E7EB` | `rgba(255,255,255,0.08)` |
| `--text` | `#0C0C0F` | `#EDEDEF` |
| `--text-2` | `#46464F` | `#B4B4BC` |
| `--muted` | `#6B6B76` | `#8B8B94` |
| `--accent` | `#5457E5` | `#7C7FF5` |
| `--accent-ink` | `#FFFFFF` | `#0B0B14` |
| `--ring` (new) | `rgba(84,87,229,0.35)` | `rgba(124,127,245,0.45)` |
| `--shadow-card` (new) | `0 1px 2px rgba(12,12,15,0.04)` | `inset 0 1px 0 rgba(255,255,255,0.04)` |
| `--shadow-pop` (new) | `0 12px 32px rgba(12,12,15,0.12)` | `0 12px 32px rgba(0,0,0,0.5)` |

Outcome colours (both themes): positive `#30A46C`, negative `#E5484D`.

Pipeline stages are one indigo ramp, light to dark as the funnel advances: applied `#A5B4FC`, viewed `#8E9CF8`, assessment `#7480F3`, interview `#6366F1`, offer `#4F46E5`; then accepted `#30A46C`, rejected `#E5484D`, withdrawn `#8B8B94`, ghosted `#5F5F68`. Outcomes are always shown with a text label.

Role types stay a fixed categorical set, retuned to sit with the indigo: design `#E0629A`, product `#6366F1`, VC `#E5A03A`, other `#8B8B94`.

## Type

- Scale: 11 / 12 / 13 / 14 / 16 / 20 / 28 px. Body is 13 px in dense areas (tables, filters) and 14 px elsewhere.
- Headings use weight 600 with `letter-spacing: -0.01em`; large KPI numbers use `-0.02em`.
- Numbers in KPIs, tables, tooltips and axes use Geist Mono with tabular figures.
- The `PIPER.` wordmark stays, with the accent dots.

## Surfaces and layout

- Radius 10 px for cards and popovers, 8 px for controls, full for badges.
- Cards: 1 px hairline border plus `--shadow-card`. No backdrop blur. Popovers and sheets use `--shadow-pop`.
- Focus: a 3 px `--ring` halo instead of the 2 px solid outline.
- Sidebar: 224 px, no fill, hairline divider. Page content keeps its current widths.
- Spacing on a 4 px grid; section gaps 16 px, card padding 16 px.

## Charts (ECharts)

- Axes: no axis lines, tick labels in `--muted` at 11 px mono, gridlines dotted hairlines (`--border`).
- Bars rounded at the top (4 px); area and line series with a smooth line and a gradient fill fading to transparent.
- Heatmap cells rounded, with a 2 px gap, on a single-hue indigo ramp.
- Tooltips: one shared card (surface, hairline border, `--shadow-pop`, 8 px radius), a colour dot per series, mono values, crosshair on time charts.
- Sankey: thinner nodes, flows at lower opacity that rise on hover, labels in `--text-2`.
- One entrance animation on first render (about 500 ms, ease-out); updates animate at about 250 ms. Both off under reduced motion.
- All colours read from the CSS variables through `chartColors()` as today, so the theme toggle recolours charts.

## Micro-interactions

All of them are CSS transitions or small React state, no animation library. Each is disabled under `prefers-reduced-motion`.

- Sidebar: the active pill slides between items; hovering an item fades its background in over 120 ms.
- Buttons: 1 px press (`scale(0.98)`), primary buttons brighten on hover.
- Theme toggle: the sun and moon swap with a 180° rotation and fade while the colours cross-fade over 200 ms.
- KPI cards: numbers count up once on first load and when filters change.
- Tables: a row highlights on hover and a chevron slides in on the right.
- Tabs: content cross-fades with a 6 px rise (the existing `fade-up`, tuned).
- Sheets and popovers: eased slide and fade; the backdrop fades.
- Insights card: the skeleton shimmers instead of pulsing.
- Icon buttons and the refresh control give feedback (spinner while pending).

## Work order

Each step is its own commit and leaves the app working.

1. **Foundations:** install Geist and `lucide-react`; new tokens; base styles (focus ring, scrollbars, selection); retuned stage and category colours.
2. **Shell:** sidebar with icons and sliding pill, theme toggle, filter bar, buttons, inputs, popovers.
3. **Charts:** shared ECharts theme and tooltip; restyle Sankey, apps-over-time, mix bars, category over time, heatmap, cohorts, conversion table, KPI and summary tiles.
4. **Content:** applications table, detail panel, sheets, review queue, add-application form, empty states.
5. **Motion:** the interactions above, plus a reduced-motion check.

## Verification

- `npm run build` (type check and bundle) after each step.
- Look at every tab in light and dark on the sample data (`PIPER_HOME=D:\piper-sample`) at desktop width and at 390 px width.
- Text contrast of at least 4.5:1 for body text and 3:1 for UI in both themes; keyboard focus visible everywhere.
- Backend tests are untouched; run them once at the end.

## Out of scope

Command palette, new screens or widgets, API or data changes, layout restructuring, a charting library swap.
