// Typed client for the FastAPI backend. Matches api/schemas.py.

export interface ReelSummary {
  id: string;
  title: string;
  author: string;
  genre: string;
  url: string;
  thumbnail_path: string | null;
  likes: number | null;
  views: number | null;
  comments: number | null;
  duration: number | null;
  has_pdf: boolean;
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
  ocr_text: string[];
  video_path: string | null;
  pdf_path: string | null;
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

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

export const api = {
  reels: () => get<ReelSummary[]>("/api/reels"),
  reel: (id: string) => get<ReelDetail>(`/api/reels/${id}`),
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
};
