import { useEffect, useRef, useState } from "react";
import { Button, cx } from "../components/ui";
import { countsOf } from "./engine";
import { latestDraft, useStudio } from "./store";
import { FORMATS, FORMAT_ORDER } from "./types";
import type { Draft, Message, Thread } from "./types";
import { ago, firstName, inline, shortDate } from "./util";

function suggestionsFor(thread: Thread): string[] {
  const who = firstName(thread.recipient);
  if (thread.pieces.length === 0) {
    return [
      "Write a cover letter",
      who ? `Email ${who} to ask for a 20-minute chat` : "Email asking for a 20-minute chat",
      "Send a LinkedIn note to connect",
    ];
  }
  return ["Follow up by email after a week", "Turn this into a LinkedIn note", "Make it warmer"];
}

function Avatar() {
  return (
    <span aria-hidden className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent text-[11px] font-bold text-accent-ink">
      P
    </span>
  );
}

function DraftCard({ draft, selected, onSelect }: { draft: Draft; selected: boolean; onSelect: () => void }) {
  const c = countsOf(draft);
  const spec = FORMATS[draft.format];
  const size = spec.unit === "chars" ? `${c.chars} characters` : spec.unit === "lines" ? `${c.lines} lines` : `${c.words} words`;
  return (
    <button
      onClick={onSelect}
      aria-pressed={selected}
      className={cx(
        "mt-2 flex w-full items-center gap-2 rounded-xl border bg-surface px-3 py-2 text-left text-sm transition-colors hover:bg-surface-2",
        selected ? "border-accent" : "border-line",
      )}
    >
      <span className="font-medium text-ink">{spec.label}</span>
      <span className="rounded bg-surface-2 px-1.5 text-xs font-medium text-ink-2">v{draft.version}</span>
      <span className="text-xs text-ink-2">{size}</span>
      {draft.usedAt && <span className="text-xs text-ink-2">· used {shortDate(draft.usedAt)}</span>}
      <span className="ml-auto text-xs font-medium text-ink-2">{selected ? "Showing" : "Show"}</span>
    </button>
  );
}

function MessageView({
  m,
  thread,
  selectedDraftId,
  onSelectDraft,
}: {
  m: Message;
  thread: Thread;
  selectedDraftId: string | null;
  onSelectDraft: (pieceId: string, draftId: string) => void;
}) {
  const { chooseFormat, state } = useStudio();
  if (m.role === "user") {
    return (
      <div className="ml-auto max-w-[88%] rounded-2xl rounded-tr-sm border border-accent/30 bg-accent/15 px-3 py-2 text-sm text-ink">
        {m.text}
      </div>
    );
  }
  const draft = m.draft ? thread.pieces.find((p) => p.id === m.draft!.pieceId)?.drafts.find((d) => d.id === m.draft!.draftId) : undefined;
  return (
    <div className="flex max-w-[94%] gap-2">
      <Avatar />
      <div className="min-w-0 flex-1">
        <div className="rounded-2xl rounded-tl-sm bg-surface-2 px-3 py-2 text-sm leading-relaxed text-ink">{m.text}</div>
        {m.ask && (
          <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label="Choose a kind of message">
            {FORMAT_ORDER.map((f) => (
              <button
                key={f}
                disabled={!!m.ask?.answered || !!state.generating}
                onClick={() => chooseFormat(thread.id, m.id, f)}
                aria-pressed={m.ask?.answered === f}
                className={cx(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors disabled:cursor-default",
                  m.ask?.answered === f ? "border-accent bg-accent/15 text-ink" : "border-line text-ink-2 hover:bg-surface-2 hover:text-ink disabled:opacity-50 disabled:hover:bg-transparent",
                )}
              >
                {FORMATS[f].label}
              </button>
            ))}
          </div>
        )}
        {draft && <DraftCard draft={draft} selected={draft.id === selectedDraftId} onSelect={() => onSelectDraft(draft.pieceId, draft.id)} />}
      </div>
    </div>
  );
}

export function Conversation({
  thread,
  selectedDraftId,
  onSelectDraft,
}: {
  thread: Thread;
  selectedDraftId: string | null;
  onSelectDraft: (pieceId: string, draftId: string) => void;
}) {
  const { state, send, stop } = useStudio();
  const [text, setText] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const gen = state.generating?.threadId === thread.id ? state.generating : null;
  const busy = !!state.generating;

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [thread.messages.length, gen?.phase, thread.id]);

  const submit = (value = text) => {
    if (!value.trim() || busy) return;
    send(thread.id, value);
    setText("");
  };
  const last = latestDraft(thread);

  return (
    <section aria-label="Conversation" className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div ref={listRef} role="log" aria-live="polite" aria-label="Messages" className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
        {thread.messages.length === 0 && !gen && (
          <div className="flex gap-2">
            <Avatar />
            <div className="rounded-2xl rounded-tl-sm bg-surface-2 px-3 py-2 text-sm leading-relaxed text-ink">
              What would you like to write to {thread.company}
              {thread.recipient ? `, to ${firstName(thread.recipient)}` : ""}? Tell me in your own words and I'll use your notes to draft it.
              <span className="mt-1 block text-ink-2">
                If I'm not sure which kind of message you mean, I'll ask.
              </span>
            </div>
          </div>
        )}
        {thread.messages.map((m) => (
          <MessageView key={m.id} m={m} thread={thread} selectedDraftId={selectedDraftId ?? last?.id ?? null} onSelectDraft={onSelectDraft} />
        ))}
        {gen && (
          <div className="flex gap-2" role="status">
            <Avatar />
            <div className="rounded-2xl rounded-tl-sm bg-surface-2 px-3 py-2 text-sm text-ink-2">
              {gen.phase === "reading" ? "Reading your notes and this thread…" : `Writing the ${inline(FORMATS[gen.format].label)}…`}
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-line px-4 pb-3 pt-2">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {suggestionsFor(thread).map((s) => (
            <button
              key={s}
              disabled={busy}
              onClick={() => submit(s)}
              className="rounded-full border border-line px-3 py-1 text-xs text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink disabled:opacity-40"
            >
              {s}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={2}
            aria-label="Message"
            placeholder="Ask for a cover letter, a LinkedIn note, a WhatsApp message or an email…"
            className="w-full resize-none px-3 py-2 text-sm"
          />
          <div className="mt-1.5 flex items-center justify-between gap-2">
            <span className="text-[11px] text-ink-2">Enter to send · Shift+Enter for a new line · updated {ago(thread.updatedAt)}</span>
            {gen ? (
              <Button onClick={stop} variant="outline" title="Stop writing (Esc)">
                ■ Stop
              </Button>
            ) : (
              <Button type="submit" variant="primary" disabled={!text.trim() || busy}>
                Send
              </Button>
            )}
          </div>
        </form>
      </div>
    </section>
  );
}
