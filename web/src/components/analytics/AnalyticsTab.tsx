import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, type Category, type Filters, type Granularity } from "../../lib/api";
import { CATEGORY_COLOR, SENIORITY_LABEL, categoryLabel, sourceLabel, stageColor, stageLabel } from "../../lib/stages";
import type { Selection } from "../SankeyChart";
import { Empty } from "../ui";
import { WEEKDAYS, defaultGranularity } from "./format";
import { Heatmap } from "./Heatmap";
import { AppsOverTime } from "./AppsOverTime";
import { CategoryOverTime } from "./CategoryOverTime";
import { Cohorts } from "./Cohorts";
import { ConversionTable } from "./ConversionTable";
import { MixBars } from "./MixBars";
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
      {data && (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Role type" hint="What kind of roles you apply to">
              <MixBars
                title="Role type"
                onSelect={onSelect}
                items={data.mix.category.map((g) => ({ ...g, label: categoryLabel(g.key), color: CATEGORY_COLOR[g.key as Category] }))}
              />
            </Section>
            <Section title="Source" hint="Where applications come from">
              <MixBars title="Source" onSelect={onSelect} items={data.mix.source.map((g) => ({ ...g, label: sourceLabel(g.key) }))} />
            </Section>
            <Section title="Seniority" hint="Read from the role title">
              <MixBars title="Seniority" onSelect={onSelect} items={data.mix.seniority.map((g) => ({ ...g, label: SENIORITY_LABEL[g.key] ?? g.key }))} />
            </Section>
            <Section title="Top role titles" hint="Levels removed: “Sr. Designer” and “Designer II” count together">
              <MixBars
                title="Role"
                onSelect={onSelect}
                items={data.top_titles.map((t) => ({ key: t.title, label: t.title.replace(/\b\w/g, (m) => m.toUpperCase()), count: t.count, ids: t.ids }))}
                total={data.summary.total}
                empty="No role titles yet"
              />
            </Section>
            <Section title="Companies applied to more than once">
              <MixBars
                title="Company"
                onSelect={onSelect}
                items={data.top_companies.map((c) => ({ key: c.company, label: `${c.company} · ${stageLabel(c.stage)}`, count: c.count, ids: c.ids }))}
                total={data.summary.total}
                empty="No company has more than one application"
              />
            </Section>
          </div>
          {data.category_by_week.length >= 3 && (
            <Section title="Role type over time" hint="Share of each week’s applications">
              <CategoryOverTime data={data.category_by_week} dark={dark} />
            </Section>
          )}
        </>
      )}
      {data && (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <Section title="Activity" hint="Each square is a day; darker means more applications">
            <Heatmap days={data.daily} onSelect={onSelect} />
          </Section>
          <Section title="Day of the week">
            <MixBars
              title="Applied on"
              onSelect={onSelect}
              items={data.weekday.map((w) => ({ key: String(w.day), label: WEEKDAYS[w.day], count: w.count, ids: w.ids }))}
            />
          </Section>
        </div>
      )}
      {data && (
        <>
          <Section title="What works" hint="Share of applications that got a reply or an interview, with how many that is">
            <ConversionTable conversion={data.conversion} />
          </Section>
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Response rate by week applied" hint="Dashed weeks may still be waiting for replies">
              {data.summary.total >= 7 ? (
                <Cohorts data={data.cohorts} dark={dark} />
              ) : (
                <div className="py-6 text-center text-sm text-muted">Needs a week of data</div>
              )}
            </Section>
            <Section
              title="Time to first reply"
              hint={data.response_time.median == null ? "No replies yet" : `Median ${data.response_time.median.toFixed(1)} days`}
            >
              <MixBars title="Replied in" items={data.response_time.buckets.map((b) => ({ ...b, label: b.key }))} empty="No replies yet" />
            </Section>
            <Section title="Open applications by days since last update" hint="Quiet ones become “ghosted” after the ghost limit">
              <MixBars title="Quiet for" onSelect={onSelect} items={data.open_by_age.map((b) => ({ ...b, label: b.key }))} empty="No open applications" />
            </Section>
            <Section title="Outcomes">
              <MixBars
                title="Outcome"
                onSelect={onSelect}
                items={data.outcomes.map((o) => ({ ...o, label: stageLabel(o.key), color: o.key === "active" ? undefined : stageColor(o.key) }))}
              />
            </Section>
          </div>
        </>
      )}
    </div>
  );
}
