import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChartColumn, Inbox, LayoutDashboard, Moon, PenLine, Plus, Rows3, SearchX, Sun, type LucideIcon } from "lucide-react";
import { api, normalizeFilters, type Application, type SavedView } from "./lib/api";
import { useUrlState, type Tab } from "./lib/urlState";
import { FilterBar } from "./components/FilterBar";
import { KpiCards } from "./components/KpiCards";
import { SankeyChart, type Selection } from "./components/SankeyChart";
import { AppSheet } from "./components/AppSheet";
import { ApplicationDetail } from "./components/ApplicationDetail";
import { AddApplication } from "./components/AddApplication";
import { ApplicationsTable } from "./components/ApplicationsTable";
import { ReviewQueue } from "./components/ReviewQueue";
import { SyncIndicator } from "./components/SyncIndicator";
import { AnalyticsTab } from "./components/analytics/AnalyticsTab";
import { Button, Empty, cx } from "./components/ui";
import { StudioPage } from "./studio/StudioPage";
import { useStudio } from "./studio/store";

/** The brand: P.I.P.E.R. (Pipeline, Interviews, Pitches, Emails & Résumés), dots in the accent color. */
function Wordmark() {
  return (
    <div
      className="flex items-baseline text-lg font-bold tracking-[0.08em] text-ink"
      aria-label="P.I.P.E.R."
      title="Pipeline · Interviews · Pitches · Emails · Résumés"
    >
      {"PIPER".split("").map((letter, i) => (
        <span key={i} aria-hidden>
          {letter}
          <span className="text-accent">.</span>
        </span>
      ))}
    </div>
  );
}

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const toggle = () => {
    const next = !dark;
    // Switch the class before re-rendering: the Sankey reads theme colors from CSS while it renders.
    const root = document.documentElement;
    root.classList.add("theme-fade");
    root.classList.toggle("dark", next);
    window.setTimeout(() => root.classList.remove("theme-fade"), 260);
    try {
      localStorage.setItem("piper-theme", next ? "dark" : "light");
    } catch {
      /* storage unavailable */
    }
    setDark(next);
  };
  return { dark, toggle };
}

const NAV: { tab: Tab; label: string; icon: LucideIcon }[] = [
  { tab: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { tab: "applications", label: "Applications", icon: Rows3 },
  { tab: "analytics", label: "Analytics", icon: ChartColumn },
  { tab: "review", label: "Review", icon: Inbox },
  { tab: "studio", label: "Writing studio", icon: PenLine },
];
const NAV_ROW = 36; // h-9
const NAV_GAP = 2; // gap-0.5

export default function App() {
  const { tab, setTab, threadId, setThreadId, viewId, setViewId, filters, setFilters, restoredFromUrl } = useUrlState();
  const { dark, toggle } = useTheme();
  const studio = useStudio();
  const [selection, setSelection] = useState<Selection | null>(null);
  const [openApp, setOpenApp] = useState<Application | null>(null);
  const [adding, setAdding] = useState(false);

  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const views = useQuery({ queryKey: ["views"], queryFn: api.views });
  const stats = useQuery({ queryKey: ["stats", filters], queryFn: () => api.stats(filters), enabled: tab === "dashboard" });
  const sankey = useQuery({ queryKey: ["sankey", filters], queryFn: () => api.sankey(filters), enabled: tab === "dashboard" });
  const apps = useQuery({ queryKey: ["applications", filters], queryFn: () => api.applications(filters), enabled: tab === "applications" });
  const review = useQuery({ queryKey: ["review"], queryFn: api.reviewQueue });

  // On a fresh start (nothing in the URL), open the default saved view once.
  const appliedDefault = useRef(restoredFromUrl);
  useEffect(() => {
    if (appliedDefault.current || !views.data) return;
    appliedDefault.current = true;
    const def = views.data.find((v) => v.is_default);
    if (def) {
      setViewId(def.id);
      setFilters(normalizeFilters(def.filters));
    }
  }, [views.data, setViewId, setFilters]);

  const openView = (v: SavedView) => {
    setViewId(v.id);
    setFilters(normalizeFilters(v.filters));
  };
  const onSelect = useCallback((s: Selection) => setSelection(s), []);
  const reviewCount = review.data?.length ?? 0;

  /** From an application: open (or start) that company's writing thread. */
  const writeTo = (a: Application) => {
    const existing = studio.threadFor(a.company);
    setThreadId(existing ? existing.id : studio.createThread({ company: a.company, role: a.role || undefined, stage: a.stage }));
    setOpenApp(null);
    setTab("studio");
  };

  return (
    <div className="flex h-full">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-line bg-bg px-3 py-4 md:flex">
        <div className="mb-6 px-2">
          <Wordmark />
          <div className="mt-0.5 text-[11px] text-muted">Your job-search assistant</div>
        </div>
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
        <div className="mt-auto flex flex-col gap-4">
          <SyncIndicator meta={meta.data} />
          <div className="flex items-center justify-between border-t border-line pt-3 text-xs text-muted">
            <span title="Local model">{meta.data?.model ?? "…"}</span>
            <Button onClick={toggle} label={dark ? "Switch to light theme" : "Switch to dark theme"} title="Toggle theme" icon className="relative">
              <Sun size={15} className={cx("absolute transition-all duration-300", dark ? "rotate-0 opacity-100" : "rotate-90 opacity-0")} />
              <Moon size={15} className={cx("absolute transition-all duration-300", dark ? "-rotate-90 opacity-0" : "rotate-0 opacity-100")} />
            </Button>
          </div>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-30 border-b border-line bg-bg/90 px-4 py-3 backdrop-blur-sm md:px-6">
          <div className="mb-2 flex items-center gap-3 md:hidden">
            {NAV.map((n) => (
              <button key={n.tab} onClick={() => setTab(n.tab)} className={cx("text-sm", tab === n.tab ? "font-semibold text-ink" : "text-ink-2")}>
                {n.label}
              </button>
            ))}
          </div>
          {(tab === "dashboard" || tab === "applications") && (
            <FilterBar
              filters={filters}
              onChange={setFilters}
              views={views.data ?? []}
              viewId={viewId}
              onOpenView={openView}
              onDetachView={() => setViewId(null)}
              onSavedView={(v) => setViewId(v.id)}
              dataSince={meta.data?.data_since ?? null}
            />
          )}
        </div>

        {tab === "studio" && (
          <div className="min-h-0 flex-1">
            <StudioPage threadId={threadId} setThreadId={setThreadId} />
          </div>
        )}
        <div key={tab} className={cx("flex-1 overflow-y-auto px-4 py-5 md:px-6", tab === "studio" && "hidden")}>
          {tab === "dashboard" && (
            <div className="anim-fade-up flex flex-col gap-4">
              <KpiCards stats={stats.data} />
              <section className="card p-4">
                <div className="mb-1 flex items-baseline justify-between">
                  <h2 className="text-sm font-semibold text-ink">Application funnel</h2>
                  <span className="text-xs text-muted">Click a flow or stage to see its applications</span>
                </div>
                {sankey.data && sankey.data.links.length > 0 ? (
                  <SankeyChart data={sankey.data} dark={dark} onSelect={onSelect} />
                ) : sankey.isLoading ? (
                  <div className="h-96" />
                ) : (
                  <Empty title="No applications in this range" icon={<SearchX size={18} />}>
                    Widen the date range, run a sync, or try sample data with <code>piper seed</code>.
                  </Empty>
                )}
              </section>
            </div>
          )}

          {tab === "analytics" && (
            <div className="anim-fade-up">
              <AnalyticsTab filters={filters} dark={dark} onSelect={onSelect} />
            </div>
          )}

          {tab === "applications" && (
            <div className="anim-fade-up flex flex-col gap-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-ink-2">
                  {apps.data ? `${apps.data.length} application${apps.data.length === 1 ? "" : "s"}` : ""}
                </span>
                <Button variant="primary" onClick={() => setAdding(true)}>
                  <Plus size={14} /> Add application
                </Button>
              </div>
              <section className="card p-2">
                {apps.data ? <ApplicationsTable apps={apps.data} onOpen={setOpenApp} /> : <div className="h-64" />}
              </section>
            </div>
          )}

          {tab === "review" && (
            <div className="anim-fade-up mx-auto flex max-w-4xl flex-col gap-3">
              <h2 className="text-sm font-semibold text-ink">Review queue</h2>
              <ReviewQueue items={review.data ?? []} />
            </div>
          )}
        </div>
      </main>

      {selection && (
        <AppSheet selection={selection} filters={filters} onClose={() => setSelection(null)} onOpen={setOpenApp} />
      )}
      {openApp && <ApplicationDetail key={openApp.id} app={openApp} onClose={() => setOpenApp(null)} onWrite={writeTo} />}
      {adding && (
        <AddApplication
          onClose={() => setAdding(false)}
          onAdded={(a) => {
            setAdding(false);
            setOpenApp(a);
          }}
        />
      )}
    </div>
  );
}
