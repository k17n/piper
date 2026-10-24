import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Application, type Source, type Stage } from "../lib/api";
import { SOURCES, STAGES, stageLabel } from "../lib/stages";
import { Button } from "./ui";

export const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs font-medium text-ink-2">{label}</span>
      {children}
    </label>
  );
}

/** For applications that never produced an email: company sites without confirmations, referrals, chats. */
export function AddApplication({ onClose, onAdded }: { onClose: () => void; onAdded: (a: Application) => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    company: "",
    role: "",
    source: "other" as Source,
    stage: "applied" as Stage,
    applied_on: today(),
    notes: "",
    job_url: "",
  });
  const [error, setError] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: () => api.createApplication({ ...form, role: form.role.trim() || undefined }),
    onSuccess: (a) => {
      qc.invalidateQueries();
      onAdded(a);
    },
    onError: (e: Error) => setError(e.message),
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });
  const [found, setFound] = useState<string | null>(null);
  const fill = useMutation({
    mutationFn: () => api.previewJobLink(form.job_url),
    onSuccess: (d) => {
      // only fill what's still empty, so nothing you typed is overwritten
      setForm((f) => ({
        ...f,
        job_url: d.url,
        company: f.company.trim() ? f.company : d.company,
        role: f.role.trim() ? f.role : d.role,
        source: f.source === "other" ? d.source : f.source,
        notes: f.notes.trim() || !d.location ? f.notes : `Location: ${d.location}`,
      }));
      setFound([d.role, d.company, d.location].filter(Boolean).join(" · ") || "Nothing new found");
      setError(null);
    },
    onError: (e: Error) => {
      setFound(null);
      setError(e.message);
    },
  });

  return (
    <div className="fixed inset-0 z-[60] flex justify-end bg-black/30" onClick={onClose}>
      <aside
        onClick={(e) => e.stopPropagation()}
        className="anim-slide-in flex h-full w-full max-w-md flex-col border-l border-line bg-surface shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <div className="text-lg font-semibold text-ink">Add an application</div>
            <div className="text-sm text-ink-2">For ones with no email: company sites, referrals, chats.</div>
          </div>
          <Button onClick={onClose} title="Close">
            ✕
          </Button>
        </header>
        <form
          className="flex flex-1 flex-col gap-4 overflow-y-auto px-5 py-5"
          onSubmit={(e) => {
            e.preventDefault();
            add.mutate();
          }}
        >
          <Field label="Company">
            <input required autoFocus value={form.company} onChange={(e) => set({ company: e.target.value })} className="h-9 px-3" />
          </Field>
          <Field label="Role">
            <input value={form.role} onChange={(e) => set({ role: e.target.value })} placeholder="e.g. Senior Product Designer" className="h-9 px-3" />
          </Field>
          <Field label="Job posting URL (optional)">
            <input
              type="text"
              inputMode="url"
              value={form.job_url}
              onChange={(e) => set({ job_url: e.target.value })}
              onBlur={(e) => {
                const v = e.target.value.trim();
                if (v && !v.includes("://")) set({ job_url: `https://${v}` });
              }}
              placeholder="https://careers.example.com/jobs/123"
              className="h-9 px-3"
            />
            <div className="mt-1 flex items-center gap-2">
              <Button
                variant="outline"
                className="h-7 px-2 text-xs"
                disabled={!form.job_url.trim() || fill.isPending}
                onClick={() => fill.mutate()}
              >
                {fill.isPending ? "Reading the posting…" : "Fill from link"}
              </Button>
              {found && <span className="min-w-0 truncate text-xs text-ink-2" title={found}>Found: {found}</span>}
            </div>
            <span className="text-[11px] text-muted">Opens the posting once to read its details. Nothing else is sent.</span>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="How you applied">
              <select value={form.source} onChange={(e) => set({ source: e.target.value as Source })} className="h-9 px-2">
                {SOURCES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Date applied">
              <input type="date" required max={today()} value={form.applied_on} onChange={(e) => set({ applied_on: e.target.value })} className="h-9 px-2" />
            </Field>
          </div>
          <Field label="Where it stands now">
            <select value={form.stage} onChange={(e) => set({ stage: e.target.value as Stage })} className="h-9 px-2">
              {STAGES.filter((s) => s !== "ghosted").map((s) => (
                <option key={s} value={s}>
                  {stageLabel(s)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Notes">
            <textarea value={form.notes} onChange={(e) => set({ notes: e.target.value })} rows={3} placeholder="Who referred you, link to the posting…" className="px-3 py-2" />
          </Field>
          {error && <div className="text-sm text-[#d03b3b]">{error}</div>}
          <div className="mt-auto flex justify-end gap-2 border-t border-line pt-4">
            <Button onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={add.isPending || !form.company.trim()}>
              Add application
            </Button>
          </div>
        </form>
      </aside>
    </div>
  );
}
