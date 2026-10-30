import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, type Filters, type Granularity } from "../../lib/api";
import type { Selection } from "../SankeyChart";
import { Empty } from "../ui";
import { defaultGranularity } from "./format";
import { SummaryTiles } from "./SummaryTiles";

export function AnalyticsTab({ filters, dark, onSelect }: { filters: Filters; dark: boolean; onSelect: (s: Selection) => void }) {
  const [chosen, setChosen] = useState<Granularity | null>(null);
  const granularity = chosen ?? defaultGranularity(filters);
  const { data } = useQuery({
    queryKey: ["analytics", filters, granularity],
    queryFn: () => api.analytics(filters, granularity),
    placeholderData: keepPreviousData,
  });

  if (data && data.summary.total === 0) {
    return (
      <div className="card">
        <Empty title="No applications in this range">
          Widen the date range, run a sync, or try sample data with <code>piper seed</code>.
        </Empty>
      </div>
    );
  }

  void [dark, onSelect, setChosen]; // used by the widgets added in the following tasks
  return (
    <div className="anim-fade-up flex flex-col gap-4">
      <SummaryTiles s={data?.summary} />
      {/* widgets: keep this line, new sections go above it */}
    </div>
  );
}
