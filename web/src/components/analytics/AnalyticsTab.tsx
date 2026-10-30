import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, type Filters, type Granularity } from "../../lib/api";
import type { Selection } from "../SankeyChart";
import { Empty } from "../ui";
import { defaultGranularity } from "./format";
import { AppsOverTime } from "./AppsOverTime";
import { Section, Segmented } from "./Section";
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

  return (
    <div className="anim-fade-up flex flex-col gap-4">
      <SummaryTiles s={data?.summary} />
      {data && (
        <Section
          title="Applications over time"
          hint={data.summary.total < 7 ? "The 7-day average appears once there are 7 applications" : undefined}
          right={
            <Segmented
              value={granularity}
              onChange={setChosen}
              options={[
                { value: "day", label: "Day" },
                { value: "week", label: "Week" },
                { value: "month", label: "Month" },
              ]}
            />
          }
        >
          <AppsOverTime data={data.series} granularity={granularity} showAverage={data.summary.total >= 7} dark={dark} onSelect={onSelect} />
        </Section>
      )}
      {/* widgets: keep this line, new sections go above it */}
    </div>
  );
}
