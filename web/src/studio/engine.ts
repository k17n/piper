/**
 * A stand-in for the real writing engine: deterministic templates that behave like the real thing
 * (format rules, sources per sentence, flagged claims, tone and length changes). The UI is built against
 * these shapes, so the real backend can replace this file without touching the screens.
 */
import { FORMATS } from "./types";
import type { Draft, FormatId, Paragraph, Sentence, SentenceKind, ThreadCtx, Tone } from "./types";
import { firstName, iso, uid } from "./util";
import { KNOWLEDGE } from "./knowledge";

type ToneText = { balanced: string; warm?: string; formal?: string };
interface Tpl {
  kind: SentenceKind;
  text: string | ToneText;
  /** "@job" and "@thread" resolve to this thread's own sources. */
  sources?: string[];
  optional?: boolean;
  onlyTone?: Tone;
}

const T: Record<string, Tpl> = {
  // greetings, asks and sign-offs
  hi_first: { kind: "plain", text: { balanced: "Hi {first},", formal: "Hello {first}," } },
  hi_team: { kind: "plain", text: "Dear {company} hiring team," },
  signoff: { kind: "plain", text: { balanced: "Best,\nAlex", warm: "Warmly,\nAlex", formal: "Kind regards,\nAlex Rivera" } },
  signoff_short: { kind: "plain", text: { balanced: "Thanks,\nAlex", warm: "Thank you!\nAlex", formal: "Kind regards,\nAlex" } },
  thanks: { kind: "plain", text: { balanced: "Thank you for your time and consideration.", warm: "Thank you so much for your time." } },
  // cover letter
  cl_1: {
    kind: "company",
    sources: ["@job"],
    text: { balanced: "I'd like to be considered for {a_role} at {company}.", formal: "I would like to be considered for {a_role} at {company}." },
  },
  cl_2: {
    kind: "company",
    sources: ["@job"],
    text: "Owning design for a product like this, in close partnership with engineering and product, is the work I have been building toward for the last several years.",
  },
  f_impact: {
    kind: "fact",
    sources: ["resume#impact"],
    text: "At Carewell I led the redesign of patient onboarding, which raised activation from 41% to 58% across four product teams.",
  },
  f_research: {
    kind: "fact",
    sources: ["projects/onboarding#research"],
    text: "Before drawing a single screen, I ran 14 interviews and a three-week diary study, which showed that patients were abandoning at the insurance step rather than where we had assumed.",
  },
  f_research2: {
    kind: "fact",
    sources: ["projects/onboarding#research"],
    text: "Our research found that patients were abandoning at the insurance step, not where we had assumed, so we rebuilt that step first.",
  },
  f_system: {
    kind: "fact",
    sources: ["projects/design-system#scale"],
    text: "I also consolidated three separate component libraries into one that five teams now share, so a decision made once carries through every product.",
  },
  f_think: {
    kind: "fact",
    sources: ["strengths#systems"],
    text: "What I do best is turn messy, cross-team problems into a handful of principles that teams can apply without needing me in the room.",
  },
  f_story: {
    kind: "fact",
    sources: ["stories/conflict#outcome"],
    text: "When I disagreed with engineering about an approach, I prototyped both options with them, and the simpler one shipped and cut support tickets by a third.",
  },
  claim_talks: {
    kind: "fact",
    sources: [],
    optional: true,
    text: "I have also spoken about designing for regulated products at industry conferences.",
  },
  why_company: {
    kind: "company",
    sources: ["@job"],
    text: "What draws me to {company} is the chance to apply that approach to problems where the constraints are real and the people affected are depending on the product.",
  },
  cl_fit: {
    kind: "company",
    sources: ["@job"],
    text: "Having looked closely at how your team works, I think my background in regulated products would be useful from the first week.",
  },
  warm_cl: { kind: "plain", onlyTone: "warm", text: "It would mean a great deal to do this work with your team." },
  cl_ask: {
    kind: "plain",
    text: {
      balanced: "I'd welcome a conversation about how I could help, and I'm happy to walk through the onboarding work in as much detail as is useful.",
      warm: "I'd love to talk about how I could help, and I'm happy to walk through the onboarding work in as much detail as is useful.",
      formal: "I would welcome a conversation about how I could contribute, and I am glad to walk through the onboarding work in whatever detail is useful.",
    },
  },
  // LinkedIn note
  ln_1: {
    kind: "fact",
    sources: ["resume#experience"],
    text: "I lead product design for regulated health products at Carewell and admire what {company} is building.",
  },
  ln_2: { kind: "company", sources: ["@job"], optional: true, text: "Your team's work caught my eye." },
  ln_long: {
    kind: "fact",
    sources: ["resume#experience"],
    optional: true,
    text: "Over the last few years I've led patient-facing design for onboarding, scheduling and billing at Carewell, and I'm always keen to compare notes with teams tackling similar problems.",
  },
  ln_3: { kind: "plain", text: { balanced: "I'd love to connect and swap notes.", warm: "I'd love to connect and swap notes!", formal: "I would welcome the chance to connect." } },
  warm_ln: { kind: "plain", onlyTone: "warm", text: "Hope you're having a great week!" },
  // LinkedIn message
  lm_1: {
    kind: "company",
    sources: ["@job"],
    text: "I've been following {company}'s work, and it lines up closely with a project I led at Carewell.",
  },
  lm_why: {
    kind: "company",
    sources: ["@job"],
    text: "The work you're doing looks like a natural next step for what I've been building.",
  },
  lm_2: {
    kind: "plain",
    optional: true,
    text: "I'd be glad to share what we learned about where patients drop off, if that's useful.",
  },
  lm_ask: {
    kind: "plain",
    text: {
      balanced: "Would you be open to a 20-minute chat in the next couple of weeks?",
      warm: "Would you be up for a quick 20-minute chat in the next couple of weeks?",
      formal: "Would you be available for a 20-minute conversation in the coming weeks?",
    },
  },
  warm_lm: { kind: "plain", onlyTone: "warm", text: "Hope your week is going well!" },
  // WhatsApp
  wa_1: { kind: "plain", text: "Hi {first}, it's Alex." },
  wa_2: {
    kind: "company",
    sources: ["@thread"],
    text: "Great to chat earlier, thanks again for the intro to the {company} team.",
  },
  wa_ask: {
    kind: "plain",
    text: {
      balanced: "Would you have 15 minutes this week for a quick call about {a_role}?",
      warm: "Do you have 15 minutes this week for a quick call about {a_role}? No rush at all.",
      formal: "Would you have 15 minutes this week for a brief call about {a_role}?",
    },
  },
  warm_wa: { kind: "plain", onlyTone: "warm", text: "Hope your week is going well!" },
  // email
  subj_follow: { kind: "plain", text: "Following up: {conv}" },
  subj_thanks: { kind: "plain", text: "Thank you for the time this week" },
  em_1: {
    kind: "company",
    sources: ["@thread"],
    text: "Thank you for the time with the team this week; I especially enjoyed the conversation about how real-world constraints shape the product and the people using it.",
  },
  warm_em: { kind: "plain", onlyTone: "warm", text: "I really enjoyed meeting everyone." },
  f_link: {
    kind: "fact",
    sources: ["resume#impact"],
    text: "It reinforced how closely this role matches the onboarding work I led at Carewell, where activation rose from 41% to 58% across four product teams.",
  },
  em_fit: {
    kind: "company",
    sources: ["@thread"],
    text: "The questions about clinical constraints are the kind I enjoy most, and I left more convinced that I could contribute quickly.",
  },
  em_extra: {
    kind: "plain",
    optional: true,
    text: "I'm happy to send a short write-up of the research behind that project if it would help.",
  },
  em_ask: {
    kind: "plain",
    text: {
      balanced: "Is there anything else I can share ahead of your decision?",
      warm: "Please let me know if there's anything else I can share ahead of your decision.",
      formal: "Please let me know if I can provide anything further ahead of your decision.",
    },
  },
};

type Slot = string[];
interface Blueprint {
  subject?: Slot;
  /** paragraphs → slots → alternative templates (one is picked by the variant number) */
  paragraphs: Slot[][];
}

const BLUEPRINTS: Record<FormatId, Blueprint> = {
  cover_letter: {
    paragraphs: [
      [["hi_team"]],
      [["cl_1"], ["cl_2"]],
      [["f_impact"], ["f_research", "f_research2"], ["f_system"], ["f_think"], ["f_story"], ["claim_talks"]],
      [["why_company"], ["cl_fit"]],
      [["warm_cl"], ["cl_ask"], ["thanks"]],
      [["signoff"]],
    ],
  },
  linkedin_note: {
    paragraphs: [[["hi_first"], ["warm_ln"], ["ln_1"], ["ln_2", "ln_long"], ["ln_3"]]],
  },
  linkedin_message: {
    paragraphs: [
      [["hi_first"], ["warm_lm"]],
      [["lm_1"], ["f_impact"], ["lm_why"]],
      [["lm_2"]],
      [["lm_ask"]],
      [["signoff_short"]],
    ],
  },
  whatsapp: {
    paragraphs: [[["wa_1"]], [["warm_wa"]], [["wa_2"]], [["wa_ask"]]],
  },
  email: {
    subject: ["subj_follow", "subj_thanks"],
    paragraphs: [
      [["hi_first"]],
      [["em_1"], ["warm_em"]],
      [["f_link"], ["em_fit"], ["em_extra"]],
      [["em_ask"]],
      [["signoff"]],
    ],
  },
};

interface Ctx {
  company: string;
  role?: string;
  first: string;
  threadId: string;
}

function fill(text: string, c: Ctx): string {
  return text
    .replaceAll("{company}", c.company)
    .replaceAll("{first}", c.first || "there")
    .replaceAll("{role}", c.role ?? "design")
    .replaceAll("{a_role}", c.role ? `the ${c.role} role` : "a role")
    .replaceAll("{conv}", c.role ? `${c.role} conversation` : `conversation with ${c.company}`);
}

function resolveSource(id: string, threadId: string): string {
  return id === "@job" ? `job:${threadId}` : id === "@thread" ? `thread:${threadId}` : id;
}

function tplText(t: Tpl, tone: Tone): string {
  if (typeof t.text === "string") return t.text;
  return t.text[tone] ?? t.text.balanced;
}

export interface BuildInput {
  thread: ThreadCtx;
  format: FormatId;
  tone: Tone;
  short: boolean;
  variant: number;
  brief: string;
  pieceId: string;
  version: number;
  note?: string;
}

export function buildDraft(i: BuildInput): { draft: Draft; trimmed: boolean } {
  const ctx: Ctx = { company: i.thread.company, role: i.thread.role, first: firstName(i.thread.recipient), threadId: i.thread.id };
  const bp = BLUEPRINTS[i.format];
  const keep = (t: Tpl) => !(t.onlyTone && t.onlyTone !== i.tone) && !(i.short && t.optional);

  const paragraphs: Paragraph[] = bp.paragraphs
    .map((slots) => ({
      id: uid("p"),
      sentences: slots
        .map((alts) => T[alts[i.variant % alts.length]])
        .filter(keep)
        .map<Sentence>((t) => ({
          id: uid("s"),
          text: fill(tplText(t, i.tone), ctx),
          kind: t.kind,
          sources: (t.sources ?? []).map((s) => resolveSource(s, ctx.threadId)),
          optional: t.optional,
        })),
    }))
    .filter((p) => p.sentences.length > 0);

  const subjectTpl = bp.subject ? T[bp.subject[i.variant % bp.subject.length]] : undefined;
  const draft: Draft = {
    id: uid("d"),
    pieceId: i.pieceId,
    version: i.version,
    format: i.format,
    tone: i.tone,
    short: i.short,
    variant: i.variant,
    brief: i.brief,
    subject: subjectTpl ? fill(tplText(subjectTpl, i.tone), ctx) : undefined,
    paragraphs,
    note: i.note,
    createdAt: iso(),
  };
  return { draft, trimmed: fit(draft) };
}

/** Enforce a hard limit by dropping optional sentences from the end. Returns true if anything was dropped. */
function fit(d: Draft): boolean {
  const spec = FORMATS[d.format];
  if (!spec.max) return false;
  let trimmed = false;
  while (countsOf(d)[spec.unit] > spec.max) {
    const flat = d.paragraphs.flatMap((p) => p.sentences);
    const last = [...flat].reverse().find((s) => s.optional);
    if (!last) break;
    d.paragraphs = d.paragraphs
      .map((p) => ({ ...p, sentences: p.sentences.filter((s) => s.id !== last.id) }))
      .filter((p) => p.sentences.length > 0);
    trimmed = true;
  }
  return trimmed;
}

// --- reading a draft --------------------------------------------------------------------------

export function bodyText(d: Draft): string {
  const joiner = d.format === "whatsapp" ? "\n" : "\n\n";
  return d.paragraphs.map((p) => p.sentences.map((s) => s.text).join(" ")).join(joiner);
}

export const fullText = (d: Draft) => (d.subject ? `Subject: ${d.subject}\n\n${bodyText(d)}` : bodyText(d));

export function countsOf(d: Draft) {
  const body = bodyText(d).trim();
  return { chars: bodyText(d).length, words: body ? body.split(/\s+/).length : 0, lines: d.paragraphs.length };
}

export function ruleStatus(d: Draft): { state: "ok" | "short" | "long"; text: string } {
  const spec = FORMATS[d.format];
  const value = countsOf(d)[spec.unit];
  const unit = spec.unit === "chars" ? "characters" : spec.unit;
  const target = spec.min && spec.max ? `${spec.min}–${spec.max}` : spec.max ? `max ${spec.max}` : "";
  if (spec.max && value > spec.max) return { state: "long", text: `${value} ${unit}, over the limit of ${spec.max}` };
  if (spec.min && value < spec.min) return { state: "short", text: `${value} ${unit}, below the target of ${spec.min}` };
  return { state: "ok", text: `${value} ${unit}${target ? ` · target ${target}` : ""}` };
}

/** Statements about the user that rest on nothing in their notes. */
export function claimsOf(d: Draft): Sentence[] {
  return d.paragraphs.flatMap((p) => p.sentences).filter((s) => s.kind === "fact" && s.sources.length === 0);
}

/** Source ids in order of first use: this order becomes the footnote numbers. */
export function sourceOrder(d: Draft): string[] {
  return [...new Set(d.paragraphs.flatMap((p) => p.sentences).flatMap((s) => s.sources))];
}

export const notesUsed = (d: Draft) => sourceOrder(d).filter((id) => id in KNOWLEDGE).length;

export function paragraphsFromText(body: string, format: FormatId): Paragraph[] {
  const splitter = format === "whatsapp" ? /\n+/ : /\n{2,}/;
  return body
    .split(splitter)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((par) => ({
      id: uid("p"),
      sentences: par
        .split(/(?<=[.!?])\s+(?=[A-Z"“(])/)
        .map<Sentence>((text) => ({ id: uid("s"), text: text.trim(), kind: "plain", sources: [] })),
    }));
}

// --- understanding a request ------------------------------------------------------------------

export interface Change {
  tone?: Tone;
  short?: boolean;
  /** Try a different angle (next variant) */
  bump?: boolean;
  /** Rewrite just this paragraph (index) */
  paragraph?: number;
}

export type Intent =
  | { type: "revise"; change: Change; label: string }
  | { type: "write"; format: FormatId | null; tone: Tone; short: boolean };

export function detectFormat(text: string): FormatId | null {
  const t = text.toLowerCase();
  if (/cover letter/.test(t)) return "cover_letter";
  if (/(connection|linkedin).*(note|request)|(note|request).*linkedin|connect(ion)? note/.test(t)) return "linkedin_note";
  if (/linkedin|inmail/.test(t)) return "linkedin_message";
  if (/whatsapp|text message/.test(t)) return "whatsapp";
  if (/e-?mail|follow[- ]?up|thank[- ]?you note|thank-you/.test(t)) return "email";
  return null;
}

export function detectIntent(text: string, hasDraft: boolean): Intent {
  const t = text.toLowerCase();
  const format = detectFormat(t);
  if (hasDraft && format === null) {
    if (/\bshorter\b|\btrim\b|\bcut (it|this) down\b/.test(t)) return { type: "revise", change: { short: true }, label: "Made it shorter." };
    if (/\bwarmer\b|\bfriendlier\b/.test(t)) return { type: "revise", change: { tone: "warm" }, label: "Warmed up the tone." };
    if (/more formal|\bformalise\b|\bformalize\b/.test(t)) return { type: "revise", change: { tone: "formal" }, label: "Made it more formal." };
    if (/try again|regenerate|another (version|take|angle)|different angle/.test(t)) return { type: "revise", change: { bump: true }, label: "Tried a different angle." };
  }
  const tone: Tone = /\b(warm|friendly|casual)\b/.test(t) ? "warm" : /\b(formal|professional)\b/.test(t) ? "formal" : "balanced";
  return { type: "write", format, tone, short: /\b(short|brief|concise|quick)\b/.test(t) };
}

/** Build the next version of a draft with one change applied. */
export function revise(thread: ThreadCtx, base: Draft, change: Change, version: number, note: string) {
  const paragraphOnly = change.paragraph !== undefined;
  const built = buildDraft({
    thread,
    format: base.format,
    tone: change.tone ?? base.tone,
    short: change.short ?? base.short,
    variant: base.variant + (change.bump || paragraphOnly ? 1 : 0),
    brief: base.brief,
    pieceId: base.pieceId,
    version,
    note,
  });
  if (!paragraphOnly) return built;
  const idx = change.paragraph as number;
  const draft: Draft = {
    ...built.draft,
    tone: base.tone,
    short: base.short,
    variant: base.variant,
    paragraphs: base.paragraphs.map((p, i) => (i === idx && built.draft.paragraphs[i] ? built.draft.paragraphs[i] : p)),
  };
  return { draft, trimmed: false };
}
