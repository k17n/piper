import type { Source, Thread } from "./types";

/**
 * Sample knowledge base for the prototype (a fictional person). In the real feature these are chunks of the
 * user's own files in ~/.piper/knowledge/.
 */
export const KNOWLEDGE: Record<string, Source> = {
  "resume#impact": {
    id: "resume#impact",
    label: "resume.md › Impact",
    kind: "knowledge",
    excerpt: "Led design for a patient onboarding redesign that raised activation from 41% to 58% across 4 product teams.",
  },
  "resume#experience": {
    id: "resume#experience",
    label: "resume.md › Experience",
    kind: "knowledge",
    excerpt: "Product Design Lead at Carewell (2021 to now): regulated health products, a team of 6 designers.",
  },
  "strengths#systems": {
    id: "strengths#systems",
    label: "strengths.md › Systems thinking",
    kind: "knowledge",
    excerpt: "Turns messy, cross-team problems into a small set of principles the team can apply without me.",
  },
  "projects/onboarding#research": {
    id: "projects/onboarding#research",
    label: "projects/onboarding-redesign.md › Research",
    kind: "knowledge",
    excerpt: "Ran 14 interviews and a 3-week diary study; found patients abandoned at the insurance step.",
  },
  "projects/design-system#scale": {
    id: "projects/design-system#scale",
    label: "projects/design-system.md › Scale",
    kind: "knowledge",
    excerpt: "Consolidated three component libraries into one, now shared by 5 teams.",
  },
  "stories/conflict#outcome": {
    id: "stories/conflict#outcome",
    label: "stories/disagreeing-with-engineering.md › Outcome",
    kind: "knowledge",
    excerpt: "Prototyped both options with the engineering lead; the simpler one shipped and cut support tickets by a third.",
  },
  "added:now": {
    id: "added:now",
    label: "Added to your notes just now",
    kind: "added",
    excerpt: "You confirmed this statement is true, so it was added to your notes.",
  },
};

/** Sources that come from the thread itself: the job description and the conversation with the company. */
export function sourcesFor(thread: Pick<Thread, "id" | "company" | "role" | "context">): Record<string, Source> {
  return {
    ...KNOWLEDGE,
    [`job:${thread.id}`]: {
      id: `job:${thread.id}`,
      label: "Job description",
      kind: "context",
      excerpt:
        thread.context?.job ??
        `${thread.role ?? "The role"} at ${thread.company}. Paste the posting into the thread to ground drafts in it.`,
    },
    [`thread:${thread.id}`]: {
      id: `thread:${thread.id}`,
      label: "Your thread with the company",
      kind: "context",
      excerpt: thread.context?.thread ?? `Your latest messages with ${thread.company}.`,
    },
  };
}

export interface KnowledgeFile {
  path: string;
  core: boolean;
  what: string;
}

export const KNOWLEDGE_FILES: KnowledgeFile[] = [
  { path: "resume.md", core: true, what: "Your résumé, in your own words. Always used." },
  { path: "positioning.md", core: true, what: "Who you are, what you want next, and the voice you write in." },
  { path: "strengths.md", core: true, what: "What you are best at, with an example for each." },
  { path: "weaknesses.md", core: false, what: "Honest gaps, for framing and interview prep. Rarely quoted." },
  { path: "projects/", core: false, what: "One file per project or case study. Pulled in when relevant." },
  { path: "stories/", core: false, what: "Short stories (situation, action, result). Pulled in when relevant." },
  { path: "writing/", core: false, what: "Letters and messages you liked, as examples of your voice." },
];
