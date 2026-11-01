import type { Selection } from "../SankeyChart";
import { cx } from "../ui";
import { pct } from "./format";

export interface MixItem {
  key: string;
  label: string;
  count: number;
  ids?: number[];
  color?: string;
}

/** Horizontal bars with count and share. Rows that carry application ids open the side panel. */
export function MixBars({
  items,
  title,
  onSelect,
  empty = "Nothing to show yet",
  total: denominator,
}: {
  items: MixItem[];
  title: string;
  onSelect?: (s: Selection) => void;
  empty?: string;
  /** Denominator for the share; defaults to the sum of the listed items. */
  total?: number;
}) {
  const sum = items.reduce((s, i) => s + i.count, 0);
  const total = denominator && denominator > 0 ? denominator : sum;
  const max = Math.max(1, ...items.map((i) => i.count));
  if (sum === 0) return <div className="py-6 text-center text-sm text-muted">{empty}</div>;
  return (
    <ul className="flex flex-col gap-1">
      {items.map((i) => {
        const clickable = !!onSelect && !!i.ids?.length;
        return (
          <li key={i.key}>
            <button
              disabled={!clickable}
              onClick={() => clickable && onSelect!({ title: `${title}: ${i.label}`, ids: i.ids! })}
              className={cx(
                "grid w-full grid-cols-[minmax(6rem,11rem)_1fr_5rem] items-center gap-2 rounded-md px-1 py-0.5 text-left text-sm",
                clickable ? "hover:bg-surface-2" : "cursor-default",
              )}
            >
              <span className="truncate text-ink-2" title={i.label}>
                {i.label}
              </span>
              <span className="h-3 rounded-sm bg-surface-2">
                <span className="block h-full rounded-sm" style={{ width: `${(i.count / max) * 100}%`, background: i.color ?? "var(--accent)" }} />
              </span>
              <span className="tabular text-right text-ink">
                {i.count} <span className="text-muted">· {pct(i.count / total)}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
