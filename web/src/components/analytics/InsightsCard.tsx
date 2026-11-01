import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Filters } from "../../lib/api";
import { Button } from "../ui";
import { Section } from "./Section";

const POLL_MS = 3000;

/** Placeholder lines shown while the summary loads or is being written. */
function Skeleton() {
  return (
    <div className="flex flex-col gap-2" role="status" aria-label="Writing a summary">
      <div className="h-3 w-full animate-pulse rounded bg-surface-2" />
      <div className="h-3 w-11/12 animate-pulse rounded bg-surface-2" />
      <div className="h-3 w-4/5 animate-pulse rounded bg-surface-2" />
      <div className="h-3 w-2/3 animate-pulse rounded bg-surface-2" />
    </div>
  );
}

/** A short written summary of the view, from the local model. While it is being written a skeleton
 * is shown; if it cannot be written, a short note says so. */
export function InsightsCard({ filters }: { filters: Filters }) {
  const queryClient = useQueryClient();
  const queryKey = ["analytics", "summary", filters]; // starts with "analytics", so data changes refresh it
  const { data, isError } = useQuery({
    queryKey,
    queryFn: () => api.analyticsSummary(filters),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? POLL_MS : false),
  });
  const refresh = useMutation({
    mutationFn: () => api.refreshAnalyticsSummary(filters),
    onSuccess: (result) => queryClient.setQueryData(queryKey, result),
  });

  if (!data && isError) {
    return (
      <Section title="Insights">
        <p className="text-sm text-muted">Could not load the summary.</p>
      </Section>
    );
  }
  if (!data) {
    return (
      <Section title="Insights">
        <Skeleton />
      </Section>
    );
  }
  const action =
    data.status === "ready" ? (
      <Button
        onClick={() => refresh.mutate()}
        disabled={refresh.isPending}
        title="Write it again with different wording"
        className="h-7 px-2"
      >
        {/* Button takes no aria-label prop (ui.tsx is out of scope), so the glyph carries the name */}
        <span role="img" aria-label="Write the summary again">
          ↻
        </span>
      </Button>
    ) : undefined;
  return (
    <Section
      title="Insights"
      hint={data.status === "ready" ? "Written by your local model from the numbers on this page" : undefined}
      right={action}
    >
      {data.status === "ready" && (
        <div className="flex flex-col gap-2">
          <p className="text-sm leading-relaxed text-ink">{data.text}</p>
          {refresh.isError && <p className="text-xs text-muted">Could not ask for a new version.</p>}
        </div>
      )}
      {data.status === "insufficient_data" && (
        <p className="text-sm text-ink-2">A summary appears once there are at least 10 applications in this view.</p>
      )}
      {data.status === "pending" && <Skeleton />}
      {data.status === "fallback" && (
        <p className="text-sm text-muted">A summary could not be written just now. It will be retried automatically.</p>
      )}
    </Section>
  );
}
