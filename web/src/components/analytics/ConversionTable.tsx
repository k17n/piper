import { useState } from "react";
import type { Analytics } from "../../lib/api";
import { SENIORITY_LABEL, categoryLabel, sourceLabel } from "../../lib/stages";
import { cx } from "../ui";
import { pct } from "./format";
import { Segmented } from "./Section";

type Dimension = "source" | "category" | "seniority";
const SMALL_SAMPLE = 5;
const HEADING: Record<Dimension, string> = { source: "Source", category: "Role type", seniority: "Seniority" };
const LABEL: Record<Dimension, (key: string) => string> = {
  source: sourceLabel,
  category: categoryLabel,
  seniority: (k) => SENIORITY_LABEL[k] ?? k,
};

export function ConversionTable({ conversion }: { conversion: Analytics["conversion"] }) {
  const [dimension, setDimension] = useState<Dimension>("source");
  const cell = (rate: number, total: number) => `${pct(rate)} (${Math.round(rate * total)})`;
  return (
    <div>
      <div className="mb-3">
        <Segmented
          value={dimension}
          onChange={setDimension}
          options={(Object.keys(HEADING) as Dimension[]).map((value) => ({ value, label: HEADING[value] }))}
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr className="text-left text-xs text-muted">
              <th className="py-1 pr-3 font-medium">{HEADING[dimension]}</th>
              <th className="px-3 py-1 text-right font-medium">Applied</th>
              <th className="px-3 py-1 text-right font-medium">Responded</th>
              <th className="px-3 py-1 text-right font-medium">Interviewed</th>
              <th className="px-3 py-1 text-right font-medium">Offers</th>
              <th className="py-1 pl-3 text-right font-medium">Median days to reply</th>
            </tr>
          </thead>
          <tbody>
            {conversion[dimension].map((r) => {
              const small = r.total < SMALL_SAMPLE;
              const rate = cx("tabular px-3 py-1.5 text-right", small ? "text-muted" : "text-ink");
              return (
                <tr key={r.key} className="border-t border-line transition-colors hover:bg-surface-2/60" title={small ? `Small sample: fewer than ${SMALL_SAMPLE} applications` : undefined}>
                  <td className="py-1.5 pr-3 text-ink">
                    {LABEL[dimension](r.key)}
                    {small && <span className="ml-2 text-xs text-muted">small sample</span>}
                  </td>
                  <td className="tabular px-3 py-1.5 text-right text-ink">{r.total}</td>
                  <td className={rate}>{cell(r.responded, r.total)}</td>
                  <td className={rate}>{cell(r.interviewed, r.total)}</td>
                  <td className="tabular px-3 py-1.5 text-right text-ink">{r.offers}</td>
                  <td className="tabular py-1.5 pl-3 text-right text-ink-2">{r.median_days == null ? "—" : r.median_days.toFixed(1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
