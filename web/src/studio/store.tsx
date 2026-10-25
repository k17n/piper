/**
 * Studio state, held in memory with sample data. The screens only talk to `useStudio()`, so the real
 * backend can replace this file (and engine.ts) without changing them.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from "react";
import type { Stage } from "../lib/api";
import { buildDraft, claimsOf, detectIntent, fullText, notesUsed, paragraphsFromText, revise } from "./engine";
import type { Change } from "./engine";
import { sampleThreads } from "./sample";
import { FORMATS } from "./types";
import type { Channel, Draft, FormatId, Message, Thread, Tone } from "./types";
import { aOrAn, inline, iso, prefersReducedMotion, uid } from "./util";

export interface Generating {
  threadId: string;
  pieceId: string;
  format: FormatId;
  phase: "reading" | "writing";
  text: string;
}

export interface StudioState {
  threads: Thread[];
  knowledgeReady: boolean;
  animate: boolean;
  generating: Generating | null;
  toast: { id: number; text: string } | null;
}

type Action =
  | { type: "reset" }
  | { type: "knowledge"; ready: boolean }
  | { type: "animate"; on: boolean }
  | { type: "toast"; text: string | null }
  | { type: "thread"; thread: Thread }
  | { type: "message"; threadId: string; message: Message }
  | { type: "answer"; threadId: string; messageId: string; format: FormatId }
  | { type: "draft"; threadId: string; draft: Draft; message: Message }
  | { type: "gen"; gen: Generating | null }
  | { type: "gen-text"; text: string }
  | { type: "mark-used"; threadId: string; draftId: string; channel: Channel }
  | { type: "claim"; threadId: string; draftId: string; sentenceId: string; how: "confirm" | "remove" };

const initialState = (): StudioState => ({
  threads: sampleThreads(),
  knowledgeReady: true,
  animate: !prefersReducedMotion(),
  generating: null,
  toast: null,
});

let toastId = 0;

function mapThread(s: StudioState, id: string, fn: (t: Thread) => Thread): StudioState {
  return { ...s, threads: s.threads.map((t) => (t.id === id ? fn(t) : t)) };
}

function mapDrafts(t: Thread, draftId: string, fn: (d: Draft) => Draft): Thread {
  return { ...t, pieces: t.pieces.map((p) => ({ ...p, drafts: p.drafts.map((d) => (d.id === draftId ? fn(d) : d)) })) };
}

function reducer(s: StudioState, a: Action): StudioState {
  switch (a.type) {
    case "reset":
      return { ...initialState(), animate: s.animate, knowledgeReady: s.knowledgeReady };
    case "knowledge":
      return { ...s, knowledgeReady: a.ready };
    case "animate":
      return { ...s, animate: a.on };
    case "toast":
      return { ...s, toast: a.text ? { id: ++toastId, text: a.text } : null };
    case "thread":
      return { ...s, threads: [a.thread, ...s.threads] };
    case "message":
      return mapThread(s, a.threadId, (t) => ({ ...t, messages: [...t.messages, a.message], updatedAt: a.message.at }));
    case "answer":
      return mapThread(s, a.threadId, (t) => ({
        ...t,
        messages: t.messages.map((m) => (m.id === a.messageId ? { ...m, ask: { answered: a.format } } : m)),
      }));
    case "draft":
      return mapThread(s, a.threadId, (t) => {
        const has = t.pieces.some((p) => p.id === a.draft.pieceId);
        const pieces = has
          ? t.pieces.map((p) => (p.id === a.draft.pieceId ? { ...p, drafts: [...p.drafts, a.draft] } : p))
          : [...t.pieces, { id: a.draft.pieceId, format: a.draft.format, drafts: [a.draft] }];
        return { ...t, pieces, messages: [...t.messages, a.message], updatedAt: a.message.at };
      });
    case "gen":
      return { ...s, generating: a.gen };
    case "gen-text":
      return s.generating ? { ...s, generating: { ...s.generating, phase: "writing", text: a.text } } : s;
    case "mark-used":
      return mapThread(s, a.threadId, (t) =>
        mapDrafts(t, a.draftId, (d) => ({ ...d, usedOn: a.channel, usedAt: iso() })),
      );
    case "claim":
      return mapThread(s, a.threadId, (t) =>
        mapDrafts(t, a.draftId, (d) => ({
          ...d,
          paragraphs: d.paragraphs
            .map((p) => ({
              ...p,
              sentences:
                a.how === "remove"
                  ? p.sentences.filter((x) => x.id !== a.sentenceId)
                  : p.sentences.map((x) => (x.id === a.sentenceId ? { ...x, sources: ["added:now"] } : x)),
            }))
            .filter((p) => p.sentences.length > 0),
        })),
      );
  }
}

export type Act =
  | { kind: "revise"; change: Change; request: string; label: string }
  | { kind: "format"; format: FormatId };

export interface NewThread {
  company: string;
  role?: string;
  recipient?: string;
  stage?: Stage;
}

export interface Studio {
  state: StudioState;
  threadFor: (company: string) => Thread | undefined;
  createThread: (input: NewThread) => string;
  send: (threadId: string, text: string) => void;
  chooseFormat: (threadId: string, messageId: string, format: FormatId) => void;
  act: (threadId: string, draftId: string, act: Act) => void;
  stop: () => void;
  saveEdit: (threadId: string, draftId: string, subject: string | undefined, body: string) => void;
  markUsed: (threadId: string, draftId: string, channel: Channel, addToTimeline: boolean) => void;
  resolveClaim: (threadId: string, draftId: string, sentenceId: string, how: "confirm" | "remove") => void;
  toast: (text: string) => void;
  setKnowledgeReady: (ready: boolean) => void;
  setAnimate: (on: boolean) => void;
  reset: () => void;
}

const Ctx = createContext<Studio | null>(null);

export function useStudio(): Studio {
  const v = useContext(Ctx);
  if (!v) throw new Error("useStudio must be used inside <StudioProvider>");
  return v;
}

export const latestDraft = (t: Thread): Draft | null => t.pieces.at(-1)?.drafts.at(-1) ?? null;

export function StudioProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);
  const ref = useRef(state);
  ref.current = state;
  const timers = useRef<number[]>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  }, []);
  const later = useCallback((ms: number, fn: () => void) => {
    timers.current.push(window.setTimeout(fn, ms));
  }, []);
  useEffect(() => clearTimers, [clearTimers]);

  // toasts fade after a few seconds
  useEffect(() => {
    if (!state.toast) return;
    const id = window.setTimeout(() => dispatch({ type: "toast", text: null }), 3500);
    return () => window.clearTimeout(id);
  }, [state.toast]);

  const thread = (id: string) => ref.current.threads.find((t) => t.id === id);
  const say = (threadId: string, text: string, extra: Partial<Message> = {}) => {
    dispatch({ type: "message", threadId, message: { id: uid("m"), role: "assistant", text, at: iso(), ...extra } });
  };

  /** Show "reading", then stream the draft in, then add it to the thread. */
  const generate = useCallback(
    (threadId: string, make: () => { draft: Draft; trimmed: boolean }, lead: string) => {
      const { draft, trimmed } = make();
      const full = fullText(draft);
      clearTimers();
      dispatch({ type: "gen", gen: { threadId, pieceId: draft.pieceId, format: draft.format, phase: "reading", text: "" } });

      const finish = () => {
        const claims = claimsOf(draft).length;
        const parts = [lead];
        if (trimmed) parts.push(`I trimmed it to fit the limit (${FORMATS[draft.format].rule}).`);
        if (claims) parts.push(`${claims === 1 ? "One sentence isn't" : `${claims} sentences aren't`} in your notes, so I flagged ${claims === 1 ? "it" : "them"} under Claims to check.`);
        const message: Message = { id: uid("m"), role: "assistant", text: parts.join(" "), at: iso(), draft: { pieceId: draft.pieceId, draftId: draft.id } };
        dispatch({ type: "draft", threadId, draft, message });
        dispatch({ type: "gen", gen: null });
      };

      if (!ref.current.animate) return later(350, finish);
      later(750, () => {
        let i = 0;
        const step = () => {
          i += 9;
          if (i >= full.length) return finish();
          dispatch({ type: "gen-text", text: full.slice(0, i) });
          later(24, step);
        };
        step();
      });
    },
    [clearTimers, later],
  );

  /** Start a new piece. The lead sentence needs the finished draft (how many notes it used). */
  const writeWithLead = useCallback(
    (threadId: string, format: FormatId, tone: Tone, short: boolean, brief: string) => {
      const t = thread(threadId);
      if (!t) return;
      const pieceId = uid("pc");
      const label = FORMATS[format].label;
      const built = buildDraft({ thread: t, format, tone, short, variant: 0, brief, pieceId, version: 1 });
      generate(
        threadId,
        () => built,
        `Here's ${aOrAn(label)} ${inline(label)} for ${t.company}, grounded in ${notesUsed(built.draft)} of your notes.`,
      );
    },
    [generate],
  );

  const send = useCallback(
    (threadId: string, text: string) => {
      const clean = text.trim();
      const t = thread(threadId);
      if (!clean || !t || ref.current.generating) return;
      dispatch({ type: "message", threadId, message: { id: uid("m"), role: "user", text: clean, at: iso() } });
      const current = latestDraft(t);
      const intent = detectIntent(clean, !!current);

      if (intent.type === "revise" && current) {
        const version = (t.pieces.find((p) => p.id === current.pieceId)?.drafts.length ?? 0) + 1;
        return generate(threadId, () => revise(t, current, intent.change, version, intent.label), intent.label);
      }
      if (intent.type === "write" && intent.format === null) {
        return later(450, () => say(threadId, "Happy to. Which kind of message should this be?", { ask: {} }));
      }
      if (intent.type === "write" && intent.format) writeWithLead(threadId, intent.format, intent.tone, intent.short, clean);
    },
    [generate, later, writeWithLead],
  );

  const chooseFormat = useCallback(
    (threadId: string, messageId: string, format: FormatId) => {
      const t = thread(threadId);
      if (!t || ref.current.generating) return;
      const brief = [...t.messages].reverse().find((m) => m.role === "user")?.text ?? "";
      dispatch({ type: "answer", threadId, messageId, format });
      dispatch({ type: "message", threadId, message: { id: uid("m"), role: "user", text: FORMATS[format].label, at: iso() } });
      writeWithLead(threadId, format, "balanced", false, brief);
    },
    [writeWithLead],
  );

  const act = useCallback(
    (threadId: string, draftId: string, a: Act) => {
      const t = thread(threadId);
      const base = t?.pieces.flatMap((p) => p.drafts).find((d) => d.id === draftId);
      if (!t || !base || ref.current.generating) return;

      if (a.kind === "format") {
        dispatch({ type: "message", threadId, message: { id: uid("m"), role: "user", text: `Turn this into ${aOrAn(FORMATS[a.format].label)} ${inline(FORMATS[a.format].label)}`, at: iso() } });
        return writeWithLead(threadId, a.format, base.tone, base.short, base.brief);
      }
      dispatch({ type: "message", threadId, message: { id: uid("m"), role: "user", text: a.request, at: iso() } });
      const version = (t.pieces.find((p) => p.id === base.pieceId)?.drafts.length ?? 0) + 1;
      generate(threadId, () => revise(t, base, a.change, version, a.label), a.label);
    },
    [generate, writeWithLead],
  );

  const stop = useCallback(() => {
    const g = ref.current.generating;
    if (!g) return;
    clearTimers();
    dispatch({ type: "gen", gen: null });
    say(g.threadId, "Stopped before finishing, and nothing was saved. Ask again, or pick a quick action on the draft.");
  }, [clearTimers]);

  const saveEdit = useCallback((threadId: string, draftId: string, subject: string | undefined, body: string) => {
    const t = thread(threadId);
    const base = t?.pieces.flatMap((p) => p.drafts).find((d) => d.id === draftId);
    if (!t || !base) return;
    const version = (t.pieces.find((p) => p.id === base.pieceId)?.drafts.length ?? 0) + 1;
    const draft: Draft = {
      ...base,
      id: uid("d"),
      version,
      subject,
      paragraphs: paragraphsFromText(body, base.format),
      note: "Edited by you.",
      editedByYou: true,
      usedOn: undefined,
      usedAt: undefined,
      createdAt: iso(),
    };
    const message: Message = { id: uid("m"), role: "assistant", text: `Saved your edit as v${version}.`, at: iso(), draft: { pieceId: draft.pieceId, draftId: draft.id } };
    dispatch({ type: "draft", threadId, draft, message });
  }, []);

  const toast = useCallback((text: string) => dispatch({ type: "toast", text }), []);

  const markUsed = useCallback((threadId: string, draftId: string, channel: Channel, addToTimeline: boolean) => {
    dispatch({ type: "mark-used", threadId, draftId, channel });
    const company = thread(threadId)?.company ?? "the company";
    toast(addToTimeline ? `Marked as used on ${channel}, and added to the ${company} timeline (prototype: not saved).` : `Marked as used on ${channel}.`);
  }, [toast]);

  const resolveClaim = useCallback((threadId: string, draftId: string, sentenceId: string, how: "confirm" | "remove") => {
    dispatch({ type: "claim", threadId, draftId, sentenceId, how });
    toast(how === "confirm" ? "Added to your notes." : "Sentence removed.");
  }, [toast]);

  const createThread = useCallback((input: NewThread) => {
    const t: Thread = { id: uid("t"), ...input, messages: [], pieces: [], updatedAt: iso() };
    dispatch({ type: "thread", thread: t });
    return t.id;
  }, []);

  const value = useMemo<Studio>(
    () => ({
      state,
      threadFor: (company) => state.threads.find((t) => t.company.toLowerCase() === company.toLowerCase()),
      createThread,
      send,
      chooseFormat,
      act,
      stop,
      saveEdit,
      markUsed,
      resolveClaim,
      toast,
      setKnowledgeReady: (ready) => dispatch({ type: "knowledge", ready }),
      setAnimate: (on) => dispatch({ type: "animate", on }),
      reset: () => {
        clearTimers();
        dispatch({ type: "gen", gen: null });
        dispatch({ type: "reset" });
      },
    }),
    [state, createThread, send, chooseFormat, act, stop, saveEdit, markUsed, resolveClaim, toast, clearTimers],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
