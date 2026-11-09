import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, ChevronUp, ExternalLink, Pencil, SearchX } from "lucide-react";
import { api, type Application, type Category, type Stage } from "../lib/api";
import { CATEGORIES, STAGES, sourceLabel, stageColor, stageLabel } from "../lib/stages";
import { Empty, fmtDate } from "./ui";

type SortKey = "company" | "role" | "category" | "source" | "stage" | "first_seen" | "last_event_at";

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "company", label: "Company" },
  { key: "role", label: "Role" },
  { key: "category", label: "Type" },
  { key: "source", label: "Source" },
  { key: "stage", label: "Stage" },
  { key: "first_seen", label: "Applied" },
  { key: "last_event_at", label: "Last update" },
];

function RoleCell({ app }: { app: Application }) {
  const qc = useQueryClient();
  const [value, setValue] = useState(app.role);
  const save = useMutation({
    mutationFn: (role: string) => api.patchApplication(app.id, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });
  return (
    <input
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => value.trim() !== app.role && save.mutate(value.trim())}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      placeholder="Role not stated — add it"
      title={value}
      className="h-7 w-full min-w-40 truncate border-transparent bg-transparent px-2 text-sm text-ink-2 hover:border-line focus:bg-surface-2"
    />
  );
}

function NotesCell({ app }: { app: Application }) {
  const qc = useQueryClient();
  const [value, setValue] = useState(app.notes);
  const save = useMutation({
    mutationFn: (notes: string) => api.patchApplication(app.id, { notes }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });
  return (
    <input
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => value !== app.notes && save.mutate(value)}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      placeholder="Add a note"
      className="h-7 w-full border-transparent bg-transparent px-2 text-sm hover:border-line focus:bg-surface-2"
    />
  );
}

export function ApplicationsTable({ apps, onOpen }: { apps: Application[]; onOpen: (a: Application) => void }) {
  const qc = useQueryClient();
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "last_event_at", dir: -1 });

  const patch = useMutation({
    mutationFn: ({ id, ...body }: { id: number; stage?: Stage; manual_override?: boolean; category?: Category; category_auto?: boolean }) =>
      api.patchApplication(id, body),
    onSuccess: () => qc.invalidateQueries(),
  });

  const sorted = useMemo(() => {
    const rank = (a: Application) => (sort.key === "stage" ? STAGES.indexOf(a.stage) : 0);
    return [...apps].sort((a, b) => {
      const av = sort.key === "stage" ? rank(a) : a[sort.key];
      const bv = sort.key === "stage" ? rank(b) : b[sort.key];
      return (av < bv ? -1 : av > bv ? 1 : 0) * sort.dir;
    });
  }, [apps, sort]);

  if (apps.length === 0) {
    return <Empty icon={<SearchX size={18} />} title="No applications match these filters">Try a wider date range or clear the stage and source filters.</Empty>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            {COLUMNS.map((c) => (
              <th key={c.key} className="px-3 py-2.5 font-medium">
                <button
                  className="inline-flex items-center gap-1 hover:text-ink"
                  onClick={() => setSort((s) => ({ key: c.key, dir: s.key === c.key ? ((-s.dir) as 1 | -1) : 1 }))}
                >
                  {c.label}
                  {sort.key === c.key ? sort.dir === 1 ? <ChevronUp size={12} /> : <ChevronDown size={12} /> : <span className="size-3" />}
                </button>
              </th>
            ))}
            <th className="w-[28%] px-3 py-2.5 font-medium">Notes</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((a) => (
            <tr key={a.id} className="group border-b border-line/60 transition-colors hover:bg-surface-2/60">
              <td className="px-3 py-2">
                <button onClick={() => onOpen(a)} className="text-left font-medium text-ink hover:text-accent hover:underline">
                  {a.company}
                </button>
                {a.job_url && (
                  <a
                    href={a.job_url}
                    target="_blank"
                    rel="noreferrer"
                    title={`Job posting: ${a.job_url}`}
                    aria-label="Open job posting"
                    className="ml-1.5 text-xs text-muted hover:text-accent"
                  >
                    <ExternalLink size={12} className="inline" />
                  </a>
                )}
                <ChevronRight size={14} className="ml-1 inline -translate-x-1 text-muted opacity-0 transition-all duration-150 group-hover:translate-x-0 group-hover:opacity-100" />
              </td>
              <td className="max-w-64 px-1 py-1">
                <RoleCell key={`${a.id}-${a.role}`} app={a} />
              </td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-1">
                  <select
                    value={a.category}
                    onChange={(e) => patch.mutate({ id: a.id, category: e.target.value as Category })}
                    className="h-7 border-transparent bg-transparent pr-1 text-sm text-ink-2 hover:border-line"
                    title={a.category_manual ? "Set by you" : "Detected from the role and emails. Change it to set it by hand."}
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                  {a.category_manual && (
                    <button
                      onClick={() => patch.mutate({ id: a.id, category_auto: true })}
                      className="rounded-md px-1 text-xs text-muted hover:bg-surface-2 hover:text-ink"
                      title="Set by you. Click to detect it automatically again."
                      aria-label="Detect the role type automatically again"
                    >
                      <Pencil size={12} />
                    </button>
                  )}
                </div>
              </td>
              <td className="px-3 py-2 text-ink-2">{sourceLabel(a.source)}</td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: stageColor(a.stage) }} />
                  <select
                    value={a.stage}
                    onChange={(e) => patch.mutate({ id: a.id, stage: e.target.value as Stage })}
                    className="h-7 border-transparent bg-transparent pr-1 text-sm hover:border-line"
                    title="Changing the stage sets a manual override"
                  >
                    {STAGES.map((s) => (
                      <option key={s} value={s}>
                        {stageLabel(s)}
                      </option>
                    ))}
                  </select>
                  {a.manual_override && (
                    <button
                      onClick={() => patch.mutate({ id: a.id, manual_override: false })}
                      className="whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs text-muted hover:bg-surface-2 hover:text-ink"
                      title="Set manually. Click to go back to the stage from emails."
                    >
                      <Pencil size={11} className="mr-1 inline" />clear
                    </button>
                  )}
                </div>
              </td>
              <td className="tabular whitespace-nowrap px-3 py-2 text-ink-2">{fmtDate(a.first_seen)}</td>
              <td className="tabular whitespace-nowrap px-3 py-2 text-ink-2">{fmtDate(a.last_event_at)}</td>
              <td className="px-1 py-1">
                <NotesCell app={a} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
