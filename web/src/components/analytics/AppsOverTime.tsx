import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { AnalyticsPoint, Granularity } from "../../lib/api";
import type { Selection } from "../SankeyChart";
import { chartColors, reducedMotion, tooltipStyle } from "./chartTheme";
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
      grid: { left: 32, right: 12, top: 16, bottom: 28 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        ...tooltipStyle(c),
        formatter: (params: { dataIndex: number }[]) => {
          const p = data[params[0].dataIndex];
          const lines = (p.apps ?? []).map((a) => `${esc(a.company)} <span style="opacity:.7">· ${esc(a.role || "role not stated")}</span>`);
          const more = p.count - lines.length;
          const avg = average?.[params[0].dataIndex];
          return [
            `<b>${fmtBucket(p.date, granularity)}</b> · ${p.count} application${p.count === 1 ? "" : "s"}`,
            ...lines,
            more > 0 ? `+${more} more` : "",
            avg != null ? `<span style="opacity:.7">7-day average ${avg}</span>` : "",
          ]
            .filter(Boolean)
            .join("<br/>");
        },
      },
      xAxis: {
        type: "category",
        data: data.map((p) => fmtBucket(p.date, granularity)),
        axisLabel: { color: c.ink2, fontSize: 11, hideOverlap: true },
        axisLine: { lineStyle: { color: c.line } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        axisLabel: { color: c.ink2, fontSize: 11 },
        splitLine: { lineStyle: { color: c.line } },
      },
      series: [
        { name: "Applications", type: "bar", data: counts, barMaxWidth: 28, itemStyle: { color: c.accent, borderRadius: [3, 3, 0, 0] } },
        ...(average
          ? [{ name: "7-day average", type: "line", data: average, smooth: true, showSymbol: false, z: 3, lineStyle: { color: c.ink2, width: 2 }, itemStyle: { color: c.ink2 } }]
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
