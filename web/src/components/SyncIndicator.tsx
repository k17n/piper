import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Meta, type SyncStatus } from "../lib/api";
import { Button } from "./ui";

function describe(s: SyncStatus): string {
  if (s.state === "error") return s.message ?? "Sync failed";
  if (s.state === "done") return `Synced · ${s.new ?? 0} new email${s.new === 1 ? "" : "s"}`;
  if (s.phase === "extracting" || s.phase === "fetching") {
    const verb = s.phase === "extracting" ? "Extracting" : "Fetching";
    return `${verb} ${s.current}/${s.total}${s.model ? ` · ${s.model}` : ""}`;
  }
  return s.message ?? "Syncing…";
}

function ago(iso: string | null): string {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(`${iso}Z`).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
}

export function SyncIndicator({ meta }: { meta: Meta | undefined }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<SyncStatus>({ state: "idle" });
  const prev = useRef<SyncStatus["state"]>("idle");

  useEffect(() => {
    const es = new EventSource("/api/sync/stream");
    es.onmessage = (e) => {
      const s = JSON.parse(e.data) as SyncStatus;
      setStatus(s);
      if (prev.current === "running" && s.state !== "running") qc.invalidateQueries();
      prev.current = s.state;
    };
    return () => es.close();
  }, [qc]);

  const running = status.state === "running";
  const progress = running && status.total ? (status.current ?? 0) / status.total : null;

  return (
    <div className="flex flex-col gap-2">
      <Button variant="primary" className="justify-center" disabled={running} onClick={() => api.startSync()}>
        {running ? "Syncing…" : "Sync now"}
      </Button>
      <div className="h-1 overflow-hidden rounded-full bg-surface-2" aria-hidden={!running}>
        {running && (
          <div
            className={progress == null ? "h-full w-1/3 animate-pulse rounded-full bg-accent" : "h-full rounded-full bg-accent transition-[width] duration-300"}
            style={progress == null ? undefined : { width: `${Math.max(4, progress * 100)}%` }}
          />
        )}
      </div>
      <div className={`text-xs leading-snug ${status.state === "error" ? "text-[#d03b3b]" : "text-muted"}`} title={status.message}>
        {status.state === "idle" ? `Last sync ${ago(meta?.last_sync_at ?? null)}` : describe(status)}
      </div>
      {meta && !meta.gmail_connected && status.state !== "running" && (
        <div className="text-xs leading-snug text-muted">Gmail not connected. Sync opens Google sign-in (see README).</div>
      )}
    </div>
  );
}
