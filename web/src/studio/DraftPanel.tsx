import { useMemo, useState } from "react";
import { Button, Popover, cx } from "../components/ui";
import { bodyText, claimsOf, countsOf, fullText, ruleStatus, sourceOrder } from "./engine";
import type { Change } from "./engine";
import { sourcesFor } from "./knowledge";
import { useStudio } from "./store";
import { CHANNELS, FORMATS, FORMAT_ORDER } from "./types";
import type { Draft, Piece, Sentence, Thread } from "./types";
import { downloadText, shortDate } from "./util";

const gmailLink = (d: Draft) =>
  `https://mail.google.com/mail/?view=cm&fs=1&su=${encodeURIComponent(d.subject ?? "")}&body=${encodeURIComponent(bodyText(d))}`;

function Rule({ draft }: { draft: Draft }) {
  const r = ruleStatus(draft);
  return (
    <span className={cx("text-xs", r.state === "ok" ? "text-ink-2" : "font-medium text-ink")}>
      {r.state === "ok" ? "✓ " : "⚠ "}
      {r.text}
    </span>
  );
}

function SentenceView({ s, numbers, onPick }: { s: Sentence; numbers: Map<string, number>; onPick: (id: string) => void }) {
  const claim = s.kind === "fact" && s.sources.length === 0;
  return (
    <span className={cx(claim && "rounded bg-[#e0a526]/20 px-0.5 underline decoration-[#e0a526] decoration-dotted underline-offset-4")}>
      {s.text}
      {claim && (
        <span className="ml-0.5 text-xs font-semibold" title="Not in your notes. Check it">
          <span aria-hidden>?</span>
          <span className="sr-only">(claim to check)</span>
        </span>
      )}
      {s.sources.map((id) => (
        <sup key={id}>
          <button onClick={() => onPick(id)} aria-label={`Source ${numbers.get(id)}`} className="px-0.5 text-[10px] font-semibold text-accent hover:underline">
            {numbers.get(id)}
          </button>
        </sup>
      ))}{" "}
    </span>
  );
}

export function DraftPanel({
  thread,
  piece,
  draft,
  onSelectDraft,
}: {
  thread: Thread;
  piece: Piece;
  draft: Draft;
  onSelectDraft: (draftId: string) => void;
}) {
  const { state, act, saveEdit, markUsed, resolveClaim, toast } = useStudio();
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [timeline, setTimeline] = useState(true);

  const busy = !!state.generating;
  const gen = state.generating?.threadId === thread.id && state.generating.pieceId === piece.id ? state.generating : null;
  const sources = useMemo(() => sourcesFor(thread), [thread]);
  const order = sourceOrder(draft);
  const numbers = useMemo(() => new Map(order.map((id, i) => [id, i + 1])), [order]);
  const claims = claimsOf(draft);
  const spec = FORMATS[draft.format];
  const isLatest = piece.drafts.at(-1)?.id === draft.id;
  const c = countsOf(draft);

  const startEdit = () => {
    setSubject(draft.subject ?? "");
    setBody(bodyText(draft));
    setEditing(true);
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(fullText(draft));
      toast("Copied to the clipboard.");
    } catch {
      toast("Couldn't copy here. Select the text and copy it.");
    }
  };
  const quick = (label: string, request: string, change: Change, done: string) => (
    <Button key={label} variant="outline" disabled={busy || editing} onClick={() => act(thread.id, draft.id, { kind: "revise", change, request, label: done })}>
      {label}
    </Button>
  );

  return (
    <aside aria-label="Draft" className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold text-ink">{spec.label}</h3>
        {piece.drafts.length > 1 && (
          <div className="flex gap-1" role="group" aria-label="Versions">
            {piece.drafts.map((d) => (
              <button
                key={d.id}
                onClick={() => onSelectDraft(d.id)}
                aria-pressed={d.id === draft.id}
                title={d.note ?? "First draft"}
                className={cx("rounded px-1.5 py-0.5 text-xs font-medium", d.id === draft.id ? "bg-accent text-accent-ink" : "bg-surface-2 text-ink-2 hover:text-ink")}
              >
                v{d.version}
              </button>
            ))}
          </div>
        )}
        {draft.usedAt && (
          <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-ink-2">
            Used on {draft.usedOn} · {shortDate(draft.usedAt)}
          </span>
        )}
        <span className="ml-auto">
          <Rule draft={draft} />
        </span>
        {draft.note && <p className="w-full text-xs text-ink-2">{draft.note}{!isLatest && " (an earlier version)"}</p>}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {gen ? (
          <div role="status" aria-label="Writing">
            {gen.phase === "reading" ? (
              <p className="text-sm text-ink-2">Reading your notes and this thread…</p>
            ) : (
              <p className="whitespace-pre-line text-sm leading-relaxed text-ink">
                {gen.text}
                <span aria-hidden className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 animate-pulse bg-accent" />
              </p>
            )}
          </div>
        ) : editing ? (
          <form
            className="flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              saveEdit(thread.id, draft.id, spec.subject ? subject : undefined, body);
              setEditing(false);
            }}
          >
            {spec.subject && (
              <label className="flex flex-col gap-1 text-xs font-medium text-ink-2">
                Subject
                <input value={subject} onChange={(e) => setSubject(e.target.value)} className="h-9 px-3 text-sm font-normal" />
              </label>
            )}
            <label className="flex flex-col gap-1 text-xs font-medium text-ink-2">
              Message
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={14} className="px-3 py-2 text-sm font-normal leading-relaxed" />
            </label>
            <p className="text-xs text-ink-2">Saving creates a new version. Sources are cleared for sentences you rewrote.</p>
            <div className="flex justify-end gap-2">
              <Button onClick={() => setEditing(false)}>Cancel</Button>
              <Button type="submit" variant="primary" disabled={!body.trim()}>
                Save as v{piece.drafts.length + 1}
              </Button>
            </div>
          </form>
        ) : (
          <>
            {draft.subject && (
              <p className="mb-3 text-sm text-ink">
                <span className="text-ink-2">Subject: </span>
                <span className="font-medium">{draft.subject}</span>
              </p>
            )}
            <div className="flex flex-col gap-3">
              {draft.paragraphs.map((p, i) => (
                <div key={p.id} className="group relative rounded-lg">
                  <p className="text-sm leading-relaxed text-ink [overflow-wrap:anywhere]">
                    {p.sentences.map((s) => (
                      <SentenceView key={s.id} s={s} numbers={numbers} onPick={setOpen} />
                    ))}
                  </p>
                  {draft.paragraphs.length > 1 && isLatest && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        act(thread.id, draft.id, { kind: "revise", change: { paragraph: i }, request: `Rewrite paragraph ${i + 1}`, label: `Rewrote paragraph ${i + 1}.` })
                      }
                      className="mt-0.5 text-xs text-ink-2 opacity-0 transition-opacity hover:text-ink focus-visible:opacity-100 group-hover:opacity-100 disabled:hidden"
                    >
                      ↻ Rewrite paragraph {i + 1}
                    </button>
                  )}
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-ink-2">
              {c.words} words · {c.chars} characters
            </p>

            {claims.length > 0 && (
              <section aria-label="Claims to check" className="mt-4 rounded-xl border border-[#e0a526]/60 bg-[#e0a526]/10 p-3">
                <h4 className="text-sm font-semibold text-ink">
                  Claims to check <span className="font-normal text-ink-2">({claims.length})</span>
                </h4>
                <p className="mt-0.5 text-xs text-ink-2">These aren't in your notes. Confirm them, or take them out before you send.</p>
                <ul className="mt-2 flex flex-col gap-2">
                  {claims.map((s) => (
                    <li key={s.id} className="rounded-lg bg-surface p-2.5 text-sm text-ink">
                      “{s.text}”
                      <div className="mt-2 flex gap-2">
                        <Button variant="outline" onClick={() => resolveClaim(thread.id, draft.id, s.id, "confirm")}>
                          It's true, add to my notes
                        </Button>
                        <Button variant="outline" onClick={() => resolveClaim(thread.id, draft.id, s.id, "remove")}>
                          Remove it
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section aria-label="Sources" className="mt-4">
              <h4 className="text-sm font-semibold text-ink">Sources</h4>
              {order.length === 0 ? (
                <p className="mt-1 text-xs text-ink-2">No sources: this text was written or edited by you.</p>
              ) : (
                <ol className="mt-2 flex flex-col gap-1.5">
                  {order.map((id) => {
                    const src = sources[id];
                    if (!src) return null;
                    const isOpen = open === id;
                    return (
                      <li key={id} className="rounded-lg border border-line">
                        <button
                          onClick={() => setOpen(isOpen ? null : id)}
                          aria-expanded={isOpen}
                          className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-sm text-ink"
                        >
                          <span className="grid h-5 w-5 shrink-0 place-items-center rounded bg-accent/15 text-[11px] font-semibold text-ink">{numbers.get(id)}</span>
                          <span className="min-w-0 flex-1 truncate">{src.label}</span>
                          <span className="text-xs text-ink-2">{src.kind === "knowledge" ? "Your notes" : src.kind === "added" ? "Added" : "This thread"}</span>
                        </button>
                        {isOpen && <p className="border-t border-line px-2.5 py-2 text-xs leading-relaxed text-ink-2">{src.excerpt}</p>}
                      </li>
                    );
                  })}
                </ol>
              )}
            </section>
          </>
        )}
      </div>

      {!editing && !gen && (
        <div className="flex flex-col gap-2 border-t border-line px-4 py-3">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Change this draft">
            {quick("Shorter", "Make it shorter", { short: true }, "Made it shorter.")}
            {quick("Warmer", "Make it warmer", { tone: "warm" }, "Warmed up the tone.")}
            {quick("More formal", "Make it more formal", { tone: "formal" }, "Made it more formal.")}
            {quick("Another angle", "Try another angle", { bump: true }, "Tried a different angle.")}
            <Popover
              trigger={(isOpen, toggle) => (
                <Button variant="outline" disabled={busy} onClick={toggle} title="Rewrite as another kind of message">
                  Turn into… <span aria-hidden>{isOpen ? "▴" : "▾"}</span>
                </Button>
              )}
            >
              {(close) => (
                <ul>
                  {FORMAT_ORDER.filter((f) => f !== draft.format).map((f) => (
                    <li key={f}>
                      <button
                        onClick={() => {
                          close();
                          act(thread.id, draft.id, { kind: "format", format: f });
                        }}
                        className="w-full rounded-lg px-2.5 py-1.5 text-left text-sm text-ink hover:bg-surface-2"
                      >
                        {FORMATS[f].label} <span className="text-xs text-ink-2">· {FORMATS[f].rule}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Popover>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Button variant="primary" onClick={copy}>
              Copy
            </Button>
            {draft.format === "email" && (
              <a
                href={gmailLink(draft)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-8 items-center rounded-lg border border-line px-3 text-sm font-medium text-ink-2 hover:bg-surface-2 hover:text-ink"
              >
                Open in Gmail ↗
              </a>
            )}
            <Button variant="outline" onClick={startEdit}>
              Edit
            </Button>
            <Button variant="outline" onClick={() => downloadText(`${thread.company}-${spec.label}-v${draft.version}.txt`.replace(/\s+/g, "-"), fullText(draft))}>
              Download
            </Button>
            <span className="ml-auto" />
            <Popover
              align="right"
              width={260}
              trigger={(isOpen, toggle) => (
                <Button variant="outline" onClick={toggle} title="Record that you sent this">
                  Mark as used <span aria-hidden>{isOpen ? "▴" : "▾"}</span>
                </Button>
              )}
            >
              {(close) => (
                <div>
                  <p className="px-2.5 py-1 text-xs font-medium text-ink-2">Where did you use it?</p>
                  <label className="flex items-center gap-2 px-2.5 py-1 text-xs text-ink">
                    <input type="checkbox" checked={timeline} onChange={(e) => setTimeline(e.target.checked)} />
                    Add to this application's timeline
                  </label>
                  <ul>
                    {CHANNELS.map((ch) => (
                      <li key={ch}>
                        <button
                          onClick={() => {
                            markUsed(thread.id, draft.id, ch, timeline);
                            close();
                          }}
                          className="w-full rounded-lg px-2.5 py-1.5 text-left text-sm text-ink hover:bg-surface-2"
                        >
                          {ch}
                        </button>
                      </li>
                    ))}
                  </ul>
                  <p className="px-2.5 py-1 text-[11px] text-ink-2">P.I.P.E.R. never sends anything for you.</p>
                </div>
              )}
            </Popover>
          </div>
        </div>
      )}
    </aside>
  );
}
