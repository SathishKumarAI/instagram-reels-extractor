import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type SearchHit } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search as SearchIcon } from "lucide-react";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const nav = useNavigate();
  const box = useRef<HTMLInputElement>(null);

  useEffect(() => { box.current?.focus(); }, []);

  useEffect(() => {
    if (!q.trim()) { setHits([]); setState("idle"); return; }
    setState("loading");
    const t = setTimeout(() => {
      api.search(q, 20)
        .then((h) => { setHits(h); setState("done"); })
        .catch(() => setState("error"));
    }, 300); // debounce
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="p-6">
      <h1 className="mb-1 text-2xl font-bold text-text">Search</h1>
      <p className="mb-4 text-sm text-overlay0">Semantic search across captions, transcripts, summaries & facts.</p>

      <div className="relative mb-5 max-w-2xl">
        <SearchIcon size={16} className="absolute left-3 top-3 text-overlay0" />
        <Input ref={box} value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Ask anything — e.g. 'PhD interview tips', 'best RAG frameworks'…"
          className="pl-9" />
      </div>

      {state === "loading" && <p className="text-sm text-overlay0">Searching…</p>}
      {state === "error" && <p className="text-sm text-red">Search index not ready — run extraction first.</p>}
      {state === "done" && hits.length === 0 && <p className="text-sm text-overlay0">No matches for “{q}”.</p>}

      <div className="max-w-2xl space-y-2">
        {hits.map((h, i) => (
          <button key={i} onClick={() => nav(`/reels?focus=${h.reel_id}`)}
            className="block w-full rounded-lg border border-surface0 p-3 text-left hover:border-mauve">
            <div className="mb-1 flex items-center gap-2">
              <Badge variant="genre">{h.kind}{h.timestamp != null ? ` @${Math.round(h.timestamp)}s` : ""}</Badge>
              <span className="font-medium text-text">{h.title}</span>
              <span className="ml-auto text-xs text-overlay0">{h.score.toFixed(2)}</span>
            </div>
            <p className="line-clamp-2 text-sm text-subtext">{h.text}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
