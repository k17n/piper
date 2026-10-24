export type Stage =
  | "applied"
  | "viewed"
  | "assessment"
  | "interview"
  | "offer"
  | "accepted"
  | "rejected"
  | "withdrawn"
  | "ghosted";

export type Source = "linkedin" | "ats" | "recruiter" | "direct" | "referral" | "other";
export type Category = "design" | "product" | "vc" | "other";
export type RangeKey = "30d" | "90d" | "180d" | "all" | "custom";

export interface Filters {
  range: RangeKey;
  from: string | null;
  to: string | null;
  sources: string[];
  stages: string[];
  categories: string[];
  q: string | null;
  include_ghosted: boolean;
}

export const DEFAULT_FILTERS: Filters = {
  range: "90d",
  from: null,
  to: null,
  sources: [],
  stages: [],
  categories: [],
  q: null,
  include_ghosted: true,
};

export function normalizeFilters(raw: Partial<Filters> | undefined): Filters {
  const f = { ...DEFAULT_FILTERS, ...(raw ?? {}) };
  return {
    ...f,
    from: f.range === "custom" ? f.from || null : null,
    to: f.range === "custom" ? f.to || null : null,
    sources: [...f.sources].sort(),
    stages: [...f.stages].sort(),
    categories: [...(f.categories ?? [])].sort(),
    q: f.q?.trim() || null,
  };
}

export function sameFilters(a: Filters, b: Filters): boolean {
  return JSON.stringify(normalizeFilters(a)) === JSON.stringify(normalizeFilters(b));
}

export function filterParams(f: Filters): URLSearchParams {
  const p = new URLSearchParams();
  p.set("range", f.range);
  if (f.range === "custom") {
    if (f.from) p.set("from", f.from);
    if (f.to) p.set("to", f.to);
  }
  f.sources.forEach((s) => p.append("sources", s));
  f.stages.forEach((s) => p.append("stages", s));
  f.categories.forEach((c) => p.append("categories", c));
  if (f.q) p.set("q", f.q);
  if (!f.include_ghosted) p.set("include_ghosted", "false");
  return p;
}

export interface Meta {
  data_since: string | null;
  last_sync_at: string | null;
  provider: string;
  model: string;
  gmail_connected: boolean;
  ghost_days: number;
  sync_interval_hours: number;
}

export interface SankeyNode {
  name: string;
  kind: string;
}
export interface SankeyLink {
  source: string;
  target: string;
  value: number;
  application_ids: number[];
}
export interface SankeyData {
  nodes: SankeyNode[];
  links: SankeyLink[];
}

export interface Stats {
  total: number;
  active: number;
  response_rate: number;
  interview_rate: number;
  offer_rate: number;
  median_days_to_first_response: number | null;
  by_stage: Record<string, number>;
}

export interface Application {
  id: number;
  company: string;
  role: string;
  source: Source;
  stage: Stage;
  current_stage: Stage;
  manual_override: boolean;
  category: Category;
  category_manual: boolean;
  first_seen: string;
  last_event_at: string;
  notes: string;
  events: AppEvent[];
}

export interface AppEvent {
  stage: Stage;
  occurred_at: string;
  email_id: string | null;
  subject: string | null;
  gmail_url: string | null;
  note: string;
}

export interface ThreadMessage {
  id: string;
  from: string;
  to: string;
  date: string;
  outgoing: boolean;
  body: string;
  highlight: boolean;
}

export interface EmailThread {
  subject: string;
  gmail_url: string;
  messages: ThreadMessage[];
}

export interface ReviewCandidate {
  id: number;
  role: string;
  stage: Stage;
  first_seen: string;
}

export interface ReviewItem {
  id: number;
  reason: string;
  extracted: Record<string, unknown> | null;
  candidates: ReviewCandidate[];
  email: {
    id: string;
    from: string;
    subject: string;
    received_at: string;
    snippet: string;
    body: string;
    gmail_url: string | null;
  } | null;
}

export interface SavedView {
  id: number;
  name: string;
  filters: Filters;
  is_default: boolean;
  updated_at: string;
}

export interface SyncStatus {
  state: "idle" | "running" | "done" | "error";
  phase?: string;
  current?: number;
  total?: number;
  model?: string;
  message?: string;
  new?: number;
  counts?: Record<string, number>;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new Error(message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  meta: () => http<Meta>("/api/meta"),
  sankey: (f: Filters) => http<SankeyData>(`/api/sankey?${filterParams(f)}`),
  stats: (f: Filters) => http<Stats>(`/api/stats?${filterParams(f)}`),
  applications: (f: Filters, ids?: number[]) => {
    const p = filterParams(f);
    ids?.forEach((id) => p.append("ids", String(id)));
    return http<Application[]>(`/api/applications?${p}`);
  },
  patchApplication: (
    id: number,
    body: {
      stage?: Stage;
      notes?: string;
      role?: string;
      manual_override?: boolean;
      category?: Category;
      category_auto?: boolean;
    },
  ) =>
    http<Application>(`/api/applications/${id}`, { method: "PATCH", body: json(body) }),
  createApplication: (body: {
    company: string;
    role?: string;
    source: Source;
    stage: Stage;
    applied_on: string;
    notes?: string;
  }) => http<Application>("/api/applications", { method: "POST", body: json(body) }),
  logUpdate: (id: number, body: { stage: Stage; occurred_on: string; note?: string }) =>
    http<Application>(`/api/applications/${id}/events`, { method: "POST", body: json(body) }),
  deleteApplication: (id: number) => http<void>(`/api/applications/${id}`, { method: "DELETE" }),
  thread: (emailId: string) => http<EmailThread>(`/api/emails/${emailId}/thread`),
  reviewQueue: () => http<ReviewItem[]>("/api/review-queue"),
  resolveReview: (id: number, body: Record<string, unknown>) =>
    http(`/api/review-queue/${id}/resolve`, { method: "POST", body: json(body) }),
  views: () => http<SavedView[]>("/api/views"),
  createView: (body: { name: string; filters: Filters; is_default?: boolean }) =>
    http<SavedView>("/api/views", { method: "POST", body: json(body) }),
  patchView: (id: number, body: { name?: string; filters?: Filters; is_default?: boolean }) =>
    http<SavedView>(`/api/views/${id}`, { method: "PATCH", body: json(body) }),
  deleteView: (id: number) => http<void>(`/api/views/${id}`, { method: "DELETE" }),
  startSync: () => http<{ started: boolean; status: SyncStatus }>("/api/sync", { method: "POST" }),
};
