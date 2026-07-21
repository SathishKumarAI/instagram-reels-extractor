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
  backend: string;
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
  tokens: { input?: number; output?: number };
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
}

export interface Citation {
  reel_id: string;
  title: string;
  url: string;
  score: number;
  snippet: string;
  timestamp: number | null;
}
export interface Answer {
  answer: string | null;
  citations: Citation[];
  note: string | null;
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

export type SyncBackend = "claude-cli" | "api" | "local";
export interface SyncStatus {
  running: boolean;
  backend: string;
  ingested: number;
  sources: number;
  error: string;
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
  sources: () => get<Source[]>("/api/sources"),
  addSource: (url: string, name = "", type = "collection") =>
    post<Source>("/api/sources", { url, name, type }),
  toggleSource: (name: string) => post<Source>(`/api/sources/${encodeURIComponent(name)}/toggle`),
  sync: (backend: SyncBackend, only?: string[]) => post<SyncStatus>("/api/sync", { backend, only }),
  syncStatus: () => get<SyncStatus>("/api/sync/status"),
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
