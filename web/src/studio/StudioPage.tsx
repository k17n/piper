import { useEffect, useState } from "react";
import { Button, Empty, Popover, StageBadge, cx } from "../components/ui";
import { Conversation } from "./Conversation";
import { DraftPanel } from "./DraftPanel";
import { EmptyKnowledge } from "./EmptyKnowledge";
import { NewThreadDialog } from "./NewThreadDialog";
import { latestDraft, useStudio } from "./store";
import { FORMATS } from "./types";
import type { Thread } from "./types";
import { ago } from "./util";

function ThreadList({ threads, activeId, onPick }: { threads: Thread[]; activeId: string | null; onPick: (id: string) => void }) {
  const sorted = [...threads].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  return (
    <ul className="flex flex-col gap-1" aria-label="Writing threads">
      {sorted.map((t) => {
        const last = latestDraft(t);
        return (
          <li key={t.id}>
            <button
              onClick={() => onPick(t.id)}
              aria-current={t.id === activeId ? "true" : undefined}
              className={cx(
                "flex w-full flex-col gap-0.5 rounded-xl px-3 py-2 text-left transition-colors",
                t.id === activeId ? "bg-surface-2" : "hover:bg-surface-2/60",
              )}
            >
              <span className="flex items-baseline justify-between gap-2">
                <span className="truncate text-sm font-medium text-ink">{t.company}</span>
                <span className="shrink-0 text-xs text-ink-2">{ago(t.updatedAt)}</span>
              </span>
              <span className="truncate text-xs text-ink-2">{t.role ?? "No role set"}</span>
              <span className="mt-0.5 flex items-center gap-2 text-xs text-ink-2">
                {t.stage && <StageBadge stage={t.stage} />}
                {last ? `${t.pieces.length} piece${t.pieces.length === 1 ? "" : "s"} · ${FORMATS[last.format].label}` : "Nothing written yet"}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function PrototypeMenu() {
  const { state, setAnimate, setKnowledgeReady, reset } = useStudio();
  return (
    <Popover
      align="right"
      width={280}
      trigger={(open, toggle) => (
        <Button variant="outline" onClick={toggle}>
          Prototype <span aria-hidden>{open ? "▴" : "▾"}</span>
        </Button>
      )}
    >
      {(close) => (
        <div className="flex flex-col gap-1 text-sm text-ink">
          <label className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-surface-2">
            <input type="checkbox" checked={state.animate} onChange={(e) => setAnimate(e.target.checked)} />
            Type drafts out gradually
          </label>
          <label className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-surface-2">
            <input type="checkbox" checked={!state.knowledgeReady} onChange={(e) => setKnowledgeReady(!e.target.checked)} />
            Show first-run (no notes yet)
          </label>
          <button
            onClick={() => {
              reset();
              close();
            }}
            className="rounded-lg px-2.5 py-1.5 text-left hover:bg-surface-2"
          >
            Reset sample data
          </button>
        </div>
      )}
    </Popover>
  );
}

export function StudioPage({ threadId, setThreadId }: { threadId: string | null; setThreadId: (id: string | null) => void }) {
  const { state } = useStudio();
  const [creating, setCreating] = useState(false);
  const [pane, setPane] = useState<"chat" | "draft">("chat");
  const [picked, setPicked] = useState<{ threadId: string; draftId: string } | null>(null);

  const thread = state.threads.find((t) => t.id === threadId) ?? null;
  const latest = thread ? latestDraft(thread) : null;

  // On wide screens open the most recent thread instead of an empty pane.
  useEffect(() => {
    if (threadId && thread) return;
    if (state.knowledgeReady && state.threads.length && window.matchMedia("(min-width: 768px)").matches) {
      setThreadId([...state.threads].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0].id);
    }
  }, [threadId, thread, state.threads, state.knowledgeReady, setThreadId]);

  // A new draft always takes over the right-hand side.
  useEffect(() => {
    setPicked(null);
  }, [latest?.id]);

  const chosen = thread && picked?.threadId === thread.id ? thread.pieces.flatMap((p) => p.drafts).find((d) => d.id === picked.draftId) : undefined;
  const draft = chosen ?? latest;
  const piece = thread && draft ? thread.pieces.find((p) => p.id === draft.pieceId) : undefined;
  const streaming = thread && state.generating?.threadId === thread.id ? state.generating : null;

  // Show the draft pane as soon as something is being written.
  useEffect(() => {
    if (streaming) setPane("draft");
  }, [streaming?.pieceId]); // eslint-disable-line react-hooks/exhaustive-deps

  const header = (
    <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
      <h2 className="text-sm font-semibold text-ink">Writing studio</h2>
      <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-ink-2">Sample data · nothing is saved or sent</span>
      <span className="ml-auto flex items-center gap-2">
        <PrototypeMenu />
        <Button variant="primary" onClick={() => setCreating(true)}>
          + New thread
        </Button>
      </span>
    </div>
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      {header}
      {!state.knowledgeReady ? (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <EmptyKnowledge />
        </div>
      ) : state.threads.length === 0 ? (
        <Empty title="No writing threads yet">
          A thread holds everything you write to one company: drafts, versions, and what you sent.
          <div className="mt-3">
            <Button variant="primary" onClick={() => setCreating(true)}>
              + Start a thread
            </Button>
          </div>
        </Empty>
      ) : (
        <div className="flex min-h-0 flex-1">
          <nav
            aria-label="Threads"
            className={cx("w-full shrink-0 overflow-y-auto border-r border-line p-2 md:w-64", thread ? "hidden md:block" : "block")}
          >
            <ThreadList threads={state.threads} activeId={thread?.id ?? null} onPick={(id) => { setThreadId(id); setPane("chat"); }} />
          </nav>

          {thread ? (
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-4 py-2.5">
                <Button className="md:hidden" onClick={() => setThreadId(null)} title="Back to all threads">
                  ← Threads
                </Button>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-ink">{thread.company}</div>
                  <div className="truncate text-xs text-ink-2">
                    {[thread.role, thread.recipient && `to ${thread.recipient}`].filter(Boolean).join(" · ") || "No role or recipient set"}
                  </div>
                </div>
                {thread.stage && <StageBadge stage={thread.stage} />}
                <div className="ml-auto flex rounded-lg border border-line p-0.5 text-xs lg:hidden" role="group" aria-label="Show">
                  {(["chat", "draft"] as const).map((p) => (
                    <button
                      key={p}
                      onClick={() => setPane(p)}
                      aria-pressed={pane === p}
                      className={cx("rounded-md px-2.5 py-1", pane === p ? "bg-accent text-accent-ink" : "text-ink-2")}
                    >
                      {p === "chat" ? "Conversation" : "Draft"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex min-h-0 flex-1">
                <div className={cx("min-w-0 flex-1 lg:flex lg:border-r lg:border-line", pane === "chat" ? "flex" : "hidden")}>
                  <Conversation thread={thread} selectedDraftId={draft?.id ?? null} onSelectDraft={(_, id) => { setPicked({ threadId: thread.id, draftId: id }); setPane("draft"); }} />
                </div>
                <div className={cx("min-w-0 flex-1 lg:flex", pane === "draft" ? "flex" : "hidden")}>
                  {streaming && !thread.pieces.some((p) => p.id === streaming.pieceId) ? (
                    <aside aria-label="Draft" className="flex-1 px-4 py-4" role="status">
                      <p className={cx("text-sm", streaming.phase === "reading" ? "text-ink-2" : "whitespace-pre-line text-ink")}>
                        {streaming.phase === "reading" ? "Reading your notes and this thread…" : streaming.text}
                      </p>
                    </aside>
                  ) : draft && piece ? (
                    <DraftPanel
                      key={draft.pieceId}
                      thread={thread}
                      piece={piece}
                      draft={draft}
                      onSelectDraft={(id) => setPicked({ threadId: thread.id, draftId: id })}
                    />
                  ) : (
                    <Empty title="No draft yet">Ask for something on the left. The draft appears here, with the notes it came from.</Empty>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="hidden min-w-0 flex-1 md:block">
              <Empty title="Pick a thread">Or start a new one for a company you're writing to.</Empty>
            </div>
          )}
        </div>
      )}
      {creating && (
        <NewThreadDialog
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            setCreating(false);
            setThreadId(id);
            setPane("chat");
          }}
        />
      )}
      <Toast />
    </div>
  );
}

function Toast() {
  const { state } = useStudio();
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed left-1/2 top-4 z-[80] -translate-x-1/2">
      {state.toast && (
        <div key={state.toast.id} className="anim-fade-up rounded-xl border border-line bg-surface px-4 py-2 text-sm text-ink shadow-2xl">
          {state.toast.text}
        </div>
      )}
    </div>
  );
}
