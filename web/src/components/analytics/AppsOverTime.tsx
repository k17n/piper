import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { AnalyticsPoint, Granularity } from "../../lib/api";
import type { Selection } from "../SankeyChart";
import { alpha, categoryAxis, chartColors, reducedMotion, tip, tooltipStyle, valueAxis } from "./chartTheme";
import { esc, fmtBucket } from "./format";

/** Mean of the last 7 points; null until there are 7. */
function trailingAverage(counts: number[]) {
  return counts.map((_, i) => (i < 6 ? null : Math.round((counts.slice(i - 6, i + 1).reduce((a, b) => a + b, 0) / 7) * 100) / 100));
}

export function AppsOverTime({
  data,
  granularity,
  showAverage,
  dark,
  onSelect,
}: {
  data: AnalyticsPoint[];
  granularity: Granularity;
  showAverage: boolean;
  dark: boolean;
  onSelect: (s: Selection) => void;
}) {
  const option = useMemo(() => {
    const c = chartColors(); // reads the live theme, so `dark` is a dependency below
    const counts = data.map((p) => p.count);
    const average = showAverage && granularity === "day" ? trailingAverage(counts) : null;
    return {
      animation: !reducedMotion(),
      animationDuration: 500,
      animationEasing: "cubicOut",
      grid: { left: 28, right: 8, top: 12, bottom: 24 },
      tooltip: {
        trigger: "axis",
        ...tooltipStyle(c),
        axisPointer: { type: "shadow", shadowStyle: { color: alpha(c.accent, 0.08) } },
        formatter: (params: { dataIndex: number }[]) => {
          const p = data[params[0].dataIndex];
          const rows = (p.apps ?? []).map((a) => ({ label: `${esc(a.company)} <span style="opacity:.6">· ${esc(a.role || "role not stated")}</span>` }));
          const more = p.count - rows.length;
          const avg = average?.[params[0].dataIndex];
          return tip(
            `${fmtBucket(p.date, granularity)} · ${p.count} application${p.count === 1 ? "" : "s"}`,
            rows,
            [more > 0 ? `+${more} more` : "", avg != null ? `7-day average ${avg}` : ""].filter(Boolean).join("<br/>"),
          );
        },
      },
      xAxis: categoryAxis(c, data.map((p) => fmtBucket(p.date, granularity))),
      yAxis: valueAxis(c, { minInterval: 1 }),
      series: [
        {
          name: "Applications",
          type: "bar",
          data: counts,
          barMaxWidth: 24,
          itemStyle: { color: alpha(c.accent, 0.85), borderRadius: [4, 4, 0, 0] },
          emphasis: { itemStyle: { color: c.accent } },
        },
        ...(average
          ? [{ name: "7-day average", type: "line", data: average, smooth: true, showSymbol: false, z: 3, lineStyle: { color: c.ink2, width: 1.5 }, itemStyle: { color: c.ink2 } }]
          : []),
      ],
    };
  }, [data, granularity, showAverage, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  const onEvents = useMemo(
    () => ({
      click: (p: { seriesType: string; dataIndex: number }) => {
        const point = data[p.dataIndex];
        if (p.seriesType === "bar" && point?.ids.length) onSelect({ title: fmtBucket(point.date, granularity), ids: point.ids });
      },
    }),
    [data, granularity, onSelect],
  );

  return <ReactECharts option={option} onEvents={onEvents} notMerge style={{ height: 280, width: "100%" }} opts={{ renderer: "svg" }} />;
}
