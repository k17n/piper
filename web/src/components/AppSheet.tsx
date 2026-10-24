import { useQuery } from "@tanstack/react-query";
import { api, type Application, type Filters } from "../lib/api";
import { sourceLabel } from "../lib/stages";
import type { Selection } from "./SankeyChart";
import { Button, StageBadge, fmtDate } from "./ui";

export function AppSheet({
  selection,
  filters,
  onClose,
  onOpen,
}: {
  selection: Selection;
  filters: Filters;
  onClose: () => void;
  onOpen: (a: Application) => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["applications", filters, selection.ids],
    queryFn: () => api.applications(filters, selection.ids),
    enabled: selection.ids.length > 0,
  });

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        onClick={(e) => e.stopPropagation()}
        className="anim-slide-in flex h-full w-full max-w-md flex-col border-l border-line bg-surface shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <div className="text-base font-semibold text-ink">{selection.title}</div>
            <div className="text-sm text-ink-2">
              {selection.ids.length} application{selection.ids.length === 1 ? "" : "s"}
            </div>
          </div>
          <Button onClick={onClose} title="Close">
            ✕
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto px-3 py-2">
          {isLoading && <div className="p-3 text-sm text-ink-2">Loading…</div>}
          {data?.map((a) => (
            <button key={a.id} onClick={() => onOpen(a)} className="block w-full rounded-xl px-3 py-3 text-left hover:bg-surface-2">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-medium text-ink">{a.company}</div>
                  <div className="truncate text-sm text-ink-2">{a.role || "Role not stated"}</div>
                </div>
                <StageBadge stage={a.stage} override={a.manual_override} />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-1 gap-y-1 text-xs text-muted">
                <span>{sourceLabel(a.source)}</span>
                <span>·</span>
                {a.events.map((e, i) => (
                  <span key={i}>
                    {i > 0 && "→ "}
                    {e.stage} <span className="opacity-70">{fmtDate(e.occurred_at)}</span>
                  </span>
                ))}
              </div>
              {a.notes && <div className="mt-1.5 text-xs text-ink-2">{a.notes}</div>}
            </button>
          ))}
        </div>
      </aside>
    </div>
  );
}
