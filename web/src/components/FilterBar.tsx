import { useEffect, useRef, useState } from "react";
import type { Filters, RangeKey, SavedView } from "../lib/api";
import { CATEGORIES, SOURCES, STAGES, stageColor, stageLabel } from "../lib/stages";
import { Popover, cx, fmtDate } from "./ui";
import { ViewPicker } from "./ViewPicker";

const RANGES: { value: RangeKey; label: string }[] = [
  { value: "30d", label: "30d" },
  { value: "90d", label: "90d" },
  { value: "180d", label: "6m" },
  { value: "all", label: "All" },
  { value: "custom", label: "Custom" },
];

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
  views: SavedView[];
  viewId: number | null;
  onOpenView: (v: SavedView) => void;
  onDetachView: () => void;
  onSavedView: (v: SavedView) => void;
  dataSince: string | null;
}

function MultiSelect({
  label,
  options,
  selected,
  onChange,
  dot,
}: {
  label: string;
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (v: string[]) => void;
  dot?: (v: string) => string;
}) {
  const summary =
    selected.length === 0 ? "All" : selected.length === 1 ? options.find((o) => o.value === selected[0])?.label : `${selected.length} selected`;
  return (
    <Popover
      width={220}
      trigger={(open, toggle) => (
        <button
          onClick={toggle}
          className={cx(
            "flex h-8 items-center gap-1.5 rounded-lg border border-line px-3 text-sm transition-colors hover:bg-surface-2",
            (open || selected.length > 0) && "bg-surface-2",
          )}
        >
          <span className="text-muted">{label}</span>
          <span className="text-ink">{summary}</span>
          <span className="text-muted">▾</span>
        </button>
      )}
    >
      {() => (
        <div className="flex flex-col text-sm">
          {options.map((o) => {
            const on = selected.includes(o.value);
            return (
              <label key={o.value} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-2">
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() => onChange(on ? selected.filter((s) => s !== o.value) : [...selected, o.value])}
                  className="accent-[var(--accent)]"
                />
                {dot && <span className="h-2 w-2 rounded-full" style={{ background: dot(o.value) }} />}
                <span className="text-ink">{o.label}</span>
              </label>
            );
          })}
          {selected.length > 0 && (
            <button onClick={() => onChange([])} className="mt-1 rounded-lg px-2 py-1.5 text-left text-ink-2 hover:bg-surface-2">
              Clear
            </button>
          )}
        </div>
      )}
    </Popover>
  );
}

export function FilterBar({ filters, onChange, views, viewId, onOpenView, onDetachView, onSavedView, dataSince }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const [q, setQ] = useState(filters.q ?? "");

  const searchRef = useRef<HTMLInputElement>(null);
  const clearSearch = () => {
    setQ("");
    if (filters.q) set({ q: null }); // apply at once instead of waiting for the typing delay
    searchRef.current?.focus();
  };

  useEffect(() => setQ(filters.q ?? ""), [filters.q]);
  useEffect(() => {
    const t = setTimeout(() => {
      if ((q.trim() || null) !== filters.q) set({ q: q.trim() || null });
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <ViewPicker
        views={views}
        viewId={viewId}
        filters={filters}
        onOpen={onOpenView}
        onDetach={onDetachView}
        onSaved={onSavedView}
      />
      <div className="mx-1 h-5 w-px bg-line" />

      <div className="flex h-8 items-center rounded-lg border border-line p-0.5" role="group" aria-label="Date range">
        {RANGES.map((r) => (
          <button
            key={r.value}
            onClick={() => set({ range: r.value })}
            className={cx(
              "h-full rounded-md px-2.5 text-sm transition-colors",
              filters.range === r.value ? "bg-accent text-accent-ink" : "text-ink-2 hover:text-ink",
            )}
          >
            {r.label}
          </button>
        ))}
      </div>
      {filters.range === "custom" && (
        <div className="flex items-center gap-1 text-sm">
          <input type="date" value={filters.from ?? ""} onChange={(e) => set({ from: e.target.value || null })} className="h-8 px-2" />
          <span className="text-muted">–</span>
          <input type="date" value={filters.to ?? ""} onChange={(e) => set({ to: e.target.value || null })} className="h-8 px-2" />
        </div>
      )}

      <MultiSelect
        label="Role"
        options={CATEGORIES}
        selected={filters.categories}
        onChange={(categories) => set({ categories })}
      />
      <MultiSelect label="Source" options={SOURCES} selected={filters.sources} onChange={(sources) => set({ sources })} />
      <MultiSelect
        label="Stage"
        options={STAGES.map((s) => ({ value: s, label: stageLabel(s) }))}
        selected={filters.stages}
        onChange={(stages) => set({ stages })}
        dot={stageColor}
      />
      <div className="relative">
        <input
          ref={searchRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Escape" && q && clearSearch()}
          placeholder="Search company or role"
          aria-label="Search company or role"
          className="h-8 w-52 pl-3 pr-8 text-sm"
        />
        {q && (
          <button
            type="button"
            onClick={clearSearch}
            aria-label="Clear search"
            title="Clear search (Esc)"
            className="absolute right-1.5 top-1/2 grid h-5 w-5 -translate-y-1/2 place-items-center rounded-full text-muted transition-colors hover:bg-line hover:text-ink"
          >
            <svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M3 3l10 10M13 3L3 13" />
            </svg>
          </button>
        )}
      </div>
      <label className="flex h-8 cursor-pointer items-center gap-2 px-1 text-sm text-ink-2">
        <input
          type="checkbox"
          checked={filters.include_ghosted}
          onChange={(e) => set({ include_ghosted: e.target.checked })}
          className="accent-[var(--accent)]"
        />
        Include ghosted
      </label>
      {dataSince && <span className="ml-auto text-xs text-muted">Data available since {fmtDate(dataSince)}</span>}
    </div>
  );
}
