// Typed client for the FastAPI backend. Matches api/schemas.py.

export interface ReelSummary {
  id: string;
  title: string;
  author: string;
  genre: string;
  tags: string[];
  collections: string[];
  url: string;
  thumbnail_path: string | null;
  likes: number | null;
  views: number | null;
  comments: number | null;
  duration: number | null;
  timestamp: string | null;
  has_pdf: boolean;
  tokens_in: number;
  tokens_out: number;
  backend: string;   // claude-cli | api | local | local->claude-cli
  model: string;     // claude-sonnet-4-6 | reels-vision
  starred: boolean;
  read: boolean;
  archived: boolean;
}

export interface SavedView {
  name: string;
  filters: Record<string, string>;
}

export interface CategoryStat {
  genre: string;
  reels: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}
export interface Stats {
  total_reels: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  cost_note: string;
  categories: CategoryStat[];
  top_tags: [string, number][];
}

export interface Fact {
  text: string;
  timestamp: number | null;
  frame: number | null;
}

export interface ReelDetail extends ReelSummary {
  caption: string;
  hashtags: string[];
  summary: string;
  structured: Record<string, unknown>;
  facts: Fact[];
  transcript_text: string;
  transcript_language: string;
  transcript_translated: boolean;
  ocr_text: string[];
  video_path: string | null;
  pdf_path: string | null;
  tokens: { input?: number; output?: number; backend?: string; model?: string };
  annotation: { note?: string; starred?: boolean; read?: boolean; archived?: boolean };
}

export interface TopicReel {
  id: string;
  title: string;
  url: string;
  author: string;
  summary: string;
  thumbnail_path: string | null;
}
export interface TopicFact {
  reel_id: string;
  text: string;
  timestamp: number | null;
}
export interface Topic {
  name: string;
  reel_count: number;
  hashtags: string[];
  overview: string;
  reels: TopicReel[];
  facts: TopicFact[];
}
export interface Knowledge {
  total_reels: number;
  topics: Topic[];
}

export interface SearchHit {
  reel_id: string;
  title: string;
  url: string;
  kind: string;
  text: string;
  score: number;
  timestamp: number | null;
  /** the shelves the hit's reel sits on */
  collections: string[];
}

export interface Citation {
  reel_id: string;
  title: string;
  url: string;
  score: number;
  snippet: string;
  timestamp: number | null;
  /** the shelves the cited reel sits on */
  collections: string[];
}
export interface Answer {
  answer: string | null;
  citations: Citation[];
  note: string | null;
}

export interface TagRow {
  tag: string;
  count: number;
  /** which saved collections this tag appears in, most-used first */
  collections: { name: string; count: number }[];
}

export interface Candidate {
  id: string;
  url: string;
  caption: string;
  author: string;
  thumbnail_url: string;
  source: string;
  collection: string;
  score: number;
  why: string;
  state: "new" | "accepted" | "rejected" | "snoozed";
  found_on: string;
}
export interface DiscoverStatus {
  running: boolean;
  error: string;
  summary?: {
    found: number; kept: number; requests_used: number;
    request_budget: number; stopped_early: string; pending: number;
  };
}

export interface Source {
  name: string;
  url: string;
  type: string;
  enabled: boolean;
  limit: number;
  last_run?: string | null;
  reels?: number | null;
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

/** A named model the bench or the Compare tab can run. `installed` is false for
 *  a model that is in models.yaml but has not been pulled yet. */
export interface VisionProfile {
  name: string;
  kind: string;
  model: string;
  installed: boolean;
  notes: string;
}

export interface SyncSourceState {
  name: string;
  last_run: string | null;
  runs: number;
  current: number;
  new: number;
  ingested: number;
  failed: number;
  error: string;
}
export interface SyncReport {
  started_at?: string;
  finished_at?: string;
  summary?: { total_reels: number; with_errors: number; clean: number };
  // stage -> status ("ok" | "error" | "skip") -> count
  stages?: Record<string, Record<string, number>>;
}
export interface SyncStatus {
  running: boolean;
  backend: string;
  ingested: number;
  sources: number;
  error: string;
  /** true for an API-started sync *or* a CLI one (run.log written < 60s ago) */
  live?: boolean;
  log_age_sec?: number | null;
  stages?: string[];
  stage?: string;
  progress?: { done?: number; total?: number };
  log?: string[];
  source_state?: SyncSourceState[];
  report?: SyncReport;
}

export interface Variant {
  backend: string;
  model: string;
  summary: string;
  genre: string;
  tags: string[];
  structured: Record<string, unknown>;
  facts: { text: string; timestamp: number | null; frame: number | null }[];
  tokens: Record<string, number | string>;
  elapsed_s: number;
  frames: number;
  created_at: string;
}
export interface CompareResult {
  reel_id: string;
  variants: Record<string, Variant>;
  errors: Record<string, string>;
  /** claim-level diff, present when exactly 2 backends ran */
  diff: {
    a?: string;
    b?: string;
    shared?: { a: string; b: string; score: number }[];
    only_a?: string[];
    only_b?: string[];
  };
}
/** One stored variant, as the reader draws it (claim text only, no frames). */
export interface VariantMeta {
  name: string;
  backend: string;
  model: string;
  summary: string;
  tags: string[];
  structured: Record<string, unknown>;
  facts: string[];
  elapsed_s: number | null;
  cost_usd: number;
  created_at: string;
}
/** Read-only diff of variants ALREADY on disk — no model runs, no cost. */
export interface VariantsDiff {
  reel_id: string;
  available: string[];
  a: string;
  b: string;
  variants: Record<string, VariantMeta>;
  diff: {
    a?: string;
    b?: string;
    shared?: { a: string; b: string; score: number }[];
    only_a?: string[];
    only_b?: string[];
  };
}

export interface ScoreRow {
  backend: string;
  model: string;
  reels: number;
  avg_facts: number;
  avg_tags: number;
  avg_summary_chars: number;
  avg_seconds: number;
  avg_structured_fields: number;
  cost_usd: number;
  /** what one reel costs on this model — see docs/research/COSTS.md */
  cost_per_reel: number;
  /** variants that parsed but carry no claim at all */
  empty: number;
  /** answers scraped out of a reasoning trace rather than finished by the model */
  salvaged: number;
  empty_rate: number;
}
export interface Scoreboard {
  reels_compared: number;
  backends: ScoreRow[];
  avg_disagreement: number | null;
}
export interface BatchStatus {
  running: boolean;
  done: number;
  total: number;
  current: string;
  backends: string[];
  errors: string[];
}

export const api = {
  reels: () => get<ReelSummary[]>("/api/reels"),
  reel: (id: string) => get<ReelDetail>(`/api/reels/${id}`),
  similar: (id: string) => get<SearchHit[]>(`/api/reels/${id}/similar`),
  stats: () => get<Stats>("/api/stats"),
  knowledge: () => get<Knowledge>("/api/knowledge"),
  search: (q: string, k = 8) =>
    get<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}&k=${k}`),
  chat: async (question: string, history: { role: string; content: string }[] = []) => {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history, k: 8 }),
    });
    if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 200)}`);
    return (await r.json()) as Answer;
  },
  media: (id: string, kind: "thumbnail" | "video" | "pdf") =>
    `/api/media/${id}/${kind}`,
  tags: () => get<TagRow[]>("/api/tags"),
  discover: (state = "new") => get<Candidate[]>(`/api/discover?state=${state}`),
  discoverRun: (max_requests = 40) =>
    post<DiscoverStatus>("/api/discover/run", { max_requests, browser: "cookies.txt" }),
  discoverStatus: () => get<DiscoverStatus>("/api/discover/status"),
  discoverAction: (id: string, action: string) =>
    post<Record<string, unknown>>(`/api/discover/${id}/${action}`),
  sources: () => get<Source[]>("/api/sources"),
  addSource: (url: string, name = "", type = "collection") =>
    post<Source>("/api/sources", { url, name, type }),
  toggleSource: (name: string) => post<Source>(`/api/sources/${encodeURIComponent(name)}/toggle`),
  // any profile name from /api/profiles, not just the three original backends
  sync: (backend: string, only?: string[]) => post<SyncStatus>("/api/sync", { backend, only }),
  syncStatus: () => get<SyncStatus>("/api/sync/status"),
  profiles: () => get<VisionProfile[]>("/api/profiles"),
  // profile names, not the three fixed backends — any installed model can be an arm
  // read-only: diffs what is stored. `compare` below re-runs the models and costs money.
  variantsDiff: (id: string, a = "", b = "") =>
    get<VariantsDiff>(`/api/reels/${id}/variants/diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  compare: (id: string, backends: string[] = ["claude-cli", "local"]) =>
    post<CompareResult>(`/api/reels/${id}/compare`, { backends }),
  scoreboard: () => get<Scoreboard>("/api/compare/scoreboard"),
  compareBatch: (n: number, backends: string[] = ["claude-cli", "local"]) =>
    post<BatchStatus>("/api/compare/batch", { n, backends, only_missing: true }),
  compareStatus: () => get<BatchStatus>("/api/compare/status"),
  compareCancel: () => post<BatchStatus>("/api/compare/cancel"),
  annotate: (id: string, patch: Record<string, boolean | string>) =>
    post(`/api/reels/${id}/annotate`, patch),
  ingestUrl: (url: string) => post<{ accepted: string; note: string }>("/api/ingest", { url }),
  renameTag: (from: string, to: string) =>
    post<{ reels_updated: number }>("/api/tags/rename", { from, to }),
  views: () => get<SavedView[]>("/api/views"),
  saveView: (name: string, filters: Record<string, string>) =>
    post<SavedView[]>("/api/views", { name, filters }),
  deleteView: (name: string) => post<SavedView[]>(`/api/views/${encodeURIComponent(name)}/delete`),
};
