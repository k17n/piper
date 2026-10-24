import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type ReviewItem } from "../lib/api";
import { SOURCES, STAGES, stageLabel } from "../lib/stages";
import { Button, EmailText, Empty, cx, fmtDate } from "./ui";

function ReviewCard({ item }: { item: ReviewItem }) {
  const qc = useQueryClient();
  const ex = (item.extracted ?? {}) as Record<string, string | null>;
  const [form, setForm] = useState({
    company: ex.company ?? "",
    role: ex.role ?? "",
    stage: ex.stage ?? "applied",
    source: ex.source ?? "other",
  });
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const resolve = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.resolveReview(item.id, body),
    onSuccess: () => qc.invalidateQueries(),
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div className="card anim-fade-up flex min-w-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-ink" title={item.email?.subject}>
            {item.email?.subject || "(no subject)"}
          </div>
          <div className="truncate text-xs text-muted" title={item.email?.from}>
            {item.email?.from} · {item.email && fmtDate(item.email.received_at)}
          </div>
        </div>
        <span className="max-w-full truncate rounded-full bg-surface-2 px-2 py-0.5 text-xs text-ink-2" title={item.reason}>
          {item.reason}
        </span>
      </div>
      {item.email?.body && (
        <div className="min-w-0">
          <div className={cx(!expanded && "max-h-24 overflow-hidden [mask-image:linear-gradient(to_bottom,black_60%,transparent)]")}>
            <EmailText text={item.email.body} />
          </div>
          <div className="mt-1.5 flex gap-3 text-xs">
            <button onClick={() => setExpanded((e) => !e)} className="font-medium text-accent hover:underline">
              {expanded ? "Show less" : "Read email"}
            </button>
            {item.email.gmail_url && (
              <a href={item.email.gmail_url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">
                Open in Gmail ↗
              </a>
            )}
          </div>
        </div>
      )}
      <form
        className="flex flex-wrap items-center gap-2 [&>input]:min-w-36 [&>input]:flex-1 [&>select]:w-32"
        onSubmit={(e) => {
          e.preventDefault();
          resolve.mutate({ action: "apply", ...form, role: form.role || null });
        }}
      >
        <input required placeholder="Company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} className="h-8 px-2 text-sm" />
        <input placeholder="Role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="h-8 px-2 text-sm" />
        <select value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })} className="h-8 px-2 text-sm">
          {STAGES.filter((s) => s !== "ghosted").map((s) => (
            <option key={s} value={s}>
              {stageLabel(s)}
            </option>
          ))}
        </select>
        <select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} className="h-8 px-2 text-sm">
          {SOURCES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <Button type="submit" variant="primary" disabled={resolve.isPending}>
          Add
        </Button>
        <Button variant="outline" onClick={() => resolve.mutate({ action: "dismiss" })} disabled={resolve.isPending}>
          Not a job email
        </Button>
      </form>
      {error && <div className="text-xs text-[#d03b3b]">{error}</div>}
    </div>
  );
}

export function ReviewQueue({ items }: { items: ReviewItem[] }) {
  if (items.length === 0) {
    return <Empty title="Nothing to review">Emails the model wasn't sure about will show up here for a quick fix.</Empty>;
  }
  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <ReviewCard key={item.id} item={item} />
      ))}
    </div>
  );
}
