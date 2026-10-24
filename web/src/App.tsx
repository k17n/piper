import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { Button, Empty, cx } from "./components/ui";

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
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("piper-theme", next ? "dark" : "light");
    } catch {
      /* storage unavailable */
    }
    setDark(next);
  };
  return { dark, toggle };
}

const NAV: { tab: Tab; label: string; icon: string }[] = [
  { tab: "dashboard", label: "Dashboard", icon: "◧" },
  { tab: "applications", label: "Applications", icon: "☰" },
  { tab: "review", label: "Review", icon: "◎" },
];

export default function App() {
  const { tab, setTab, viewId, setViewId, filters, setFilters, restoredFromUrl } = useUrlState();
  const { dark, toggle } = useTheme();
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

  return (
    <div className="flex h-full">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-line bg-surface/60 px-3 py-4 md:flex">
        <div className="mb-6 px-2">
          <Wordmark />
          <div className="mt-0.5 text-[11px] text-muted">Your job-search assistant</div>
        </div>
        <nav className="flex flex-col gap-0.5">
          {NAV.map((n) => (
            <button
              key={n.tab}
              onClick={() => setTab(n.tab)}
              className={cx(
                "flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm transition-colors",
                tab === n.tab ? "bg-surface-2 font-medium text-ink" : "text-ink-2 hover:bg-surface-2/60 hover:text-ink",
              )}
            >
              <span className="w-4 text-center text-muted">{n.icon}</span>
              {n.label}
              {n.tab === "review" && reviewCount > 0 && (
                <span className="tabular ml-auto rounded-full bg-accent px-1.5 text-xs font-medium text-accent-ink">{reviewCount}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-4">
          <SyncIndicator meta={meta.data} />
          <div className="flex items-center justify-between border-t border-line pt-3 text-xs text-muted">
            <span title="Local model">{meta.data?.model ?? "…"}</span>
            <Button onClick={toggle} title="Toggle theme" className="h-7 px-2">
              {dark ? "☀" : "☾"}
            </Button>
          </div>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-30 border-b border-line bg-bg/85 px-4 py-3 backdrop-blur md:px-6">
          <div className="mb-2 flex items-center gap-3 md:hidden">
            {NAV.map((n) => (
              <button key={n.tab} onClick={() => setTab(n.tab)} className={cx("text-sm", tab === n.tab ? "font-semibold text-ink" : "text-ink-2")}>
                {n.label}
              </button>
            ))}
          </div>
          {tab !== "review" && (
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

        <div className="flex-1 overflow-y-auto px-4 py-5 md:px-6">
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
                  <Empty title="No applications in this range">
                    Widen the date range, run a sync, or try sample data with <code>piper seed</code>.
                  </Empty>
                )}
              </section>
            </div>
          )}

          {tab === "applications" && (
            <div className="anim-fade-up flex flex-col gap-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-ink-2">
                  {apps.data ? `${apps.data.length} application${apps.data.length === 1 ? "" : "s"}` : ""}
                </span>
                <Button variant="primary" onClick={() => setAdding(true)}>
                  + Add application
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
      {openApp && <ApplicationDetail key={openApp.id} app={openApp} onClose={() => setOpenApp(null)} />}
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
