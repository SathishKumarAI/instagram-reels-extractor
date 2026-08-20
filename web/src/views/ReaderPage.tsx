import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type ReelDetail, type ReelSummary, type VariantsDiff } from "@/lib/api";
import { ExternalLink, Hash, Quote, Search } from "lucide-react";
import { CollectionChip } from "@/components/TagChip";
import { ModelBadge } from "@/components/ModelBadge";

// Text-only "thesis" reader: left = sortable/filterable index of reels
// (heading + sub-heading), right = the reel's full text as a long-form paper.
// No video, no thumbnails — reading surface only.

type Sort = "newest" | "oldest" | "likes" | "title";
const SORTS: { v: Sort; label: string }[] = [
  { v: "newest", label: "Newest" },
  { v: "oldest", label: "Oldest" },
  { v: "likes", label: "Most liked" },
  { v: "title", label: "Title A–Z" },
];

const ts = (s: string | null) => (s ? new Date(s).getTime() : 0);
const fmtDate = (s: string | null) =>
  s ? new Date(s).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }) : "";

// pull bare URLs out of caption/summary text so every entry surfaces its links
const URL_RE = /(https?:\/\/[^\s)]+)|(\b[a-z0-9-]+\.(?:com|io|org|net|dev|ai|co|app|gg|me)\/[^\s)]*)/gi;
const extractLinks = (r: ReelDetail): string[] => {
  const text = `${r.caption ?? ""}\n${r.summary ?? ""}`;
  const hits = text.match(URL_RE) ?? [];
  const norm = hits.map((h) => (h.startsWith("http") ? h : `https://${h}`));
  return [...new Set([r.url, ...norm])];
};

export default function ReaderPage() {
  const [reels, setReels] = useState<ReelSummary[]>([]);
  const [q, setQ] = useState("");
  const [collection, setCollection] = useState("");
  const [sort, setSort] = useState<Sort>("newest");
  const [params, setParams] = useSearchParams();
  const sel = params.get("r");

  useEffect(() => {
    api.reels().then(setReels).catch(() => setReels([]));
  }, []);

  const allCollections = useMemo(
    () => [...new Set(reels.flatMap((r) => r.collections ?? []))].sort(),
    [reels],
  );

  const list = useMemo(() => {
    const filtered = reels.filter(
      (r) =>
        (!collection || (r.collections ?? []).includes(collection)) &&
        (!q ||
          r.title.toLowerCase().includes(q.toLowerCase()) ||
          r.author.toLowerCase().includes(q.toLowerCase()) ||
          r.genre.toLowerCase().includes(q.toLowerCase()) ||
          (r.tags ?? []).some((t) => t.includes(q.toLowerCase()))),
    );
    const sorted = [...filtered].sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title);
      if (sort === "likes") return (b.likes ?? 0) - (a.likes ?? 0);
      if (sort === "oldest") return ts(a.timestamp) - ts(b.timestamp);
      return ts(b.timestamp) - ts(a.timestamp); // newest
    });
    return sorted;
  }, [reels, q, collection, sort]);

  // keep a valid selection: default to the first item when none/invalid
  useEffect(() => {
    if (list.length === 0) return;
    if (!sel || !list.some((r) => r.id === sel)) setParams({ r: list[0].id }, { replace: true });
  }, [list, sel, setParams]);

  const selCls = "rounded-md border border-surface0 bg-base px-2 py-1.5 text-sm text-text";

  return (
    <div className="flex h-full">
      {/* left: sortable / filterable index */}
      <aside className="flex w-80 shrink-0 flex-col border-r border-surface0 bg-mantle">
        <div className="space-y-2 border-b border-surface0 p-3">
          <div className="flex items-center gap-2">
            <Quote size={16} className="text-mauve" />
            <h2 className="text-sm font-semibold text-text">Reader</h2>
            <span className="ml-auto text-xs text-overlay0">{list.length}</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-md border border-surface0 bg-base px-2">
            <Search size={13} className="text-overlay0" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Filter…"
              className="w-full bg-transparent py-1.5 text-sm text-text outline-none placeholder:text-overlay0"
            />
          </div>
          <div className="flex gap-1.5">
            <select value={collection} onChange={(e) => setCollection(e.target.value)} className={`${selCls} flex-1`}>
              <option value="">All collections</option>
              {allCollections.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className={selCls}>
              {SORTS.map((s) => (
                <option key={s.v} value={s.v}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {list.map((r, i) => {
            const active = r.id === sel;
            return (
              <button
                key={r.id}
                onClick={() => setParams({ r: r.id })}
                className={`block w-full border-b border-surface0/50 px-3 py-2.5 text-left transition-colors ${
                  active ? "bg-mauve/15" : "hover:bg-surface0/60"
                }`}
              >
                <div className="flex gap-2">
                  <span className="mt-0.5 w-6 shrink-0 text-right font-mono text-[10px] text-overlay0">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0">
                    {/* heading */}
                    <div className={`line-clamp-2 text-sm font-medium ${active ? "text-mauve" : "text-text"}`}>
                      {r.title}
                    </div>
                    {/* side heading */}
                    <div className="mt-0.5 truncate text-xs text-overlay0">
                      {r.author}
                      {r.genre && <span className="text-subtext"> · {r.genre}</span>}
                      {r.timestamp && <span> · {fmtDate(r.timestamp)}</span>}
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
          {list.length === 0 && (
            <div className="p-6 text-center text-sm text-overlay0">No reels match.</div>
          )}
        </div>
      </aside>

      {/* right: thesis-style paper */}
      <main className="flex-1 overflow-y-auto">
        {sel ? <Paper id={sel} /> : <div className="p-16 text-center text-overlay0">Select a reel.</div>}
      </main>
    </div>
  );
}

function Paper({ id }: { id: string }) {
  const [r, setR] = useState<ReelDetail | null>(null);
  const navigate = useNavigate();
  useEffect(() => {
    setR(null);
    api.reel(id).then(setR).catch(() => setR(null));
  }, [id]);

  if (!r) return <div className="p-16 text-center text-overlay0">Loading…</div>;

  const links = extractLinks(r);
  const structured = Object.entries(r.structured ?? {}).filter(
    ([, v]) => v != null && v !== "" && !(Array.isArray(v) && v.length === 0),
  );

  return (
    <article className="mx-auto max-w-3xl px-8 py-12 font-serif text-text">
      {/* title block */}
      <header className="mb-8 border-b border-surface0 pb-6">
        <h1 className="text-3xl font-bold leading-tight text-text">{r.title || r.id}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 font-sans text-sm text-subtext">
          <span className="font-medium text-text">{r.author}</span>
          {r.timestamp && <span>· {fmtDate(r.timestamp)}</span>}
          {r.genre && <span className="rounded bg-surface0 px-2 py-0.5 text-xs capitalize text-mauve">{r.genre}</span>}
          <ModelBadge
            backend={r.tokens?.backend ?? r.backend}
            model={r.tokens?.model ?? r.model}
            showModel
          />
          {(r.collections ?? []).map((c) => (
            <CollectionChip key={c} name={c} onClick={() => navigate(`/reels?collection=${encodeURIComponent(c)}`)} />
          ))}
          <a href={r.url} target="_blank" className="inline-flex items-center gap-1 text-blue hover:underline">
            <ExternalLink size={12} /> source
          </a>
        </div>
        {(r.tags ?? []).length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 font-sans">
            <Hash size={13} className="text-overlay0" />
            {r.tags.map((t) => (
              <span key={t} className="rounded bg-surface0 px-2 py-0.5 text-xs text-subtext">#{t}</span>
            ))}
          </div>
        )}
      </header>

      {/* abstract = summary */}
      {r.summary && (
        <Sec label="Abstract">
          <p className="text-[17px] leading-relaxed text-subtext">{r.summary}</p>
        </Sec>
      )}

      {/* key facts with provenance */}
      {r.facts?.length > 0 && (
        <Sec label="Key points">
          <ol className="space-y-2.5">
            {r.facts.map((f, i) => (
              <li key={i} className="flex gap-3 leading-relaxed">
                <span className="mt-1 shrink-0 font-mono text-xs text-peach">
                  {f.timestamp != null ? `${f.timestamp}s` : "—"}
                </span>
                <span className="text-[17px] text-subtext">{f.text}</span>
              </li>
            ))}
          </ol>
        </Sec>
      )}

      {/* structured fields (genre-specific) */}
      {structured.length > 0 && (
        <Sec label="Details">
          <dl className="divide-y divide-surface0/50">
            {structured.map(([k, v]) => (
              <div key={k} className="grid grid-cols-[9rem_1fr] gap-3 py-2">
                <dt className="font-sans text-xs uppercase tracking-wide text-overlay0">{k.replace(/_/g, " ")}</dt>
                <dd className="text-[16px] text-subtext">
                  {Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v)}
                </dd>
              </div>
            ))}
          </dl>
        </Sec>
      )}

      {/* transcript */}
      {r.transcript_text && (
        <Sec label={r.transcript_translated ? `Transcript (translated${r.transcript_language ? ` from ${r.transcript_language}` : ""})` : "Transcript"}>
          <p className="whitespace-pre-wrap text-[17px] leading-relaxed text-subtext">{r.transcript_text}</p>
        </Sec>
      )}

      {/* caption */}
      {r.caption && (
        <Sec label="Caption">
          <p className="whitespace-pre-wrap text-[16px] leading-relaxed text-subtext">{r.caption}</p>
        </Sec>
      )}

      {/* on-screen text */}
      {r.ocr_text?.length > 0 && (
        <Sec label="On-screen text">
          <p className="text-[16px] leading-relaxed text-subtext">{r.ocr_text.join(" · ")}</p>
        </Sec>
      )}

      {/* what a second model said about the same reel — from disk, not a new run */}
      <ModelDiff key={r.id} id={r.id} />

      {/* every link, consistently surfaced */}
      {links.length > 0 && (
        <Sec label="Links">
          <ul className="space-y-1 font-sans">
            {links.map((l) => (
              <li key={l}>
                <a href={l} target="_blank" className="inline-flex items-center gap-1.5 break-all text-sm text-blue hover:underline">
                  <ExternalLink size={12} className="shrink-0" /> {l}
                </a>
              </li>
            ))}
          </ul>
        </Sec>
      )}
    </article>
  );
}

// Inline local-vs-cloud diff. Reads stored variants only — the Compare tab is
// where you pay to run a model; here you just see what the other arm already said.
function ModelDiff({ id }: { id: string }) {
  const [d, setD] = useState<VariantsDiff | null>(null);
  const [pair, setPair] = useState<{ a: string; b: string } | null>(null);

  useEffect(() => {
    setD(null);
    api.variantsDiff(id, pair?.a, pair?.b).then(setD).catch(() => setD(null));
  }, [id, pair]);

  if (!d || d.available.length < 2 || !d.diff.shared) return null;
  const { only_a = [], only_b = [], shared = [] } = d.diff;
  const va = d.variants[d.a];
  const vb = d.variants[d.b];
  const pick = (which: "a" | "b") => (e: React.ChangeEvent<HTMLSelectElement>) =>
    setPair(which === "a" ? { a: e.target.value, b: d.b } : { a: d.a, b: e.target.value });
  const sel = "rounded border border-surface0 bg-base px-1.5 py-0.5 font-sans text-xs text-text";
  const meta = (v: typeof va) =>
    v ? `${v.facts.length} claims · ${v.elapsed_s ? `${v.elapsed_s.toFixed(1)}s` : "—"} · ${v.cost_usd ? `$${v.cost_usd.toFixed(2)}` : "$0"}` : "";

  return (
    <Sec label="Model diff">
      <div className="mb-3 flex flex-wrap items-center gap-2 font-sans text-xs text-overlay0">
        <select value={d.a} onChange={pick("a")} className={sel}>
          {d.available.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <span>{meta(va)}</span>
        <span className="text-overlay0">vs</span>
        <select value={d.b} onChange={pick("b")} className={sel}>
          {d.available.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <span>{meta(vb)}</span>
        <span className="ml-auto">
          {shared.length} shared · {only_a.length} only {d.a} · {only_b.length} only {d.b}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 font-sans text-sm">
        <Claims title={`Only ${d.a}`} colour="text-mauve" items={only_a} />
        <Claims title={`Only ${d.b}`} colour="text-peach" items={only_b} />
      </div>

      {shared.length > 0 && (
        <details className="mt-3 font-sans text-sm">
          <summary className="cursor-pointer text-xs uppercase tracking-wide text-overlay0">
            {shared.length} claims both models make
          </summary>
          <ul className="mt-2 space-y-2">
            {shared.map((s, i) => (
              <li key={i} className="rounded border border-surface0/60 p-2 text-subtext">
                <div>{s.a}</div>
                <div className="mt-1 text-overlay0">{s.b}</div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Sec>
  );
}

function Claims({ title, colour, items }: { title: string; colour: string; items: string[] }) {
  return (
    <div>
      <h3 className={`mb-1.5 text-xs font-semibold uppercase tracking-wide ${colour}`}>
        {title} <span className="text-overlay0">({items.length})</span>
      </h3>
      {items.length === 0 ? (
        <p className="text-xs text-overlay0">nothing the other model missed</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((t, i) => (
            <li key={i} className="leading-snug text-subtext">· {t}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Sec({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-2 font-sans text-xs font-semibold uppercase tracking-widest text-overlay0">{label}</h2>
      {children}
    </section>
  );
}
