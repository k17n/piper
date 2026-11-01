import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { Analytics } from "../../lib/api";
import { chartColors, reducedMotion, tooltipStyle } from "./chartTheme";
import { fmtBucket, pct } from "./format";

/** Response rate by the week an application was sent. The newest weeks are dashed: replies may not be in yet. */
export function Cohorts({ data, dark }: { data: Analytics["cohorts"]; dark: boolean }) {
  const option = useMemo(() => {
    const c = chartColors();
    const rate = (i: number) => Math.round(data[i].responded * 1000) / 10;
    let lastMature = -1;
    data.forEach((p, i) => {
      if (!p.maturing) lastMature = i;
    });
    return {
      animation: !reducedMotion(),
      grid: { left: 40, right: 12, top: 12, bottom: 28 },
      tooltip: {
        trigger: "axis",
        ...tooltipStyle(c),
        formatter: (params: { dataIndex: number }[]) => {
          const p = data[params[0].dataIndex];
          const note = p.maturing ? '<br/><span style="opacity:.7">still maturing</span>' : "";
          const small = p.total < 5 ? " (small sample)" : "";
          return `<b>${fmtBucket(p.week, "week")}</b><br/>${pct(p.responded)} responded · ${p.total} applied${small}${note}`;
        },
      },
      xAxis: {
        type: "category",
        data: data.map((p) => fmtBucket(p.week, "day")),
        axisLabel: { color: c.ink2, fontSize: 11, hideOverlap: true },
        axisLine: { lineStyle: { color: c.line } },
        axisTick: { show: false },
      },
      yAxis: { type: "value", min: 0, max: 100, axisLabel: { color: c.ink2, fontSize: 11, formatter: "{value}%" }, splitLine: { lineStyle: { color: c.line } } },
      series: [
        { type: "line", data: data.map((p, i) => (p.maturing ? null : rate(i))), symbolSize: 7, lineStyle: { color: c.accent, width: 2 }, itemStyle: { color: c.accent } },
        {
          type: "line",
          data: data.map((p, i) => (p.maturing || i === lastMature ? rate(i) : null)),
          symbolSize: 7,
          lineStyle: { color: c.accent, width: 2, type: "dashed", opacity: 0.6 },
          itemStyle: { color: c.accent, opacity: 0.6 },
        },
      ],
    };
  }, [data, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  return <ReactECharts option={option} notMerge style={{ height: 220, width: "100%" }} opts={{ renderer: "svg" }} />;
}
