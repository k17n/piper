import type { Category, Source, Stage } from "./api";

export const STAGES: Stage[] = [
  "applied",
  "viewed",
  "assessment",
  "interview",
  "offer",
  "accepted",
  "rejected",
  "withdrawn",
  "ghosted",
];

export const SOURCES: { value: Source; label: string }[] = [
  { value: "linkedin", label: "LinkedIn" },
  { value: "ats", label: "Company site / ATS" },
  { value: "recruiter", label: "Recruiter" },
  { value: "direct", label: "Direct" },
  { value: "referral", label: "Referral" },
  { value: "other", label: "Other" },
];

export const CATEGORIES: { value: Category; label: string }[] = [
  { value: "design", label: "Design" },
  { value: "product", label: "Product" },
  { value: "vc", label: "VC" },
  { value: "other", label: "Other" },
];

export const categoryLabel = (c: string) => CATEGORIES.find((x) => x.value === c)?.label ?? c;

export const sourceLabel = (s: string) => SOURCES.find((x) => x.value === s)?.label ?? s;
export const stageLabel = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

// Progress stages: one indigo ramp, light→dark as the funnel advances.
// Outcomes: reserved status colors (always shown with a text label). Neutral grays otherwise.
const STAGE_COLOR: Record<Stage, string> = {
  applied: "#a5b4fc",
  viewed: "#8e9cf8",
  assessment: "#7480f3",
  interview: "#6366f1",
  offer: "#4f46e5",
  accepted: "#30a46c",
  rejected: "#e5484d",
  withdrawn: "#8b8b94",
  ghosted: "#5f5f68",
};
export const SOURCE_COLOR = "#8b8b94";

export const stageColor = (s: string) => STAGE_COLOR[s as Stage] ?? SOURCE_COLOR;

// Role types are a categorical series, so each keeps one colour everywhere it is drawn.
export const CATEGORY_COLOR: Record<Category, string> = {
  design: "#e0629a",
  product: "#6366f1",
  vc: "#e5a03a",
  other: "#8b8b94",
};

export const SENIORITY_LABEL: Record<string, string> = {
  intern: "Intern",
  junior: "Junior",
  mid: "Mid",
  senior: "Senior",
  staff: "Staff / Principal",
  lead: "Lead",
  head: "Head / Director+",
  unspecified: "Unspecified",
};
