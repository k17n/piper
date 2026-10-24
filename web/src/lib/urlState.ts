import { useEffect, useState } from "react";
import { DEFAULT_FILTERS, filterParams, normalizeFilters, type Filters, type RangeKey } from "./api";

export type Tab = "dashboard" | "applications" | "review";
const TABS: Tab[] = ["dashboard", "applications", "review"];
const FILTER_KEYS = ["range", "from", "to", "sources", "stages", "categories", "q", "include_ghosted"];

interface UrlState {
  tab: Tab;
  viewId: number | null;
  filters: Filters;
  hasFilterParams: boolean;
}

function readUrl(): UrlState {
  const p = new URLSearchParams(window.location.search);
  const tab = TABS.includes(p.get("tab") as Tab) ? (p.get("tab") as Tab) : "dashboard";
  const viewId = p.get("view") ? Number(p.get("view")) : null;
  const hasFilterParams = FILTER_KEYS.some((k) => p.has(k));
  const range = (p.get("range") as RangeKey) || DEFAULT_FILTERS.range;
  const filters = normalizeFilters({
    range: ["30d", "90d", "180d", "all", "custom"].includes(range) ? range : "90d",
    from: p.get("from"),
    to: p.get("to"),
    sources: p.getAll("sources"),
    stages: p.getAll("stages"),
    categories: p.getAll("categories"),
    q: p.get("q"),
    include_ghosted: p.get("include_ghosted") !== "false",
  });
  return { tab, viewId: Number.isFinite(viewId) ? viewId : null, filters, hasFilterParams };
}

/** Tab, active saved view and filters, mirrored into the URL so refreshes and bookmarks keep them. */
export function useUrlState() {
  const [initial] = useState(readUrl);
  const [tab, setTab] = useState<Tab>(initial.tab);
  const [viewId, setViewId] = useState<number | null>(initial.viewId);
  const [filters, setFilters] = useState<Filters>(initial.filters);

  useEffect(() => {
    const p = filterParams(filters);
    if (tab !== "dashboard") p.set("tab", tab);
    if (viewId != null) p.set("view", String(viewId));
    window.history.replaceState(null, "", `${window.location.pathname}?${p}`);
  }, [tab, viewId, filters]);

  return {
    tab,
    setTab,
    viewId,
    setViewId,
    filters,
    setFilters: (f: Filters) => setFilters(normalizeFilters(f)),
    restoredFromUrl: initial.hasFilterParams || initial.viewId != null,
  };
}
