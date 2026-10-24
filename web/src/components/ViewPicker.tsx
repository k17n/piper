import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, sameFilters, type Filters, type SavedView } from "../lib/api";
import { Button, Popover, cx } from "./ui";

interface Props {
  views: SavedView[];
  viewId: number | null;
  filters: Filters;
  onOpen: (view: SavedView) => void;
  onDetach: () => void;
  onSaved: (view: SavedView) => void;
}

export function ViewPicker({ views, viewId, filters, onOpen, onDetach, onSaved }: Props) {
  const qc = useQueryClient();
  const active = views.find((v) => v.id === viewId) ?? null;
  const modified = active != null && !sameFilters(active.filters, filters);
  const [newName, setNewName] = useState("");
  const [renaming, setRenaming] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => qc.invalidateQueries({ queryKey: ["views"] });
  const onError = (e: Error) => setError(e.message);

  const create = useMutation({
    mutationFn: (name: string) => api.createView({ name, filters }),
    onSuccess: (v) => {
      setNewName("");
      setError(null);
      refresh();
      onSaved(v);
    },
    onError,
  });
  const patch = useMutation({
    mutationFn: ({ id, ...body }: { id: number; name?: string; filters?: Filters; is_default?: boolean }) =>
      api.patchView(id, body),
    onSuccess: () => {
      setRenaming(null);
      setError(null);
      refresh();
    },
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteView(id),
    onSuccess: (_d, id) => {
      if (id === viewId) onDetach();
      refresh();
    },
    onError,
  });

  return (
    <Popover
      width={320}
      trigger={(open, toggle) => (
        <button
          onClick={toggle}
          className={cx(
            "flex h-8 max-w-56 items-center gap-2 rounded-lg border border-line px-3 text-sm font-medium transition-colors hover:bg-surface-2",
            open && "bg-surface-2",
          )}
        >
          <span className="text-muted">View</span>
          <span className="truncate text-ink">{active ? active.name : "Unsaved"}</span>
          {modified && <span title="Filters changed since this view was saved" className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />}
          <span className="text-muted">▾</span>
        </button>
      )}
    >
      {(close) => (
        <div className="flex flex-col gap-1 text-sm">
          {views.length === 0 && <div className="px-2 py-2 text-ink-2">No saved views yet.</div>}
          {views.map((v) => (
            <div key={v.id} className={cx("group flex items-center gap-1 rounded-lg px-1", v.id === viewId && "bg-surface-2")}>
              {renaming === v.id ? (
                <form
                  className="flex flex-1 gap-1 py-1"
                  onSubmit={(e) => {
                    e.preventDefault();
                    patch.mutate({ id: v.id, name: renameValue });
                  }}
                >
                  <input autoFocus value={renameValue} onChange={(e) => setRenameValue(e.target.value)} className="h-7 flex-1 px-2" />
                  <Button type="submit" variant="outline" className="h-7 px-2">
                    Save
                  </Button>
                </form>
              ) : (
                <>
                  <button
                    className="flex-1 truncate py-1.5 pl-1 text-left text-ink"
                    onClick={() => {
                      onOpen(v);
                      close();
                    }}
                  >
                    {v.name}
                  </button>
                  <button
                    title={v.is_default ? "Default view (loads on startup)" : "Set as default"}
                    onClick={() => patch.mutate({ id: v.id, is_default: !v.is_default })}
                    className={cx("px-1 text-base", v.is_default ? "text-[#eda100]" : "text-muted opacity-0 group-hover:opacity-100")}
                  >
                    {v.is_default ? "★" : "☆"}
                  </button>
                  <button
                    title="Rename"
                    onClick={() => {
                      setRenaming(v.id);
                      setRenameValue(v.name);
                    }}
                    className="px-1 text-muted opacity-0 hover:text-ink group-hover:opacity-100"
                  >
                    ✎
                  </button>
                  <button
                    title="Delete"
                    onClick={() => remove.mutate(v.id)}
                    className="px-1 text-muted opacity-0 hover:text-[#d03b3b] group-hover:opacity-100"
                  >
                    ✕
                  </button>
                </>
              )}
            </div>
          ))}

          <div className="my-1 border-t border-line" />
          {active && modified && (
            <Button
              variant="outline"
              className="justify-center"
              onClick={() => patch.mutate({ id: active.id, filters })}
            >
              Save changes to “{active.name}”
            </Button>
          )}
          <form
            className="flex gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              if (newName.trim()) create.mutate(newName.trim());
            }}
          >
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Save current filters as…"
              className="h-8 flex-1 px-2 text-sm"
            />
            <Button type="submit" variant="primary" disabled={!newName.trim()}>
              Save
            </Button>
          </form>
          {error && <div className="px-1 text-xs text-[#d03b3b]">{error}</div>}
        </div>
      )}
    </Popover>
  );
}
