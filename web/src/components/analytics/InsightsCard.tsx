import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Filters } from "../../lib/api";
import { Button } from "../ui";
import { Section } from "./Section";

const POLL_MS = 3000;

function Facts({ facts }: { facts: string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
      {facts.map((f) => (
        <li key={f}>{f}</li>
      ))}
    </ul>
  );
}

/** A short written summary of the view, from the local model. While it is being written, or if it
 * cannot be, the plain numbers it is based on are shown instead. */
export function InsightsCard({ filters }: { filters: Filters }) {
  const queryClient = useQueryClient();
  const queryKey = ["analytics", "summary", filters]; // starts with "analytics", so data changes refresh it
  const { data } = useQuery({
    queryKey,
    queryFn: () => api.analyticsSummary(filters),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? POLL_MS : false),
  });
  const refresh = useMutation({
    mutationFn: () => api.refreshAnalyticsSummary(filters),
    onSuccess: (result) => queryClient.setQueryData(queryKey, result),
  });

  if (!data) {
    return (
      <Section title="Insights">
        <div className="h-12" />
      </Section>
    );
  }
  const action =
    data.status === "ready" ? (
      <Button onClick={() => refresh.mutate()} title="Write it again with different wording" className="h-7 px-2">
        ↻
      </Button>
    ) : undefined;
  return (
    <Section
      title="Insights"
      hint={data.status === "ready" ? "Written by your local model from the numbers on this page" : undefined}
      right={action}
    >
      {data.status === "ready" && <p className="text-sm leading-relaxed text-ink">{data.text}</p>}
      {data.status === "insufficient_data" && (
        <p className="text-sm text-ink-2">A summary appears once there are at least 10 applications in this view.</p>
      )}
      {data.status === "pending" && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted">Writing a summary…</p>
          <Facts facts={data.facts} />
        </div>
      )}
      {data.status === "fallback" && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted">A summary could not be written just now, so here are the numbers.</p>
          <Facts facts={data.facts} />
        </div>
      )}
    </Section>
  );
}
