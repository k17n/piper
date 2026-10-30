import type { Analytics } from "../../lib/api";
import { Kpi } from "../KpiCards";
import { fmtDate } from "../ui";

const int = (n: number) => String(Math.round(n));
const one = (n: number) => n.toFixed(1);

function versus(now: number, before: number | null, what: string) {
  if (before == null) return undefined;
  if (before === 0) return now > 0 ? `▲ from none ${what}` : `same as ${what}`;
  const change = Math.round(((now - before) / before) * 100);
  if (change === 0) return `same as ${what}`;
  return `${change > 0 ? "▲" : "▼"} ${Math.abs(change)}% vs ${what}`;
}

export function SummaryTiles({ s }: { s: Analytics["summary"] | undefined }) {
  const days = (n: number) => `${n} day${n === 1 ? "" : "s"}`;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <Kpi label="Applications" value={s?.total ?? null} format={int} hint={s ? versus(s.total, s.previous_total, "previous period") : undefined} />
      <Kpi label="Per active day" value={s?.per_active_day ?? null} format={one} hint={s ? `on ${days(s.active_days)} with an application` : undefined} />
      <Kpi label="Daily average" value={s?.daily_average ?? null} format={(n) => n.toFixed(2)} hint={s ? `${s.last_7d_average.toFixed(1)} a day over the last 7 days` : undefined} />
      <Kpi label="Current streak" value={s?.streak ?? null} format={int} hint={s ? `longest ${days(s.longest_streak)}` : undefined} />
      <Kpi label="Best day" value={s?.best_day?.count ?? null} format={int} hint={s?.best_day ? fmtDate(s.best_day.date) : undefined} />
      <Kpi label="This week" value={s?.this_week ?? null} format={int} hint={s ? versus(s.this_week, s.last_week, "last week") : undefined} />
    </div>
  );
}
