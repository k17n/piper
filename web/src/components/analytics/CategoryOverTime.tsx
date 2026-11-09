import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { Analytics } from "../../lib/api";
import { CATEGORIES, CATEGORY_COLOR, categoryLabel } from "../../lib/stages";
import { categoryAxis, chartColors, MONO, reducedMotion, tip, tooltipStyle, valueAxis } from "./chartTheme";
import { fmtBucket, pct } from "./format";

export function CategoryOverTime({ data, dark }: { data: Analytics["category_by_week"]; dark: boolean }) {
  const option = useMemo(() => {
    const c = chartColors();
    const totals = data.map((w) => CATEGORIES.reduce((sum, cat) => sum + w[cat.value], 0));
    return {
      animation: !reducedMotion(),
      animationDuration: 500,
      animationEasing: "cubicOut",
      grid: { left: 36, right: 8, top: 8, bottom: 36 },
      legend: { bottom: 0, textStyle: { color: c.ink2, fontSize: 11 }, icon: "circle", itemWidth: 8, itemHeight: 8, itemGap: 16 },
      tooltip: {
        trigger: "axis",
        ...tooltipStyle(c),
        axisPointer: { type: "shadow", shadowStyle: { color: "rgba(128,128,128,0.08)" } },
        formatter: (params: { dataIndex: number }[]) => {
          const i = params[0].dataIndex;
          const w = data[i];
          const rows = CATEGORIES.filter((cat) => w[cat.value] > 0).map((cat) => ({
            dot: CATEGORY_COLOR[cat.value],
            label: categoryLabel(cat.value),
            value: `${w[cat.value]} · ${pct(w[cat.value] / totals[i])}`,
          }));
          return tip(`${fmtBucket(w.week, "week")} · ${totals[i]} applications`, rows);
        },
      },
      xAxis: categoryAxis(c, data.map((w) => fmtBucket(w.week, "day"))),
      yAxis: valueAxis(c, { max: 100, formatter: "{value}%" }),
      series: CATEGORIES.map((cat) => ({
        name: cat.label,
        type: "bar",
        stack: "share",
        barMaxWidth: 28,
        itemStyle: { color: CATEGORY_COLOR[cat.value], borderColor: c.surface, borderWidth: 1 },
        data: data.map((w, i) => (totals[i] ? (w[cat.value] / totals[i]) * 100 : 0)),
      })),
      textStyle: { fontFamily: MONO },
    };
  }, [data, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  return <ReactECharts option={option} notMerge style={{ height: 260, width: "100%" }} opts={{ renderer: "svg" }} />;
}
