import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { Analytics } from "../../lib/api";
import { alpha, categoryAxis, chartColors, reducedMotion, tip, tooltipStyle, valueAxis } from "./chartTheme";
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
    const fade = {
      type: "linear",
      x: 0,
      y: 0,
      x2: 0,
      y2: 1,
      colorStops: [
        { offset: 0, color: alpha(c.accent, 0.28) },
        { offset: 1, color: alpha(c.accent, 0) },
      ],
    };
    return {
      animation: !reducedMotion(),
      animationDuration: 500,
      animationEasing: "cubicOut",
      grid: { left: 36, right: 8, top: 8, bottom: 24 },
      tooltip: {
        trigger: "axis",
        ...tooltipStyle(c),
        formatter: (params: { dataIndex: number }[]) => {
          const p = data[params[0].dataIndex];
          const small = p.total < 5 ? " (small sample)" : "";
          return tip(fmtBucket(p.week, "week"), [{ label: "Responded", value: pct(p.responded) }, { label: "Applied", value: `${p.total}${small}` }], p.maturing ? "still maturing" : "");
        },
      },
      xAxis: categoryAxis(c, data.map((p) => fmtBucket(p.week, "day"))),
      yAxis: valueAxis(c, { min: 0, max: 100, formatter: "{value}%" }),
      series: [
        {
          type: "line",
          smooth: true,
          data: data.map((p, i) => (p.maturing ? null : rate(i))),
          symbolSize: 6,
          lineStyle: { color: c.accent, width: 2 },
          itemStyle: { color: c.accent, borderColor: c.surface, borderWidth: 2 },
          areaStyle: { color: fade },
        },
        {
          type: "line",
          smooth: true,
          data: data.map((p, i) => (p.maturing || i === lastMature ? rate(i) : null)),
          symbolSize: 6,
          lineStyle: { color: c.accent, width: 2, type: "dashed", opacity: 0.6 },
          itemStyle: { color: c.accent, opacity: 0.6 },
        },
      ],
    };
  }, [data, dark]); // eslint-disable-line react-hooks/exhaustive-deps

  return <ReactECharts option={option} notMerge style={{ height: 220, width: "100%" }} opts={{ renderer: "svg" }} />;
}
