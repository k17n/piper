let counter = 0;
export const uid = (prefix: string) => `${prefix}-${Date.now().toString(36)}${(counter++).toString(36)}`;

export const iso = (msAgo = 0) => new Date(Date.now() - msAgo).toISOString();
export const MIN = 60_000;
export const HOUR = 60 * MIN;
export const DAY = 24 * HOUR;

export const firstName = (full?: string) => (full ?? "").trim().split(/\s+/)[0] ?? "";

export function ago(isoString: string): string {
  const ms = Date.now() - new Date(isoString).getTime();
  if (ms < MIN) return "just now";
  if (ms < HOUR) return `${Math.round(ms / MIN)} min ago`;
  if (ms < DAY) return `${Math.round(ms / HOUR)} h ago`;
  if (ms < 2 * DAY) return "yesterday";
  return `${Math.round(ms / DAY)} d ago`;
}

export function shortDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export const aOrAn = (word: string) => (/^[aeiou]/i.test(word) ? "an" : "a");

export function downloadText(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** A format label inside a sentence: "email", but "LinkedIn note" keeps its capitals. */
export const inline = (label: string) => (/^(LinkedIn|WhatsApp)/.test(label) ? label : label.toLowerCase());
