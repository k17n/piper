# UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the whole web UI (tokens, fonts, icons, charts, micro-interactions) in a Linear/Stripe-like graphite and indigo look, light and dark.

**Architecture:** Look and feel only. All colour lives in CSS variables on `:root` / `.dark` (names unchanged, plus a few additions), exposed to Tailwind through `@theme inline`. ECharts reads the same variables through `chartColors()` in `web/src/components/analytics/chartTheme.ts`, which becomes the one shared chart theme. Icons come from `lucide-react`. Motion is CSS transitions and small React state, no animation library.

**Tech Stack:** React 19, TypeScript, Vite 6, Tailwind 4, ECharts via `echarts-for-react` (SVG renderer), `@fontsource-variable/geist`, `@fontsource-variable/geist-mono`, `lucide-react`.

Spec: `docs/superpowers/specs/2026-11-03-ui-refresh-design.md`. Work happens in `web/`; run commands from `web/`.

## Global Constraints

- No new features, no API or data changes, no layout restructuring, no charting-library swap, no command palette.
- Token names stay: `--bg --surface --surface-2 --border --text --text-2 --muted --accent --accent-ink`. Additions: `--ring --shadow-card --shadow-pop --positive --negative`.
- Light values: bg `#FAFAFB`, surface `#FFFFFF`, surface-2 `#F4F4F6`, border `#E7E7EB`, text `#0C0C0F`, text-2 `#46464F`, muted `#6B6B76`, accent `#5457E5`, accent-ink `#FFFFFF`.
- Dark values: bg `#09090B`, surface `#101013`, surface-2 `#17171B`, border `rgba(255,255,255,0.08)`, text `#EDEDEF`, text-2 `#B4B4BC`, muted `#8B8B94`, accent `#7C7FF5`, accent-ink `#0B0B14`.
- Positive `#30A46C`, negative `#E5484D` in both themes.
- Stage colours: applied `#A5B4FC`, viewed `#8E9CF8`, assessment `#7480F3`, interview `#6366F1`, offer `#4F46E5`, accepted `#30A46C`, rejected `#E5484D`, withdrawn `#8B8B94`, ghosted `#5F5F68`. Role types: design `#E0629A`, product `#6366F1`, vc `#E5A03A`, other `#8B8B94`.
- Fonts: Geist Sans for the interface, Geist Mono only for numbers, dates and IDs (through the `.tabular` class).
- Radius 10 px cards and popovers, 8 px controls. No backdrop blur on cards. Focus is a 3 px `--ring` halo.
- Every animation and transition is disabled under `prefers-reduced-motion`.
- Both themes must work after every task. Contrast: 4.5:1 body text, 3:1 UI.
- There are no frontend unit tests. The check for each task is `npm run build` (type check + bundle) plus the visual check stated in the task, using sample data: `PIPER_HOME=/d/piper-sample uv run piper ui --browser --port 8000` (already seeded) and `npm run dev` in `web/`.

---

### Task 1: Foundations (fonts, tokens, base styles, colours)

**Files:**
- Modify: `web/package.json` (via npm), `web/src/main.tsx`, `web/src/index.css`, `web/src/lib/stages.ts`

**Interfaces:**
- Produces: CSS variables and Tailwind colour names listed in Global Constraints; Tailwind `font-sans` / `font-mono` mapped to Geist; the `.tabular` class now means "Geist Mono, tabular figures"; `.card` is hairline border + `--shadow-card`; keyframes `slide-in`, `fade-up`, `fade-in`, `pop-in`, `shimmer` and classes `.anim-slide-in`, `.anim-fade-up`, `.anim-fade-in`, `.anim-pop-in`, `.skeleton`.

- [ ] **Step 1: Install packages**

```bash
cd web && npm install @fontsource-variable/geist @fontsource-variable/geist-mono lucide-react
```
Expected: three packages added to `dependencies`, no errors.

- [ ] **Step 2: Load the fonts**

Read `web/src/main.tsx`. Add these two lines above the existing `import "./index.css";` line:

```ts
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
```

- [ ] **Step 3: Replace `web/src/index.css`** with:

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

:root {
  color-scheme: light;
  --bg: #fafafb;
  --surface: #ffffff;
  --surface-2: #f4f4f6;
  --border: #e7e7eb;
  --text: #0c0c0f;
  --text-2: #46464f;
  --muted: #6b6b76;
  --accent: #5457e5;
  --accent-ink: #ffffff;
  --ring: rgba(84, 87, 229, 0.35);
  --positive: #30a46c;
  --negative: #e5484d;
  --shadow-card: 0 1px 2px rgba(12, 12, 15, 0.04);
  --shadow-pop: 0 12px 32px rgba(12, 12, 15, 0.12);
}

.dark {
  color-scheme: dark;
  --bg: #09090b;
  --surface: #101013;
  --surface-2: #17171b;
  --border: rgba(255, 255, 255, 0.08);
  --text: #ededef;
  --text-2: #b4b4bc;
  --muted: #8b8b94;
  --accent: #7c7ff5;
  --accent-ink: #0b0b14;
  --ring: rgba(124, 127, 245, 0.45);
  --shadow-card: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  --shadow-pop: 0 12px 32px rgba(0, 0, 0, 0.5);
}

@theme inline {
  --color-bg: var(--bg);
  --color-surface: var(--surface);
  --color-surface-2: var(--surface-2);
  --color-line: var(--border);
  --color-ink: var(--text);
  --color-ink-2: var(--text-2);
  --color-muted: var(--muted);
  --color-accent: var(--accent);
  --color-accent-ink: var(--accent-ink);
  --color-positive: var(--positive);
  --color-negative: var(--negative);
  --font-sans: "Geist Variable", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "Geist Mono Variable", ui-monospace, "Cascadia Mono", Consolas, monospace;
}

@layer base {
  html,
  body,
  #root {
    height: 100%;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: 14px;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }

  h1,
  h2,
  h3 {
    letter-spacing: -0.01em;
  }

  ::selection {
    background: var(--ring);
  }

  * {
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow-card);
  }

  /* Numbers, dates and IDs: Geist Mono with tabular figures. */
  .tabular {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;
  }

  input,
  select,
  textarea {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    transition:
      border-color 120ms,
      box-shadow 120ms,
      background-color 120ms;
  }

  input::placeholder,
  textarea::placeholder {
    color: var(--muted);
  }

  /* The open option list is drawn by the browser engine; the app window (WebView2) ignores
     color-scheme there, so give options explicit theme colors. */
  option,
  optgroup {
    background-color: var(--surface);
    color: var(--text);
  }

  input:focus,
  select:focus,
  textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--ring);
  }

  button:focus-visible,
  a:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--ring);
    border-radius: 8px;
  }
}

@keyframes slide-in {
  from {
    transform: translateX(24px);
    opacity: 0;
  }
  to {
    transform: none;
    opacity: 1;
  }
}

@keyframes fade-up {
  from {
    transform: translateY(6px);
    opacity: 0;
  }
  to {
    transform: none;
    opacity: 1;
  }
}

@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes pop-in {
  from {
    transform: translateY(-4px) scale(0.98);
    opacity: 0;
  }
  to {
    transform: none;
    opacity: 1;
  }
}

@keyframes shimmer {
  from {
    background-position: 200% 0;
  }
  to {
    background-position: -200% 0;
  }
}

.anim-slide-in {
  animation: slide-in 260ms cubic-bezier(0.16, 1, 0.3, 1);
}

.anim-fade-up {
  animation: fade-up 260ms cubic-bezier(0.16, 1, 0.3, 1);
}

.anim-fade-in {
  animation: fade-in 180ms ease-out;
}

.anim-pop-in {
  animation: pop-in 140ms cubic-bezier(0.16, 1, 0.3, 1);
  transform-origin: top left;
}

/* Placeholder block for content that is loading. */
.skeleton {
  background: linear-gradient(90deg, var(--surface-2) 30%, color-mix(in srgb, var(--text) 7%, var(--surface-2)) 50%, var(--surface-2) 70%);
  background-size: 200% 100%;
  animation: shimmer 1.6s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 4: Retune stage and category colours in `web/src/lib/stages.ts`**

Replace the `STAGE_COLOR` block, `SOURCE_COLOR`, the comment above `STAGE_COLOR`, and `CATEGORY_COLOR` with:

```ts
// Progress stages: one indigo ramp, light→dark as the funnel advances.
// Outcomes: reserved status colors (always shown with a text label). Neutral grays otherwise.
const STAGE_COLOR: Record<Stage, string> = {
  applied: "#a5b4fc",
  viewed: "#8e9cf8",
  assessment: "#7480f3",
  interview: "#6366f1",
  offer: "#4f46e5",
  accepted: "#30a46c",
  rejected: "#e5484d",
  withdrawn: "#8b8b94",
  ghosted: "#5f5f68",
};
export const SOURCE_COLOR = "#8b8b94";

export const stageColor = (s: string) => STAGE_COLOR[s as Stage] ?? SOURCE_COLOR;

// Role types are a categorical series, so each keeps one colour everywhere it is drawn.
export const CATEGORY_COLOR: Record<Category, string> = {
  design: "#e0629a",
  product: "#6366f1",
  vc: "#e5a03a",
  other: "#8b8b94",
};
```
(Keep the `stageColor` export only once: delete the old definition.)

- [ ] **Step 5: Verify**

Run: `npm run build`
Expected: succeeds, no type errors.
Then run `npm run dev` with the sample backend and open every tab in dark and light: text is Geist (not Segoe UI), numbers in KPIs and tables are monospaced, cards have a hairline border and no blur, the accent is indigo, focus on any input shows a soft halo.

- [ ] **Step 6: Commit**

```bash
git add web/package.json web/package-lock.json web/src/main.tsx web/src/index.css web/src/lib/stages.ts
git commit -m "feat(ui): Geist fonts, graphite and indigo tokens, base styles"
```

---

### Task 2: Shell (icons, sidebar, buttons, filter bar)

**Files:**
- Modify: `web/src/components/ui.tsx`, `web/src/App.tsx`, `web/src/components/FilterBar.tsx`, `web/src/components/ViewPicker.tsx`, `web/src/components/SyncIndicator.tsx`, `web/src/components/analytics/InsightsCard.tsx`

**Interfaces:**
- Consumes: tokens and `.anim-pop-in` from Task 1.
- Produces: `Button` gains `label?: string` (becomes `aria-label`), press feedback; `Empty` gains `icon?: ReactNode`; lucide icons everywhere the shell used glyphs. Later tasks import icons from `lucide-react` directly.

- [ ] **Step 1: Confirm icon names exist in the installed lucide-react**

Run:
```bash
node -e "const l=require('lucide-react');const n=['LayoutDashboard','ChartColumn','Rows3','Inbox','Sun','Moon','ChevronDown','ChevronUp','ChevronRight','X','Pencil','ExternalLink','Star','Plus','RefreshCw','SearchX'];console.log(n.filter(x=>!l[x]))"
```
Expected: `[]`. If a name is listed, pick the closest existing icon (look in `node_modules/lucide-react/dist/lucide-react.d.ts`) and use it consistently in later tasks.

- [ ] **Step 2: `web/src/components/ui.tsx`: Button, StageBadge, Empty, Popover**

Replace the `Button` component with:

```tsx
export function Button({
  children,
  onClick,
  variant = "ghost",
  disabled,
  title,
  label,
  className,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "outline" | "danger";
  disabled?: boolean;
  title?: string;
  /** Accessible name for buttons that show only an icon. */
  label?: string;
  className?: string;
  type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-accent text-accent-ink shadow-sm hover:brightness-110",
    ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink",
    outline: "border border-line text-ink-2 hover:bg-surface-2 hover:text-ink",
    danger: "text-negative hover:bg-negative/10",
  }[variant];
  return (
    <button
      type={type}
      title={title}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={cx(
        "inline-flex h-8 select-none items-center gap-1.5 whitespace-nowrap rounded-lg px-3 text-[13px] font-medium transition-[background-color,color,filter,transform] duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40",
        styles,
        className,
      )}
    >
      {children}
    </button>
  );
}
```

In `Popover`, change the panel's className string to:
```tsx
"anim-pop-in absolute top-full z-40 mt-1.5 rounded-[10px] border border-line bg-surface p-1.5 shadow-[var(--shadow-pop)]",
```
(keep the `align === "right" ? "right-0" : "left-0"` argument).

At the top of the file add `import { Pencil } from "lucide-react";`. In `StageBadge` replace the `✎` span with:
```tsx
{override && <Pencil size={11} aria-label="Set manually" className="text-muted" />}
```
and replace the dot span so the badge reads: dot `h-1.5 w-1.5`, text `text-xs`.

Replace `Empty` with:

```tsx
export function Empty({ title, icon, children }: { title: string; icon?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      {icon && <div className="mb-1 flex size-10 items-center justify-center rounded-full bg-surface-2 text-muted">{icon}</div>}
      <div className="text-[15px] font-medium text-ink">{title}</div>
      {children && <div className="max-w-md text-sm text-ink-2">{children}</div>}
    </div>
  );
}
```

- [ ] **Step 3: `web/src/App.tsx`: nav icons, sliding pill, theme toggle**

Add imports: `import { ChartColumn, Inbox, LayoutDashboard, Moon, Plus, Rows3, SearchX, Sun, type LucideIcon } from "lucide-react";`

Replace the `NAV` constant with:

```tsx
const NAV: { tab: Tab; label: string; icon: LucideIcon }[] = [
  { tab: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { tab: "analytics", label: "Analytics", icon: ChartColumn },
  { tab: "applications", label: "Applications", icon: Rows3 },
  { tab: "review", label: "Review", icon: Inbox },
];
const NAV_ROW = 36; // h-9
const NAV_GAP = 2; // gap-0.5
```

Replace the `<nav>…</nav>` block with:

```tsx
<nav className="relative flex flex-col gap-0.5">
  <div
    aria-hidden
    className="pointer-events-none absolute inset-x-0 top-0 rounded-lg bg-surface-2 transition-transform duration-200 ease-[cubic-bezier(0.16,1,0.3,1)]"
    style={{ height: NAV_ROW, transform: `translateY(${NAV.findIndex((n) => n.tab === tab) * (NAV_ROW + NAV_GAP)}px)` }}
  />
  {NAV.map((n) => {
    const active = tab === n.tab;
    return (
      <button
        key={n.tab}
        onClick={() => setTab(n.tab)}
        aria-current={active ? "page" : undefined}
        className={cx(
          "relative flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[13px] transition-colors duration-150",
          active ? "font-medium text-ink" : "text-ink-2 hover:text-ink",
        )}
      >
        <n.icon size={16} strokeWidth={1.75} className={cx("transition-colors duration-150", active ? "text-accent" : "text-muted")} />
        {n.label}
        {n.tab === "review" && reviewCount > 0 && (
          <span className="tabular ml-auto rounded-full bg-accent px-1.5 text-[11px] font-medium text-accent-ink">{reviewCount}</span>
        )}
      </button>
    );
  })}
</nav>
```

Replace the theme `Button` in the sidebar footer with:

```tsx
<Button onClick={toggle} label={dark ? "Switch to light theme" : "Switch to dark theme"} title="Toggle theme" className="relative size-7 justify-center px-0">
  <Sun size={15} className={cx("absolute transition-all duration-300", dark ? "rotate-0 opacity-100" : "rotate-90 opacity-0")} />
  <Moon size={15} className={cx("absolute transition-all duration-300", dark ? "-rotate-90 opacity-0" : "rotate-0 opacity-100")} />
</Button>
```

Change the "+ Add application" button content to `<Plus size={14} /> Add application`. In the funnel empty state add `icon={<SearchX size={18} />}` to `<Empty …>`. Change the sidebar `aside` background class `bg-surface/60` to `bg-bg`. Change the sticky filter header's `bg-bg/85 … backdrop-blur` to `bg-bg/90 backdrop-blur-sm` (this is chrome, not a card, so a light blur stays).

- [ ] **Step 4: Replace glyphs in the filter bar and view picker**

`web/src/components/FilterBar.tsx` line ~54 and `web/src/components/ViewPicker.tsx` line ~70: replace `<span className="text-muted">▾</span>` with `<ChevronDown size={14} className="text-muted" />` and import `ChevronDown` from `lucide-react`.

In `ViewPicker.tsx` (around lines 108-125): replace `{v.is_default ? "★" : "☆"}` with `<Star size={14} className={v.is_default ? "fill-current" : ""} />`, the `✎` with `<Pencil size={13} />`, the `✕` with `<X size={14} />`. Give each of those buttons a `label` or `aria-label` ("Default view", "Rename view", "Delete view") if they do not have one. Import `Pencil, Star, X`.

Filter-bar trigger buttons: change `rounded-lg border border-line px-3 text-sm` to `rounded-lg border border-line px-3 text-[13px]` and keep the rest.

- [ ] **Step 5: `web/src/components/SyncIndicator.tsx`**

Import `RefreshCw` from `lucide-react`. Replace the primary Button with:

```tsx
<Button variant="primary" className="justify-center" disabled={running} onClick={() => api.startSync()}>
  <RefreshCw size={14} className={running ? "animate-spin" : ""} />
  {running ? "Syncing…" : "Sync now"}
</Button>
```
Replace `text-[#d03b3b]` with `text-negative`.

- [ ] **Step 6: `web/src/components/analytics/InsightsCard.tsx`**

Import `RefreshCw`. Replace the refresh Button block with:

```tsx
<Button onClick={() => refresh.mutate()} disabled={refresh.isPending} title="Write it again with different wording" label="Write the summary again" className="size-7 justify-center px-0">
  <RefreshCw size={14} className={refresh.isPending ? "animate-spin" : ""} />
</Button>
```
In `Skeleton`, replace each `animate-pulse rounded bg-surface-2` with `skeleton rounded`.

- [ ] **Step 7: Verify and commit**

Run: `npm run build` → succeeds.
Visual: sidebar shows icons, the pill slides when switching tabs, the sun/moon rotate on toggle, filter bar chevrons are icons, Sync now spins while syncing, Insights skeleton shimmers. Check light and dark.

```bash
git add -A web/src
git commit -m "feat(ui): lucide icons, sliding nav pill, refreshed buttons and filter bar"
```

---

### Task 3: Charts (shared theme, every chart and tile)

**Files:**
- Modify: `web/src/components/analytics/chartTheme.ts`, `AppsOverTime.tsx`, `CategoryOverTime.tsx`, `Cohorts.tsx`, `Heatmap.tsx`, `MixBars.tsx`, `Section.tsx`, `SummaryTiles.tsx`, `web/src/components/KpiCards.tsx`, `web/src/components/SankeyChart.tsx`

**Interfaces:**
- Consumes: tokens from Task 1; `esc`, `fmtBucket`, `pct`, `parseDay` from `analytics/format.ts` (unchanged).
- Produces in `chartTheme.ts`: `ChartColors` (adds `shadow`), `MONO`, `SANS`, `alpha(hex, a)`, `categoryAxis(c, labels)`, `valueAxis(c, opts)`, `tooltipStyle(c)`, `tip(title, rows, note?)`, `reducedMotion()`, `chartColors()`.

- [ ] **Step 1: Replace `web/src/components/analytics/chartTheme.ts`** with:

```ts
export interface ChartColors {
  ink: string;
  ink2: string;
  muted: string;
  line: string;
  surface: string;
  accent: string;
  shadow: string;
}

// Single quotes: these strings are also embedded in style="…" attributes inside tooltip HTML.
export const MONO = "'Geist Mono Variable', ui-monospace, Consolas, monospace";
export const SANS = "'Geist Variable', system-ui, sans-serif";

/** Read the live theme colours; call inside a memo that depends on `dark` so charts follow the toggle. */
export function chartColors(): ChartColors {
  const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return {
    ink: css("--text"),
    ink2: css("--text-2"),
    muted: css("--muted"),
    line: css("--border"),
    surface: css("--surface"),
    accent: css("--accent"),
    shadow: css("--shadow-pop"),
  };
}

/** `#rrggbb` + opacity → `rgba(...)`. */
export function alpha(hex: string, a: number) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.replace(/./g, "$&$&") : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

const axisLabel = (c: ChartColors, extra: object = {}) => ({ color: c.muted, fontSize: 11, fontFamily: MONO, ...extra });

export const categoryAxis = (c: ChartColors, labels: string[]) => ({
  type: "category" as const,
  data: labels,
  axisLabel: axisLabel(c, { hideOverlap: true }),
  axisLine: { show: false },
  axisTick: { show: false },
});

export const valueAxis = (c: ChartColors, o: { formatter?: string; min?: number; max?: number; minInterval?: number } = {}) => {
  const { formatter, ...rest } = o;
  return {
    type: "value" as const,
    ...rest,
    axisLabel: axisLabel(c, formatter ? { formatter } : {}),
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: c.line, type: "dotted" as const } },
  };
};

export const tooltipStyle = (c: ChartColors) => ({
  backgroundColor: c.surface,
  borderColor: c.line,
  borderWidth: 1,
  padding: [8, 10],
  textStyle: { color: c.ink, fontSize: 12, fontFamily: SANS },
  extraCssText: `border-radius:8px;box-shadow:${c.shadow};`,
  axisPointer: { lineStyle: { color: c.line, type: "dotted" }, shadowStyle: { color: alpha(c.ink.startsWith("#") ? c.ink : "#888888", 0.05) } },
});

/** Tooltip body: bold title, then rows with an optional colour dot and a right-aligned mono value. Callers escape text. */
export function tip(title: string, rows: { dot?: string; label: string; value?: string }[] = [], note = "") {
  const body = rows
    .map(
      (r) =>
        `<div style="display:flex;align-items:center;gap:8px;margin-top:4px">${
          r.dot ? `<span style="width:8px;height:8px;border-radius:999px;background:${r.dot}"></span>` : ""
        }<span style="flex:1;opacity:.8">${r.label}</span>${
          r.value ? `<span style="font-family:${MONO};margin-left:12px">${r.value}</span>` : ""
        }</div>`,
    )
    .join("");
  return `<div style="font-weight:600">${title}</div>${body}${note ? `<div style="margin-top:6px;opacity:.6">${note}</div>` : ""}`;
}

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
```

- [ ] **Step 2: `AppsOverTime.tsx`**

Change the import to `import { alpha, categoryAxis, chartColors, reducedMotion, tip, tooltipStyle, valueAxis } from "./chartTheme";`.

Replace the `option` object (everything returned inside `useMemo`) with:

```tsx
return {
  animation: !reducedMotion(),
  animationDuration: 500,
  animationEasing: "cubicOut",
  grid: { left: 28, right: 8, top: 12, bottom: 24 },
  tooltip: {
    trigger: "axis",
    ...tooltipStyle(c),
    axisPointer: { type: "shadow", shadowStyle: { color: alpha(c.accent, 0.08) } },
    formatter: (params: { dataIndex: number }[]) => {
      const p = data[params[0].dataIndex];
      const rows = (p.apps ?? []).map((a) => ({ label: `${esc(a.company)} <span style="opacity:.6">· ${esc(a.role || "role not stated")}</span>` }));
      const more = p.count - rows.length;
      const avg = average?.[params[0].dataIndex];
      return tip(
        `${fmtBucket(p.date, granularity)} · ${p.count} application${p.count === 1 ? "" : "s"}`,
        rows,
        [more > 0 ? `+${more} more` : "", avg != null ? `7-day average ${avg}` : ""].filter(Boolean).join("<br/>"),
      );
    },
  },
  xAxis: categoryAxis(c, data.map((p) => fmtBucket(p.date, granularity))),
  yAxis: valueAxis(c, { minInterval: 1 }),
  series: [
    {
      name: "Applications",
      type: "bar",
      data: counts,
      barMaxWidth: 24,
      itemStyle: { color: alpha(c.accent, 0.85), borderRadius: [4, 4, 0, 0] },
      emphasis: { itemStyle: { color: c.accent } },
    },
    ...(average
      ? [{ name: "7-day average", type: "line", data: average, smooth: true, showSymbol: false, z: 3, lineStyle: { color: c.ink2, width: 1.5 }, itemStyle: { color: c.ink2 } }]
      : []),
  ],
};
```
Set the chart height `style={{ height: 280, …}}` unchanged.

- [ ] **Step 3: Replace `CategoryOverTime.tsx`** with:

```tsx
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { Analytics } from "../../lib/api";
import { CATEGORIES, CATEGORY_COLOR, categoryLabel } from "../../lib/stages";
import { categoryAxis, chartColors, MONO, reducedMotion, tip, tooltipStyle, valueAxis } from "./chartTheme";
import { fmtBucket, pct } from "./format";

export function CategoryOverTime({ data, dark }: { data: Analytics["category_by_week"]; dark: boolean }) {
  const option = useMemo(() => {
    const c = chartColors();
    const totals = data.map((w) => CATEGORIES.reduce((sum, cat) => sum + w[cat.value], 0));
    return {
      animation: !reducedMotion(),
      animationDuration: 500,
      animationEasing: "cubicOut",
      grid: { left: 36, right: 8, top: 8, bottom: 36 },
      legend: { bottom: 0, textStyle: { color: c.ink2, fontSize: 11 }, icon: "circle", itemWidth: 8, itemHeight: 8, itemGap: 16 },
      tooltip: {
        trigger: "axis",
        ...tooltipStyle(c),
        axisPointer: { type: "shadow", shadowStyle: { color: "rgba(128,128,128,0.08)" } },
        formatter: (params: { dataIndex: number }[]) => {
          const i = params[0].dataIndex;
          const w = data[i];
          const rows = CATEGORIES.filter((cat) => w[cat.value] > 0).map((cat) => ({
            dot: CATEGORY_COLOR[cat.value],
            label: categoryLabel(cat.value),
            value: `${w[cat.value]} · ${pct(w[cat.value] / totals[i])}`,
          }));
          return tip(`${fmtBucket(w.week, "week")} · ${totals[i]} applications`, rows);
        },
      },
      xAxis: categoryAxis(c, data.map((w) => fmtBucket(w.week, "day"))),
      yAxis: valueAxis(c, { max: 100, formatter: "{value}%" }),
      series: CATEGORIES.map((cat) => ({
        name: cat.label,
        type: "bar",
        stack: "share",
        barMaxWidth: 28,
        itemStyle: { color: CATEGORY_COLOR[cat.value], borderColor: c.surface, borderWidth: 1 },
        data: data.map((w, i) => (totals[i] ? (w[cat.value] / totals[i]) * 100 : 0)),
      })),
      textStyle: { fontFamily: MONO },
    };
  }, [data, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  return <ReactECharts option={option} notMerge style={{ height: 260, width: "100%" }} opts={{ renderer: "svg" }} />;
}
```

- [ ] **Step 4: Replace `Cohorts.tsx`** with:

```tsx
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { Analytics } from "../../lib/api";
import { alpha, categoryAxis, chartColors, reducedMotion, tip, tooltipStyle, valueAxis } from "./chartTheme";
import { fmtBucket, pct } from "./format";

/** Response rate by the week an application was sent. The newest weeks are dashed: replies may not be in yet. */
export function Cohorts({ data, dark }: { data: Analytics["cohorts"]; dark: boolean }) {
  const option = useMemo(() => {
    const c = chartColors();
    const rate = (i: number) => Math.round(data[i].responded * 1000) / 10;
    let lastMature = -1;
    data.forEach((p, i) => {
      if (!p.maturing) lastMature = i;
    });
    const fade = {
      type: "linear",
      x: 0,
      y: 0,
      x2: 0,
      y2: 1,
      colorStops: [
        { offset: 0, color: alpha(c.accent, 0.28) },
        { offset: 1, color: alpha(c.accent, 0) },
      ],
    };
    return {
      animation: !reducedMotion(),
      animationDuration: 500,
      animationEasing: "cubicOut",
      grid: { left: 36, right: 8, top: 8, bottom: 24 },
      tooltip: {
        trigger: "axis",
        ...tooltipStyle(c),
        formatter: (params: { dataIndex: number }[]) => {
          const p = data[params[0].dataIndex];
          const small = p.total < 5 ? " (small sample)" : "";
          return tip(fmtBucket(p.week, "week"), [{ label: "Responded", value: pct(p.responded) }, { label: "Applied", value: `${p.total}${small}` }], p.maturing ? "still maturing" : "");
        },
      },
      xAxis: categoryAxis(c, data.map((p) => fmtBucket(p.week, "day"))),
      yAxis: valueAxis(c, { min: 0, max: 100, formatter: "{value}%" }),
      series: [
        {
          type: "line",
          smooth: true,
          data: data.map((p, i) => (p.maturing ? null : rate(i))),
          symbolSize: 6,
          lineStyle: { color: c.accent, width: 2 },
          itemStyle: { color: c.accent, borderColor: c.surface, borderWidth: 2 },
          areaStyle: { color: fade },
        },
        {
          type: "line",
          smooth: true,
          data: data.map((p, i) => (p.maturing || i === lastMature ? rate(i) : null)),
          symbolSize: 6,
          lineStyle: { color: c.accent, width: 2, type: "dashed", opacity: 0.6 },
          itemStyle: { color: c.accent, opacity: 0.6 },
        },
      ],
    };
  }, [data, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  return <ReactECharts option={option} notMerge style={{ height: 220, width: "100%" }} opts={{ renderer: "svg" }} />;
}
```

- [ ] **Step 5: `Heatmap.tsx`**: rounder cells, tighter gap, hover lift

Change `gap-[3px]` to `gap-[2px]`, and every cell's `rounded-[3px]` to `rounded-[4px]`. On the day `<button>` use className:
```tsx
className="size-3 rounded-[4px] transition-transform duration-100 enabled:hover:scale-125 disabled:cursor-default"
```
Replace the `shade` function with `level === 0 ? "var(--surface-2)" : \`color-mix(in srgb, var(--accent) ${25 + (75 / LEVELS) * level}%, var(--surface-2))\`` (so level 1 is a visible tint, level 4 is full accent).

- [ ] **Step 6: Replace `MixBars.tsx` row markup**

Replace the `<li>…</li>` content: the button className → `"grid w-full grid-cols-[minmax(6rem,11rem)_1fr_5rem] items-center gap-3 rounded-md px-1.5 py-1 text-left text-[13px] transition-colors " + (clickable ? "hover:bg-surface-2" : "cursor-default")`. The track span → `<span className="h-1.5 rounded-full bg-surface-2">`, the fill span → `<span className="block h-full rounded-full transition-[width] duration-500 ease-out" style={{ width: \`${(i.count / max) * 100}%\`, background: i.color ?? "var(--accent)" }} />`. Keep the count span with `tabular`.

- [ ] **Step 7: `Section.tsx`**

Section title → `className="text-[13px] font-semibold text-ink"`. Replace `Segmented`'s wrapper and button classes: wrapper `"flex rounded-lg bg-surface-2 p-0.5 text-xs"`; button `cx("h-6 rounded-md px-2.5 transition-colors", o.value === value ? "bg-surface font-medium text-ink shadow-[var(--shadow-card)]" : "text-ink-2 hover:text-ink")`.

- [ ] **Step 8: Tiles (`KpiCards.tsx`, `SummaryTiles.tsx`)**

In `Kpi`: label `text-xs font-medium text-muted`; number `tabular text-[28px] font-semibold leading-tight text-ink`; hint `text-xs text-muted`; card padding `px-4 py-3.5`.

In `SummaryTiles.tsx` replace `versus` with:

```tsx
function versus(now: number, before: number | null, what: string) {
  if (before == null) return undefined;
  if (before === 0) return now > 0 ? `up from none ${what}` : `same as ${what}`;
  const change = Math.round(((now - before) / before) * 100);
  if (change === 0) return `same as ${what}`;
  return `${change > 0 ? "+" : "−"}${Math.abs(change)}% vs ${what}`;
}
```

- [ ] **Step 9: `SankeyChart.tsx`**

Import `{ chartColors, tip, tooltipStyle }` from `./analytics/chartTheme`. Replace the four `cssVar` lines (`ink`, `ink2`, `surface`, `border`) and `cssVar` helper with `const c = chartColors();` and use `c.ink`, `c.ink2`, `c.surface`. Replace the `tooltip` with:

```tsx
tooltip: {
  trigger: "item",
  ...tooltipStyle(c),
  formatter: (p: { dataType: string; data: { source: string; target: string; value: number; name: string } }) => {
    if (p.dataType === "edge") {
      const { source, target, value } = p.data;
      const share = Math.round((value / (nodeTotal(source) || 1)) * 100);
      return tip(`${source} → ${target}`, [{ label: `${value} application${value === 1 ? "" : "s"}`, value: `${share}% of ${source}` }]);
    }
    const n = nodeTotal(p.data.name);
    return tip(p.data.name, [{ label: `${n} application${n === 1 ? "" : "s"}` }]);
  },
},
```
In the series: `nodeWidth: 8`, `nodeGap: 12`; node `itemStyle`: remove `borderColor`/`borderWidth`, `borderRadius: 2`; `lineStyle: { color: "gradient", curveness: 0.5, opacity: dark ? 0.3 : 0.24 }`; add `emphasis: { focus: "adjacency", lineStyle: { opacity: 0.55 } }` (replace the existing `emphasis`); in `label.rich` set `name: { color: c.ink, fontSize: 12, fontWeight: 500 }` and `count: { color: c.muted, fontSize: 11, fontFamily: MONO }` (import `MONO`). Set `animationDuration: 600`.

- [ ] **Step 10: Verify and commit**

Run: `npm run build` → succeeds.
Visual (sample data, both themes, 180d range): Dashboard Sankey has thin nodes and soft flows; Analytics: bars are softly rounded with a shaded hover column, grid lines are dotted, axis numbers are mono, tooltips are the shared card, Cohorts has a fading area, heatmap cells are rounded, mix bars are slim pills, tiles use 28 px mono numbers. Toggle the theme and confirm charts recolour.

```bash
git add -A web/src
git commit -m "feat(ui): shared chart theme and restyled charts and tiles"
```

---

### Task 4: Content (tables, sheets, forms, empty states)

**Files:**
- Modify: `web/src/components/ApplicationsTable.tsx`, `AppSheet.tsx`, `ApplicationDetail.tsx`, `ReviewQueue.tsx`, `AddApplication.tsx`, `analytics/ConversionTable.tsx`

**Interfaces:**
- Consumes: `Button` `label` prop, `Empty` `icon` prop (Task 2); lucide icons.

- [ ] **Step 1: `ApplicationsTable.tsx`**

Import `{ ChevronDown, ChevronRight, ChevronUp, ExternalLink, Pencil, SearchX }` from `lucide-react`.

- Sort indicator: replace the `<span className={cx("text-[10px]", …)}>{sort.dir === 1 ? "▲" : "▼"}</span>` with
  ```tsx
  {sort.key === c.key ? sort.dir === 1 ? <ChevronUp size={12} /> : <ChevronDown size={12} /> : <span className="size-3" />}
  ```
- Header row: `className="border-b border-line text-left text-xs text-muted"`; th `px-3 py-2.5 font-medium`.
- Table: `className="w-full text-[13px]"`.
- Row: `<tr … className="group border-b border-line/60 transition-colors hover:bg-surface-2/60">`.
- Company cell: after the job-link anchor add a chevron that slides in on row hover:
  ```tsx
  <ChevronRight size={14} className="ml-1 inline -translate-x-1 text-muted opacity-0 transition-all duration-150 group-hover:translate-x-0 group-hover:opacity-100" />
  ```
  Replace the `↗` job link text with `<ExternalLink size={12} className="inline" />` (keep its `title`, and add `aria-label="Open job posting"`).
- Category override pencil: replace `✎` with `<Pencil size={12} />` and add `aria-label="Detect the role type automatically again"`.
- Stage override button: replace `✎ clear` with `<Pencil size={11} className="mr-1 inline" />clear`.
- Empty: `<Empty icon={<SearchX size={18} />} title="No applications match these filters">…`.
- Row-number cells already use `tabular` (now mono).

- [ ] **Step 2: `AppSheet.tsx`**

Import `X` from `lucide-react`. Backdrop: `className="anim-fade-in fixed inset-0 z-50 flex justify-end bg-black/40"`. Aside: `anim-slide-in … border-l border-line bg-surface shadow-[var(--shadow-pop)]` (replace `shadow-2xl`). Close button: `<Button onClick={onClose} title="Close" label="Close"><X size={16} /></Button>` with `className="size-8 justify-center px-0"`. Result rows: `className="block w-full rounded-[10px] px-3 py-3 text-left transition-colors hover:bg-surface-2"`. The "Loading…" line becomes three `skeleton` rows: `<div className="flex flex-col gap-2 p-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-14 rounded-lg" />)}</div>`.

- [ ] **Step 3: `ApplicationDetail.tsx`, `ReviewQueue.tsx`, `AddApplication.tsx`**

Import the needed icons from `lucide-react` in each file and replace glyphs:

| File | Old | New |
| --- | --- | --- |
| `ApplicationDetail.tsx` ~60, `ReviewQueue.tsx` ~52 | `Open in Gmail ↗` | `Open in Gmail <ExternalLink size={12} className="inline" />` |
| `ApplicationDetail.tsx` ~170 | `Job posting ↗` | `Job posting <ExternalLink size={12} className="inline" />` |
| `ApplicationDetail.tsx` ~189 | `+ Add job posting link` | `<Plus size={14} /> Add job posting link` |
| `ApplicationDetail.tsx` ~212 | `+ Log an update` | `<Plus size={14} /> Log an update` |
| `ApplicationDetail.tsx` ~307, `AddApplication.tsx` ~74 | `✕` | `<X size={16} />` and give the wrapping `Button` `label="Close"` |

For modals/panels in `ApplicationDetail.tsx` and `AddApplication.tsx`: backdrop gets `anim-fade-in`; replace `shadow-2xl` with `shadow-[var(--shadow-pop)]`; any `rounded-2xl` becomes `rounded-[10px]`. Replace any remaining hard-coded hex colours (`#d03b3b` etc.) with `text-negative` / `bg-negative`.

- [ ] **Step 4: `ConversionTable.tsx`**

Header row `text-xs text-muted` (already); row border `border-t border-line` stays; add `transition-colors hover:bg-surface-2/60` to each body `<tr>`.

- [ ] **Step 5: Verify and commit**

Run: `npm run build` → succeeds.
Visual: Applications table row hover shows the sliding chevron; sort arrows are icons; open a sheet (click a chart bar) and the detail panel: icons replace glyphs, backdrop fades, panel slides; empty state shows the icon circle; check light and dark and a 390 px wide window.

```bash
git add -A web/src
git commit -m "feat(ui): icons, hover affordances and softer overlays in tables and sheets"
```

---

### Task 5: Motion polish and final pass

**Files:**
- Modify: `web/src/App.tsx`, `web/src/index.css`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Theme cross-fade**

In `index.css` add (outside `@layer`):

```css
/* While the theme switches, fade colours instead of snapping. Added and removed by the toggle in App.tsx. */
html.theme-fade,
html.theme-fade *,
html.theme-fade *::before,
html.theme-fade *::after {
  transition:
    background-color 200ms ease,
    border-color 200ms ease,
    color 200ms ease,
    fill 200ms ease,
    stroke 200ms ease !important;
}
```

In `App.tsx` `useTheme().toggle`, wrap the class toggle:

```tsx
const root = document.documentElement;
root.classList.add("theme-fade");
root.classList.toggle("dark", next);
window.setTimeout(() => root.classList.remove("theme-fade"), 260);
```
(replace the existing `document.documentElement.classList.toggle("dark", next);`; keep the comment about the Sankey reading CSS during render.)

- [ ] **Step 2: Tab content cross-fade**

The tab bodies already use `anim-fade-up`. Add `key={tab}` to the wrapper so it replays on tab change: in `App.tsx` change `<div className="flex-1 overflow-y-auto px-4 py-5 md:px-6">` to include `key={tab}`. Verify the Analytics tab (which renders `AnalyticsTab` without its own wrapper) also fades: wrap it as `{tab === "analytics" && <div className="anim-fade-up"><AnalyticsTab … /></div>}`.

- [ ] **Step 3: Review the interaction list against the spec**

Check each in the browser; fix any that is missing:
- sidebar pill slides; hover fades (Task 2)
- buttons press (Task 2)
- theme icons rotate and colours cross-fade (Tasks 2, 5)
- KPI numbers count up on first load and when filters change (existing `useCountUp`)
- table row chevron (Task 4)
- tab content fades (this task)
- sheets and popovers ease (Tasks 1, 4)
- Insights skeleton shimmers; refresh spins (Task 2)
- with the OS "reduce motion" setting on, nothing animates (the global rule in `index.css`)

- [ ] **Step 4: Full verification**

```bash
cd web && npm run build
cd .. && uv run pytest -q
```
Expected: build succeeds; 236 passed.
Visual pass on the sample data: every tab, light and dark, desktop and 390 px width. Contrast spot check: muted text on `--bg` and `--surface` in both themes meets 4.5:1 for body-size text (muted `#6B6B76` on `#FFFFFF` ≈ 5.0:1; `#8B8B94` on `#101013` ≈ 5.7:1). Tab through the page: every control shows the halo ring.

- [ ] **Step 5: Docs and commit**

In `docs/PRD.md`, if a section describes the look (grep for "dark mode" / "theme"), add one line: the interface uses Geist, lucide icons and a graphite and indigo palette in light and dark. Otherwise skip.

```bash
git add -A web/src docs
git commit -m "feat(ui): theme cross-fade, tab transitions and final polish"
```
