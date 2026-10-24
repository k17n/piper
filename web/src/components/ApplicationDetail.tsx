import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Application } from "../lib/api";
import { sourceLabel, stageColor, stageLabel } from "../lib/stages";
import { Button, EmailText, StageBadge, cx, fmtDate } from "./ui";

function senderName(from: string) {
  return from.replace(/<.*>/, "").replace(/"/g, "").trim() || from;
}

function fmtDateTime(iso: string) {
  return new Date(`${iso}Z`).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

const ORDER_KEY = "jt-thread-order";
type Order = "newest" | "oldest";

function useThreadOrder(): [Order, (o: Order) => void] {
  const [order, setOrder] = useState<Order>(() => {
    try {
      return localStorage.getItem(ORDER_KEY) === "oldest" ? "oldest" : "newest";
    } catch {
      return "newest";
    }
  });
  const update = (o: Order) => {
    setOrder(o);
    try {
      localStorage.setItem(ORDER_KEY, o);
    } catch {
      /* storage unavailable: the choice lasts for this session */
    }
  };
  return [order, update];
}

function Thread({ emailId, order, setOrder }: { emailId: string; order: Order; setOrder: (o: Order) => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["thread", emailId],
    queryFn: () => api.thread(emailId),
    staleTime: 5 * 60_000,
  });
  if (isLoading) return <div className="px-1 py-4 text-sm text-ink-2">Loading the conversation from Gmail…</div>;
  if (error) return <div className="px-1 py-4 text-sm text-[#d03b3b]">{(error as Error).message}</div>;
  if (!data) return null;
  const messages = order === "newest" ? [...data.messages].reverse() : data.messages;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3 px-1">
        <div className="line-clamp-2 min-w-0 text-sm font-medium text-ink [overflow-wrap:anywhere]">
          {data.subject || "(no subject)"}
        </div>
        <a href={data.gmail_url} target="_blank" rel="noreferrer" className="shrink-0 text-xs font-medium text-accent hover:underline">
          Open in Gmail ↗
        </a>
      </div>
      <div className="flex items-center justify-between gap-2 px-1">
        <span className="text-xs text-muted">
          {data.messages.length} message{data.messages.length === 1 ? "" : "s"}
        </span>
        <div className="flex h-7 items-center rounded-lg border border-line p-0.5 text-xs" role="group" aria-label="Message order">
          {(["newest", "oldest"] as const).map((o) => (
            <button
              key={o}
              onClick={() => setOrder(o)}
              aria-pressed={order === o}
              className={cx(
                "h-full rounded-md px-2.5 transition-colors",
                order === o ? "bg-accent text-accent-ink" : "text-ink-2 hover:text-ink",
              )}
            >
              {o === "newest" ? "Newest first" : "Oldest first"}
            </button>
          ))}
        </div>
      </div>
      {messages.map((m) => (
        <div
          key={m.id}
          className={cx(
            "min-w-0 rounded-xl border px-3 py-2.5",
            m.outgoing ? "ml-8 border-line bg-surface-2/60" : "mr-8 border-line bg-surface",
            m.highlight && "ring-1 ring-accent",
          )}
        >
          <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
            <span className="truncate font-medium text-ink">{m.outgoing ? "You" : senderName(m.from)}</span>
            <span className="tabular shrink-0 text-muted">{fmtDateTime(m.date)}</span>
          </div>
          <EmailText text={m.body.trim() || "(no text)"} />
        </div>
      ))}
    </div>
  );
}

export function ApplicationDetail({ app, onClose }: { app: Application; onClose: () => void }) {
  const withEmail = app.events.filter((e) => e.email_id);
  const [order, setOrder] = useThreadOrder();
  const events = order === "newest" ? [...app.events].reverse() : app.events;
  const [emailId, setEmailId] = useState<string | null>(withEmail.at(-1)?.email_id ?? null);

  return (
    <div className="fixed inset-0 z-[60] flex justify-end bg-black/30" onClick={onClose}>
      <aside
        onClick={(e) => e.stopPropagation()}
        className="anim-slide-in flex h-full w-full max-w-xl flex-col border-l border-line bg-surface shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <div className="truncate text-lg font-semibold text-ink">{app.company}</div>
            <div className="truncate text-sm text-ink-2">
              {app.role || "Role not stated"} · {sourceLabel(app.source)}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <StageBadge stage={app.stage} override={app.manual_override} />
            <Button onClick={onClose} title="Close">
              ✕
            </Button>
          </div>
        </header>

        <div className="min-w-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-4">
          <h3 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted">Timeline</h3>
          <ol className="mb-5 flex flex-col">
            {events.map((e, i) => (
              <li key={i}>
                <button
                  disabled={!e.email_id}
                  onClick={() => setEmailId(e.email_id)}
                  className={cx(
                    "flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left text-sm",
                    e.email_id ? "hover:bg-surface-2" : "cursor-default",
                    e.email_id && e.email_id === emailId && "bg-surface-2",
                  )}
                >
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: stageColor(e.stage) }} />
                  <span className="w-24 shrink-0 font-medium text-ink">{stageLabel(e.stage)}</span>
                  <span className="tabular w-28 shrink-0 whitespace-nowrap text-ink-2">{fmtDate(e.occurred_at)}</span>
                  <span className="min-w-0 flex-1 truncate text-muted" title={e.subject ?? undefined}>
                    {e.subject ?? "Added by hand"}
                  </span>
                </button>
              </li>
            ))}
          </ol>
          {app.notes && <p className="mb-5 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">{app.notes}</p>}

          <h3 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted">Conversation</h3>
          {emailId ? (
            <Thread emailId={emailId} order={order} setOrder={setOrder} />
          ) : (
            <div className="px-1 text-sm text-ink-2">No email linked to this application.</div>
          )}
        </div>
      </aside>
    </div>
  );
}
