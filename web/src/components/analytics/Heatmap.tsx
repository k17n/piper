import type { AnalyticsPoint } from "../../lib/api";
import type { Selection } from "../SankeyChart";
import { fmtBucket, parseDay } from "./format";

const LEVELS = 4;
const shade = (level: number) =>
  level === 0 ? "var(--surface-2)" : `color-mix(in srgb, var(--accent) ${(100 / LEVELS) * level}%, var(--surface-2))`;

/** One square per day, a column per week (Monday on top). `days` must be consecutive. */
export function Heatmap({ days, onSelect }: { days: AnalyticsPoint[]; onSelect: (s: Selection) => void }) {
  if (days.length === 0) return null;
  const max = Math.max(1, ...days.map((d) => d.count));
  const lead = (parseDay(days[0].date).getDay() + 6) % 7; // blank cells so the first day lands on its weekday row
  return (
    <div>
      <div className="overflow-x-auto pb-1">
        <div className="grid w-max grid-flow-col grid-rows-7 gap-[3px]">
          {Array.from({ length: lead }, (_, i) => (
            <span key={`pad-${i}`} className="size-3" />
          ))}
          {days.map((d) => {
            const level = d.count === 0 ? 0 : Math.max(1, Math.ceil((d.count / max) * LEVELS));
            const label = `${fmtBucket(d.date, "day")}: ${d.count} application${d.count === 1 ? "" : "s"}`;
            return (
              <button
                key={d.date}
                title={label}
                aria-label={label}
                disabled={d.count === 0}
                onClick={() => onSelect({ title: fmtBucket(d.date, "day"), ids: d.ids })}
                className="size-3 rounded-[3px] disabled:cursor-default"
                style={{ background: shade(level) }}
              />
            );
          })}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-end gap-1 text-xs text-muted">
        Less
        {Array.from({ length: LEVELS + 1 }, (_, l) => (
          <span key={l} className="size-3 rounded-[3px]" style={{ background: shade(l) }} />
        ))}
        More
      </div>
    </div>
  );
}
