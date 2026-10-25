import { buildDraft, notesUsed } from "./engine";
import type { Draft, Message, Thread, ThreadCtx } from "./types";
import { DAY, HOUR, MIN, iso, uid } from "./util";

const msg = (role: Message["role"], text: string, msAgo: number, extra: Partial<Message> = {}): Message => ({
  id: uid("m"),
  role,
  text,
  at: iso(msAgo),
  ...extra,
});

const ref = (d: Draft) => ({ pieceId: d.pieceId, draftId: d.id });
const intro = (label: string, d: Draft, company: string) =>
  `Here's ${label} for ${company}, grounded in ${notesUsed(d)} of your notes.`;

/** Fictional threads that show the main states: used pieces, a flagged claim, and an empty thread. */
export function sampleThreads(): Thread[] {
  // --- Northstar Bio: two pieces, versions, used ---
  const ns: ThreadCtx = { id: "t-northstar", company: "Northstar Bio", role: "Product Design Lead", recipient: "Jordan Lee" };
  const base = { thread: ns, tone: "balanced" as const, variant: 0 };
  const e1 = buildDraft({ ...base, format: "email", short: false, brief: "Write a thank-you email to Jordan after the panel interview.", pieceId: "pc-ns-email", version: 1 }).draft;
  const e2 = {
    ...buildDraft({ ...base, format: "email", short: true, brief: e1.brief, pieceId: "pc-ns-email", version: 2, note: "Made it shorter." }).draft,
    usedOn: "Email" as const,
    usedAt: iso(2 * DAY),
    createdAt: iso(2 * DAY + 20 * MIN),
  };
  const n1 = {
    ...buildDraft({ ...base, format: "linkedin_note", short: false, brief: "Send Jordan a LinkedIn connection note too.", pieceId: "pc-ns-note", version: 1 }).draft,
    usedOn: "LinkedIn" as const,
    usedAt: iso(2 * DAY - 30 * MIN),
  };
  const northstar: Thread = {
    ...ns,
    stage: "interview",
    context: {
      job: "Product Design Lead: own design for patient onboarding; partner with clinical and engineering leads.",
      thread: "Jordan Lee: “Thanks for your time with the team this week. We're finalising our decision and will be in touch by Friday.”",
    },
    messages: [
      msg("user", e1.brief, 3 * DAY),
      msg("assistant", intro("an email", e1, ns.company), 3 * DAY - MIN, { draft: ref(e1) }),
      msg("user", "Make it shorter", 2 * DAY + 25 * MIN),
      msg("assistant", "Made it shorter.", 2 * DAY + 24 * MIN, { draft: ref(e2) }),
      msg("user", n1.brief, 2 * DAY - 40 * MIN),
      msg("assistant", intro("a LinkedIn note", n1, ns.company), 2 * DAY - 41 * MIN, { draft: ref(n1) }),
    ],
    pieces: [
      { id: "pc-ns-email", format: "email", drafts: [e1, e2] },
      { id: "pc-ns-note", format: "linkedin_note", drafts: [n1] },
    ],
    updatedAt: iso(2 * DAY - 30 * MIN),
  };

  // --- Lumen Health: a cover letter with one claim to check ---
  const lh: ThreadCtx = { id: "t-lumen", company: "Lumen Health", role: "Design Systems Lead" };
  const cl = buildDraft({ thread: lh, format: "cover_letter", tone: "balanced", short: false, variant: 0, brief: "Draft a cover letter for the Design Systems Lead role.", pieceId: "pc-lh-cl", version: 1 }).draft;
  const lumen: Thread = {
    ...lh,
    stage: "applied",
    context: { job: "Design Systems Lead: scale one design system across clinical and consumer products." },
    messages: [
      msg("user", cl.brief, 5 * HOUR),
      msg(
        "assistant",
        `${intro("a cover letter", cl, lh.company)} One sentence isn't in your notes, so I flagged it under Claims to check.`,
        5 * HOUR - MIN,
        { draft: ref(cl) },
      ),
    ],
    pieces: [{ id: "pc-lh-cl", format: "cover_letter", drafts: [cl] }],
    updatedAt: iso(5 * HOUR),
  };

  // --- Wonka Labs: nothing written yet ---
  const wonka: Thread = {
    id: "t-wonka",
    company: "Wonka Labs",
    role: "Product Designer",
    messages: [],
    pieces: [],
    updatedAt: iso(3 * DAY),
  };

  return [lumen, northstar, wonka];
}
