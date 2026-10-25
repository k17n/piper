import type { Stage } from "../lib/api";

export type FormatId = "cover_letter" | "linkedin_note" | "linkedin_message" | "whatsapp" | "email";
export type Tone = "balanced" | "warm" | "formal";
/** plain: greetings, asks (no source needed) · company: from the posting or thread · fact: a claim about the user */
export type SentenceKind = "plain" | "company" | "fact";
export type Channel = "Email" | "LinkedIn" | "WhatsApp" | "Application form" | "Other";

export const CHANNELS: Channel[] = ["Email", "LinkedIn", "WhatsApp", "Application form", "Other"];

export interface FormatSpec {
  id: FormatId;
  label: string;
  /** The rule the output must follow, shown to the user. */
  rule: string;
  unit: "words" | "chars" | "lines";
  min?: number;
  max?: number;
  subject: boolean;
  defaultChannel: Channel;
}

export const FORMATS: Record<FormatId, FormatSpec> = {
  email: { id: "email", label: "Email", rule: "80–200 words with a subject", unit: "words", min: 80, max: 200, subject: true, defaultChannel: "Email" },
  linkedin_message: { id: "linkedin_message", label: "LinkedIn message", rule: "60–150 words", unit: "words", min: 60, max: 150, subject: false, defaultChannel: "LinkedIn" },
  linkedin_note: { id: "linkedin_note", label: "LinkedIn note", rule: "300 characters at most", unit: "chars", max: 300, subject: false, defaultChannel: "LinkedIn" },
  whatsapp: { id: "whatsapp", label: "WhatsApp", rule: "1–4 short lines, no sign-off", unit: "lines", min: 1, max: 4, subject: false, defaultChannel: "WhatsApp" },
  cover_letter: { id: "cover_letter", label: "Cover letter", rule: "250–400 words", unit: "words", min: 250, max: 400, subject: false, defaultChannel: "Application form" },
};
export const FORMAT_ORDER: FormatId[] = ["email", "linkedin_message", "linkedin_note", "whatsapp", "cover_letter"];

export interface Sentence {
  id: string;
  text: string;
  kind: SentenceKind;
  /** Ids of the sources this statement rests on. A "fact" with none is a claim to check. */
  sources: string[];
  optional?: boolean;
}
export interface Paragraph {
  id: string;
  sentences: Sentence[];
}

export interface Draft {
  id: string;
  pieceId: string;
  version: number;
  format: FormatId;
  tone: Tone;
  short: boolean;
  variant: number;
  /** What the user asked for, kept so the draft can be regenerated or turned into another format. */
  brief: string;
  subject?: string;
  paragraphs: Paragraph[];
  /** What changed from the previous version, e.g. "Made it shorter". */
  note?: string;
  editedByYou?: boolean;
  usedOn?: Channel;
  usedAt?: string;
  createdAt: string;
}

/** One thing being written (an email, a LinkedIn note…) with all its versions. */
export interface Piece {
  id: string;
  format: FormatId;
  drafts: Draft[];
}

export interface Source {
  id: string;
  label: string;
  kind: "knowledge" | "context" | "added";
  excerpt: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  at: string;
  /** The assistant asked which kind of message to write. */
  ask?: { answered?: FormatId };
  /** The assistant produced this draft. */
  draft?: { pieceId: string; draftId: string };
}

export interface Thread {
  id: string;
  company: string;
  role?: string;
  recipient?: string;
  stage?: Stage;
  /** Text behind the "job description" and "thread" sources. */
  context?: { job?: string; thread?: string };
  messages: Message[];
  pieces: Piece[];
  updatedAt: string;
}

export type ThreadCtx = Pick<Thread, "id" | "company" | "role" | "recipient">;
