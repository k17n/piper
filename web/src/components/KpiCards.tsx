import { useEffect, useRef, useState } from "react";
import type { Stats } from "../lib/api";

function useCountUp(target: number, duration = 600) {
  const [value, setValue] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setValue(target);
      return;
    }
    const start = performance.now();
    const origin = from.current;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(origin + (target - origin) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else from.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      from.current = target;
    };
  }, [target, duration]);
  return value;
}

function Kpi({ label, value, format, hint }: { label: string; value: number | null; format: (n: number) => string; hint?: string }) {
  const animated = useCountUp(value ?? 0);
  return (
    <div className="card flex flex-col gap-1 px-4 py-3">
      <div className="text-xs font-medium text-ink-2">{label}</div>
      <div className="tabular text-2xl font-semibold tracking-tight text-ink">{value == null ? "—" : format(animated)}</div>
      {hint && <div className="text-xs text-muted">{hint}</div>}
    </div>
  );
}

const pct = (n: number) => `${Math.round(n * 100)}%`;

export function KpiCards({ stats }: { stats: Stats | undefined }) {
  const s = stats;
  const of = (rate: number | undefined) => (s && rate != null ? `${Math.round(rate * s.total)} of ${s.total}` : undefined);
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      <Kpi label="Applications" value={s?.total ?? null} format={(n) => String(Math.round(n))} hint={s ? `${s.active} still active` : undefined} />
      <Kpi label="Response rate" value={s?.response_rate ?? null} format={pct} hint={of(s?.response_rate)} />
      <Kpi label="Interview rate" value={s?.interview_rate ?? null} format={pct} hint={of(s?.interview_rate)} />
      <Kpi label="Offer rate" value={s?.offer_rate ?? null} format={pct} hint={of(s?.offer_rate)} />
      <Kpi
        label="Median days to first response"
        value={s?.median_days_to_first_response ?? null}
        format={(n) => n.toFixed(1)}
        hint="Applied → first reply"
      />
    </div>
  );
}
