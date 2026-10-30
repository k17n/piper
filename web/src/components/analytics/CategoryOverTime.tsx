import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { Analytics } from "../../lib/api";
import { CATEGORIES, CATEGORY_COLOR, categoryLabel } from "../../lib/stages";
import { chartColors, reducedMotion, tooltipStyle } from "./chartTheme";
import { fmtBucket, pct } from "./format";

export function CategoryOverTime({ data, dark }: { data: Analytics["category_by_week"]; dark: boolean }) {
  const option = useMemo(() => {
    const c = chartColors();
    const totals = data.map((w) => CATEGORIES.reduce((sum, cat) => sum + w[cat.value], 0));
    return {
      animation: !reducedMotion(),
      grid: { left: 40, right: 12, top: 12, bottom: 36 },
      legend: { bottom: 0, textStyle: { color: c.ink2, fontSize: 11 }, icon: "roundRect", itemWidth: 10, itemHeight: 10 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        ...tooltipStyle(c),
        formatter: (params: { dataIndex: number }[]) => {
          const i = params[0].dataIndex;
          const w = data[i];
          const rows = CATEGORIES.filter((cat) => w[cat.value] > 0).map(
            (cat) => `${categoryLabel(cat.value)}: ${w[cat.value]} (${pct(w[cat.value] / totals[i])})`,
          );
          return [`<b>${fmtBucket(w.week, "week")}</b> · ${totals[i]} applications`, ...rows].join("<br/>");
        },
      },
      xAxis: {
        type: "category",
        data: data.map((w) => fmtBucket(w.week, "day")),
        axisLabel: { color: c.ink2, fontSize: 11, hideOverlap: true },
        axisLine: { lineStyle: { color: c.line } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        max: 100,
        axisLabel: { color: c.ink2, fontSize: 11, formatter: "{value}%" },
        splitLine: { lineStyle: { color: c.line } },
      },
      series: CATEGORIES.map((cat) => ({
        name: cat.label,
        type: "bar",
        stack: "share",
        barMaxWidth: 36,
        itemStyle: { color: CATEGORY_COLOR[cat.value] },
        data: data.map((w, i) => (totals[i] ? (w[cat.value] / totals[i]) * 100 : 0)),
      })),
    };
  }, [data, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  return <ReactECharts option={option} notMerge style={{ height: 260, width: "100%" }} opts={{ renderer: "svg" }} />;
}
