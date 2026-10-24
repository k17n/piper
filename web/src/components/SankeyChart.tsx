import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { SankeyData } from "../lib/api";
import { SOURCE_COLOR, stageColor } from "../lib/stages";

export interface Selection {
  title: string;
  ids: number[];
}

function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function SankeyChart({ data, dark, onSelect }: { data: SankeyData; dark: boolean; onSelect: (s: Selection) => void }) {
  const { option, nodeIds } = useMemo(() => {
    const ink = cssVar("--text");
    const ink2 = cssVar("--text-2");
    const surface = cssVar("--surface");
    const border = cssVar("--border");

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
      animationDuration: 700,
      animationEasing: "cubicOut",
      tooltip: {
        trigger: "item",
        backgroundColor: surface,
        borderColor: border,
        textStyle: { color: ink, fontSize: 12 },
        extraCssText: "border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);",
        formatter: (p: { dataType: string; data: { source: string; target: string; value: number; name: string } }) => {
          if (p.dataType === "edge") {
            const { source, target, value } = p.data;
            const share = Math.round((value / (nodeTotal(source) || 1)) * 100);
            return `<b>${source} → ${target}</b><br/>${value} application${value === 1 ? "" : "s"} · ${share}% of ${source}`;
          }
          const name = p.data.name;
          return `<b>${name}</b><br/>${nodeTotal(name)} application${nodeTotal(name) === 1 ? "" : "s"}`;
        },
      },
      series: [
        {
          type: "sankey",
          left: 8,
          right: 120,
          top: 12,
          bottom: 12,
          nodeWidth: 12,
          nodeGap: 14,
          nodeAlign: "left",
          layoutIterations: 64,
          draggable: false,
          emphasis: { focus: "adjacency" },
          data: data.nodes.map((n) => ({
            name: n.name,
            itemStyle: {
              color: n.kind === "source" ? SOURCE_COLOR : stageColor(n.kind),
              borderColor: surface,
              borderWidth: 1,
              borderRadius: 3,
            },
          })),
          links: data.links.map((l) => ({ ...l })),
          lineStyle: { color: "gradient", curveness: 0.5, opacity: dark ? 0.38 : 0.32 },
          label: {
            color: ink,
            fontSize: 12,
            formatter: (p: { name: string }) => `{name|${p.name}}  {count|${nodeTotal(p.name)}}`,
            rich: {
              name: { color: ink, fontSize: 12, fontWeight: 500 },
              count: { color: ink2, fontSize: 12 },
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
      style={{ height: Math.max(380, data.nodes.length * 34), width: "100%" }}
      opts={{ renderer: "svg" }}
    />
  );
}
