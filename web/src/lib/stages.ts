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

// Progress stages: ordinal blue ramp (light→dark as the funnel advances).
// Outcomes: reserved status colors (always shown with a text label). Neutral grays otherwise.
const STAGE_COLOR: Record<Stage, string> = {
  applied: "#6da7ec",
  viewed: "#5598e7",
  assessment: "#3987e5",
  interview: "#2a78d6",
  offer: "#256abf",
  accepted: "#0ca30c",
  rejected: "#d03b3b",
  withdrawn: "#8a8985",
  ghosted: "#6b6a66",
};
export const SOURCE_COLOR = "#9a988f";

export const stageColor = (s: string) => STAGE_COLOR[s as Stage] ?? SOURCE_COLOR;

// Role types are a categorical series, so each keeps one colour everywhere it is drawn.
export const CATEGORY_COLOR: Record<Category, string> = {
  design: "#8b6fd6",
  product: "#2a78d6",
  vc: "#d98a1f",
  other: "#9a988f",
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
