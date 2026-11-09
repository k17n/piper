import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { SankeyData } from "../lib/api";
import { SOURCE_COLOR, stageColor } from "../lib/stages";
import { chartColors, MONO, tip, tooltipStyle } from "./analytics/chartTheme";

export interface Selection {
  title: string;
  ids: number[];
}

// Filter bar, KPI cards and the funnel card's header + padding sit above/around the chart.
const CHROME_ABOVE_CHART = 300;

function useViewportHeight() {
  const [height, setHeight] = useState(() => window.innerHeight);
  useEffect(() => {
    const onResize = () => setHeight(window.innerHeight);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return height;
}

export function SankeyChart({ data, dark, onSelect }: { data: SankeyData; dark: boolean; onSelect: (s: Selection) => void }) {
  // Fill the window's remaining height so the funnel isn't squashed into the top half of the screen.
  const viewportHeight = useViewportHeight();
  const { option, nodeIds } = useMemo(() => {
    const c = chartColors();

    const inflow = new Map<string, number>();
    const outflow = new Map<string, number>();
    const nodeIds = new Map<string, Set<number>>();
    for (const l of data.links) {
      inflow.set(l.target, (inflow.get(l.target) ?? 0) + l.value);
      outflow.set(l.source, (outflow.get(l.source) ?? 0) + l.value);
      for (const end of [l.source, l.target]) {
        if (!nodeIds.has(end)) nodeIds.set(end, new Set());
      }
      // a node's applications are those flowing into it (or out of it, for source nodes)
      l.application_ids.forEach((id) => nodeIds.get(l.target)!.add(id));
    }
    for (const l of data.links) {
      if (!inflow.has(l.source)) l.application_ids.forEach((id) => nodeIds.get(l.source)!.add(id));
    }
    const nodeTotal = (name: string) => Math.max(inflow.get(name) ?? 0, outflow.get(name) ?? 0);

    const option = {
      animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      animationDuration: 600,
      animationEasing: "cubicOut",
      tooltip: {
        trigger: "item",
        ...tooltipStyle(c),
        formatter: (p: { dataType: string; data: { source: string; target: string; value: number; name: string } }) => {
          if (p.dataType === "edge") {
            const { source, target, value } = p.data;
            const share = Math.round((value / (nodeTotal(source) || 1)) * 100);
            return tip(`${source} → ${target}`, [{ label: `${value} application${value === 1 ? "" : "s"}`, value: `${share}% of ${source}` }]);
          }
          const n = nodeTotal(p.data.name);
          return tip(p.data.name, [{ label: `${n} application${n === 1 ? "" : "s"}` }]);
        },
      },
      series: [
        {
          type: "sankey",
          left: 8,
          right: 120,
          top: 12,
          bottom: 12,
          nodeWidth: 8,
          nodeGap: 12,
          nodeAlign: "left",
          layoutIterations: 64,
          draggable: false,
          emphasis: { focus: "adjacency", lineStyle: { opacity: 0.55 } },
          data: data.nodes.map((n) => ({
            name: n.name,
            itemStyle: {
              color: n.kind === "source" ? SOURCE_COLOR : stageColor(n.kind),
              borderRadius: 2,
            },
          })),
          links: data.links.map((l) => ({ ...l })),
          lineStyle: { color: "gradient", curveness: 0.5, opacity: dark ? 0.3 : 0.24 },
          label: {
            color: c.ink,
            fontSize: 12,
            formatter: (p: { name: string }) => `{name|${p.name}}  {count|${nodeTotal(p.name)}}`,
            rich: {
              name: { color: c.ink, fontSize: 12, fontWeight: 500 },
              count: { color: c.muted, fontSize: 11, fontFamily: MONO },
            },
          },
        },
      ],
    };
    return { option, nodeIds };
  }, [data, dark]);

  const onEvents = useMemo(
    () => ({
      click: (p: { dataType: string; data: { source: string; target: string; name: string; application_ids?: number[] } }) => {
        if (p.dataType === "edge") {
          onSelect({ title: `${p.data.source} → ${p.data.target}`, ids: p.data.application_ids ?? [] });
        } else if (p.dataType === "node") {
          onSelect({ title: p.data.name, ids: [...(nodeIds.get(p.data.name) ?? [])] });
        }
      },
    }),
    [nodeIds, onSelect],
  );

  return (
    <ReactECharts
      option={option}
      onEvents={onEvents}
      notMerge
      style={{ height: Math.max(380, data.nodes.length * 34, viewportHeight - CHROME_ABOVE_CHART), width: "100%" }}
      opts={{ renderer: "svg" }}
    />
  );
}
