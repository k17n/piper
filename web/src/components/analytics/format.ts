import type { Filters, Granularity } from "../../lib/api";

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const pct = (n: number) => `${Math.round(n * 100)}%`;

/** Escape text that goes into an ECharts HTML tooltip (company and role names come from email). */
export const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

/** A YYYY-MM-DD string as a local-midnight Date. */
export const parseDay = (iso: string) => new Date(`${iso}T00:00:00`);

export function fmtBucket(iso: string, g: Granularity) {
  const d = parseDay(iso);
  if (g === "month") return d.toLocaleDateString(undefined, { month: "short", year: "numeric" });
  const label = d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return g === "week" ? `Week of ${label}` : label;
}

/** Day bars up to ~3 months, weekly beyond that. */
export function defaultGranularity(f: Filters): Granularity {
  if (f.range === "180d" || f.range === "all") return "week";
  if (f.range === "custom" && f.from) {
    const to = f.to ? parseDay(f.to) : new Date();
    return (to.getTime() - parseDay(f.from).getTime()) / 86_400_000 > 90 ? "week" : "day";
  }
  return "day";
}
