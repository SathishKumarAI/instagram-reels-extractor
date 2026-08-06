import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type ReelDetail, type ReelSummary, type SavedView, type Stats } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { CollectionChip } from "@/components/TagChip";
import { ModelBadge } from "@/components/ModelBadge";
import { fmtNum } from "@/lib/utils";
import { Archive, Calendar, Check, Coins, Copy, Download, ExternalLink, FileText, Hash, Heart, MessageCircle, Star, X } from "lucide-react";

const fmtTok = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`);

type Sort = "newest" | "oldest" | "likes" | "comments" | "tokens" | "duration" | "title";
const SORTS: { v: Sort; label: string }[] = [
  { v: "newest", label: "Newest first" },
  { v: "oldest", label: "Oldest first" },
  { v: "likes", label: "Most liked" },
  { v: "comments", label: "Most comments" },
  { v: "tokens", label: "Most tokens" },
  { v: "duration", label: "Longest" },
  { v: "title", label: "Title A–Z" },
];

// value = max age in days ("all" = no date filter)
const PERIODS: { v: string; label: string }[] = [
  { v: "all", label: "Any date" },
  { v: "7", label: "Past week" },
  { v: "30", label: "Past month" },
  { v: "90", label: "Past 3 months" },
  { v: "365", label: "Past year" },
];
const ts = (s: string | null) => (s ? new Date(s).getTime() : 0);
const fmtDate = (s: string | null) =>
  s ? new Date(s).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "";

const selCls =
  "rounded-md border border-surface0 bg-base px-2 py-2 text-sm text-text";

export default function ReelsPage() {
  const [reels, setReels] = useState<ReelSummary[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [genre, setGenre] = useState("");
  const [account, setAccount] = useState("");
  const [collection, setCollection] = useState("");
  const [status, setStatus] = useState<"all" | "starred" | "unread" | "archived">("all");
  const [sort, setSort] = useState<Sort>("newest");
  const [period, setPeriod] = useState("all");
  const [views, setViews] = useState<SavedView[]>([]);
  const [params, setParams] = useSearchParams();
  const focus = params.get("focus");

  useEffect(() => {
    api.reels().then(setReels).catch(() => setReels([]));
    api.stats().then(setStats).catch(() => setStats(null));
    api.views().then(setViews).catch(() => setViews([]));
  }, []);

  // inbound deep links: /reels?tag=x, /reels?collection=y (from the reader, tags page)
  useEffect(() => {
    const t = params.get("tag");
    if (t) setTag(t);
    const c = params.get("collection");
    if (c) setCollection(c);
  }, [params]);

  const setFlag = (id: string, key: "starred" | "read" | "archived", val: boolean) => {
    setReels((rs) => rs.map((r) => (r.id === id ? { ...r, [key]: val } : r)));
    api.annotate(id, { [key]: val }).catch(() => {});
  };

  const saveCurrentView = () => {
    const name = prompt("Save this filter as a view named:");
    if (!name) return;
    api.saveView(name, { genre, account, collection, tag: tag ?? "", status, sort }).then(setViews).catch(() => {});
  };
  const applyView = (v: SavedView) => {
    const f = v.filters;
    setGenre(f.genre ?? ""); setAccount(f.account ?? ""); setCollection(f.collection ?? "");
    setTag(f.tag || null); setStatus((f.status as typeof status) ?? "all");
    setSort((f.sort as Sort) ?? "likes");
  };

  const tokByCat = useMemo(() => {
    const m = new Map<string, { in: number; out: number; cost: number }>();
    for (const c of stats?.categories ?? [])
      m.set(c.genre, { in: c.tokens_in, out: c.tokens_out, cost: c.cost_usd });
    return m;
  }, [stats]);

  const allGenres = useMemo(
    () => [...new Set(reels.map((r) => r.genre).filter(Boolean))].sort(),
    [reels],
  );
  const allAccounts = useMemo(
    () => [...new Set(reels.map((r) => r.author).filter(Boolean))].sort(),
    [reels],
  );
  const allCollections = useMemo(
    () => [...new Set(reels.flatMap((r) => r.collections ?? []))].sort(),
    [reels],
  );

  const sortFn = (a: ReelSummary, b: ReelSummary) => {
    if (sort === "title") return a.title.localeCompare(b.title);
    if (sort === "newest") return ts(b.timestamp) - ts(a.timestamp);
    if (sort === "oldest") return ts(a.timestamp) - ts(b.timestamp);
    const val = (r: ReelSummary) =>
      sort === "tokens" ? r.tokens_in + r.tokens_out
        : sort === "duration" ? (r.duration ?? 0)
        : sort === "comments" ? (r.comments ?? 0)
        : (r.likes ?? 0);
    return val(b) - val(a);
  };

  const filtered = reels.filter(
    (r) =>
      (!q ||
        r.title.toLowerCase().includes(q.toLowerCase()) ||
        r.author.toLowerCase().includes(q.toLowerCase()) ||
        r.genre.toLowerCase().includes(q.toLowerCase()) ||
        r.tags.some((t) => t.includes(q.toLowerCase()))) &&
      (!tag || r.tags.includes(tag)) &&
      (!genre || r.genre === genre) &&
      (!account || r.author === account) &&
      (!collection || (r.collections ?? []).includes(collection)) &&
      (status === "archived" ? r.archived : !r.archived) &&
      (status !== "starred" || r.starred) &&
      (status !== "unread" || !r.read) &&
      (period === "all" ||
        (!!r.timestamp && Date.now() - ts(r.timestamp) <= Number(period) * 86400000)),
  );

  // group by category (genre); empty genre -> "uncategorized", sorted last
  const groups = new Map<string, ReelSummary[]>();
  for (const r of filtered) {
    const key = r.genre || "uncategorized";
    (groups.get(key) ?? groups.set(key, []).get(key)!).push(r);
  }
  for (const items of groups.values()) items.sort(sortFn);
  const filterActive = !!(q || tag || genre || account || collection || status !== "all" || period !== "all");
  const expQ = filterActive ? `?ids=${filtered.map((r) => r.id).join(",")}` : "";
  const categories = [...groups.entries()].sort((a, b) => {
    if (a[0] === "uncategorized") return 1;
    if (b[0] === "uncategorized") return -1;
    return b[1].length - a[1].length; // biggest category first
  });
  const orderedIds = categories.flatMap(([, items]) => items.map((r) => r.id));

  // keyboard: / focus search · j/k next-prev reel · s star · esc close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") return;
      if (e.key === "/") { e.preventDefault(); (document.querySelector<HTMLInputElement>('input[placeholder^="Search"]'))?.focus(); return; }
      if (!focus) return;
      const i = orderedIds.indexOf(focus);
      if ((e.key === "j" || e.key === "ArrowDown") && i < orderedIds.length - 1) setParams({ focus: orderedIds[i + 1] });
      else if ((e.key === "k" || e.key === "ArrowUp") && i > 0) setParams({ focus: orderedIds[i - 1] });
      else if (e.key === "Escape") setParams({});
      else if (e.key === "s") {
        const r = reels.find((x) => x.id === focus);
        if (r) setFlag(r.id, "starred", !r.starred);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [focus, orderedIds, reels]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">Reels</h1>
          <p className="text-sm text-overlay0">
            {reels.length} archived · {categories.length} categories
            {stats && stats.tokens_in + stats.tokens_out > 0 && (
              <span className="ml-2 inline-flex items-center gap-1 text-peach" title={stats.cost_note}>
                <Coins size={12} /> {fmtTok(stats.tokens_in)} in / {fmtTok(stats.tokens_out)} out
                {stats.cost_usd > 0 && <span className="ml-1">· ~${stats.cost_usd.toFixed(2)}*</span>}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={collection} onChange={(e) => setCollection(e.target.value)} className={selCls} title="Saved collection">
            <option value="">All collections</option>
            {allCollections.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select value={genre} onChange={(e) => setGenre(e.target.value)} className={selCls}>
            <option value="">All categories</option>
            {allGenres.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <select value={account} onChange={(e) => setAccount(e.target.value)} className={selCls}>
            <option value="">All accounts</option>
            {allAccounts.map((a) => (
              <option key={a} value={a}>@{a}</option>
            ))}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value as typeof status)} className={selCls}>
            <option value="all">All</option>
            <option value="starred">★ Starred</option>
            <option value="unread">Unread</option>
            <option value="archived">Archived</option>
          </select>
          <select value={period} onChange={(e) => setPeriod(e.target.value)} className={selCls} title="Filter by date posted">
            {PERIODS.map((p) => (
              <option key={p.v} value={p.v}>{p.label}</option>
            ))}
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className={selCls}>
            {SORTS.map((s) => (
              <option key={s.v} value={s.v}>{s.label}</option>
            ))}
          </select>
          <Input
            placeholder="Search title, author, genre, tag…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="max-w-xs"
          />
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-overlay0">Views:</span>
        {views.map((v) => (
          <button key={v.name} onClick={() => applyView(v)}
            className="rounded-full bg-surface0 px-3 py-1 text-xs text-subtext hover:bg-mauve/20 hover:text-mauve">
            {v.name}
          </button>
        ))}
        <Button variant="ghost" size="sm" onClick={saveCurrentView}>+ Save view</Button>
        <span className="mx-1 text-overlay0">·</span>
        <span className="text-overlay0">Export{expQ ? " (filtered)" : ""}:</span>
        <a href={`/api/export.csv${expQ}`} download><Button variant="ghost" size="sm"><Download size={13} /> CSV</Button></a>
        <a href={`/api/export.xlsx${expQ}`} download><Button variant="ghost" size="sm">XLSX</Button></a>
        <a href={`/api/export.md${expQ}`} download><Button variant="ghost" size="sm">MD</Button></a>
      </div>

      {tag && (
        <div className="mb-4 flex items-center gap-2 text-sm">
          <span className="text-overlay0">filtering tag</span>
          <Badge variant="genre">#{tag}</Badge>
          <Button variant="ghost" size="sm" onClick={() => setTag(null)}>clear</Button>
        </div>
      )}

      <div className="space-y-8">
        {categories.map(([cat, items]) => {
          const tk = tokByCat.get(cat);
          return (
          <section key={cat}>
            <div className="mb-3 flex items-center gap-2 border-b border-surface0 pb-2">
              <Badge variant="genre" className="capitalize">{cat}</Badge>
              <span className="text-xs text-overlay0">{items.length} reels</span>
              {tk && tk.in + tk.out > 0 && (
                <span className="inline-flex items-center gap-1 text-xs text-peach">
                  <Coins size={11} /> {fmtTok(tk.in)}/{fmtTok(tk.out)} tok
                  {tk.cost > 0 && <span>· ~${tk.cost.toFixed(2)}</span>}
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((r) => (
                <Card
                  key={r.id}
                  className="group relative cursor-pointer overflow-hidden origin-center transform-gpu will-change-transform transition-all duration-300 ease-out hover:scale-[1.035] hover:z-10 hover:border-mauve hover:shadow-2xl hover:shadow-mauve/20"
                  onClick={() => { setParams({ focus: r.id }); if (!r.read) setFlag(r.id, "read", true); }}
                >
                  <div className="absolute right-1.5 top-1.5 z-10 flex gap-1">
                    <button
                      title="Star"
                      onClick={(e) => { e.stopPropagation(); setFlag(r.id, "starred", !r.starred); }}
                      className={`rounded-full bg-crust/70 p-1.5 ${r.starred ? "text-yellow" : "text-subtext hover:text-yellow"}`}
                    >
                      <Star size={13} fill={r.starred ? "currentColor" : "none"} />
                    </button>
                    <button
                      title="Archive"
                      onClick={(e) => { e.stopPropagation(); setFlag(r.id, "archived", !r.archived); }}
                      className="rounded-full bg-crust/70 p-1.5 text-subtext hover:text-red"
                    >
                      <Archive size={13} />
                    </button>
                  </div>
                  <div className="overflow-hidden">
                    <img
                      src={api.media(r.id, "thumbnail")}
                      alt=""
                      className={`h-56 w-full bg-surface0 object-cover transition-transform duration-500 ease-out group-hover:scale-105 ${r.read ? "opacity-70" : ""}`}
                      onError={(e) => ((e.target as HTMLImageElement).style.opacity = "0")}
                    />
                  </div>
                  <CardContent>
                    <div className="mb-1 flex items-center gap-2">
                      {r.genre && <Badge variant="genre">{r.genre}</Badge>}
                      <ModelBadge backend={r.backend} model={r.model} size="xs" />
                    </div>
                    <div className="line-clamp-2 text-sm font-medium text-text">{r.title}</div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-overlay0">
                      <span className="truncate">{r.author}</span>
                      {r.timestamp && (
                        <span className="flex shrink-0 items-center gap-1 text-overlay0/80">
                          <Calendar size={11} />{fmtDate(r.timestamp)}
                        </span>
                      )}
                    </div>
                    {(r.collections ?? []).length > 0 && (
                      // every shelf, not a truncated one — 1 in 4 reels sits on two
                      <div className="mt-2 flex flex-wrap gap-1">
                        {r.collections.map((c) => (
                          <span key={c} onClick={(e) => e.stopPropagation()}>
                            {/* URL too, so the filtered grid is shareable and survives a reload */}
                            <CollectionChip name={c} onClick={() => { setCollection(c); setParams({ collection: c }); }} />
                          </span>
                        ))}
                      </div>
                    )}
                    {r.tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {r.tags.slice(0, 4).map((t) => (
                          <button
                            key={t}
                            onClick={(e) => { e.stopPropagation(); setTag(t); }}
                            className="rounded bg-surface0 px-1.5 py-0.5 text-[10px] text-subtext hover:bg-mauve/20 hover:text-mauve"
                          >#{t}</button>
                        ))}
                      </div>
                    )}
                    <div className="mt-2 flex gap-3 text-xs text-subtext">
                      <span className="flex items-center gap-1"><Heart size={12} />{fmtNum(r.likes)}</span>
                      <span className="flex items-center gap-1"><MessageCircle size={12} />{fmtNum(r.comments)}</span>
                      {r.tokens_in + r.tokens_out > 0 && (
                        <span className="flex items-center gap-1 text-peach" title="vision tokens in/out">
                          <Coins size={12} />{fmtTok(r.tokens_in)}/{fmtTok(r.tokens_out)}
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
          );
        })}
        {categories.length === 0 && (
          <div className="py-16 text-center text-overlay0">
            {reels.length === 0 ? "No reels yet — add a source and run sync." : "No reels match these filters."}
          </div>
        )}
      </div>

      {focus && <ReelDrawer id={focus} onClose={() => setParams({})} />}
    </div>
  );
}

function ReelDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const [r, setR] = useState<ReelDetail | null>(null);
  const [similar, setSimilar] = useState<{ reel_id: string; title: string }[]>([]);
  const [, setParams] = useSearchParams();
  useEffect(() => {
    setR(null); setSimilar([]);
    api.reel(id).then(setR).catch(() => setR(null));
    api.similar(id).then((h) => setSimilar(h.map((x) => ({ reel_id: x.reel_id, title: x.title })))).catch(() => setSimilar([]));
  }, [id]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-crust/60" onClick={onClose}>
      <div
        className="h-full w-full max-w-2xl overflow-y-auto border-l border-surface0 bg-base p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-xl font-bold text-text">{r?.title ?? id}</h2>
          <div className="flex items-center gap-2">
            {r && (
              <Button variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(reelMarkdown(r)).catch(() => {})}>
                <Copy size={14} /> Copy all
              </Button>
            )}
            <Button variant="ghost" size="icon" onClick={onClose}><X size={18} /></Button>
          </div>
        </div>
        {!r ? (
          <p className="text-overlay0">Loading…</p>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2 text-sm text-subtext">
              {r.genre && <Badge variant="genre">{r.genre}</Badge>}
              <ModelBadge backend={r.tokens?.backend ?? r.backend} model={r.tokens?.model ?? r.model} showModel />
              <span>{r.author}</span>
              <a href={r.url} target="_blank" className="flex items-center gap-1 text-blue hover:underline">
                <ExternalLink size={13} /> original
              </a>
              {r.has_pdf && (
                <a href={api.media(r.id, "pdf")} target="_blank" className="flex items-center gap-1 text-peach hover:underline">
                  <FileText size={13} /> PDF
                </a>
              )}
              {(r.tokens?.input || r.tokens?.output) && (
                <span className="flex items-center gap-1 text-peach" title="vision tokens in/out">
                  <Coins size={13} /> {fmtTok(r.tokens.input ?? 0)} in / {fmtTok(r.tokens.output ?? 0)} out
                </span>
              )}
            </div>

            {(r.collections ?? []).length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                {r.collections.map((c) => (
                  // filtering the grid means leaving the drawer — dropping `focus` closes it
                  <CollectionChip key={c} name={c} onClick={() => setParams({ collection: c })} />
                ))}
              </div>
            )}

            {r.tags?.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <Hash size={13} className="text-overlay0" />
                {r.tags.map((t) => (
                  <span key={t} className="rounded bg-surface0 px-2 py-0.5 text-xs text-subtext">#{t}</span>
                ))}
              </div>
            )}

            {r.video_path && (
              <video src={api.media(r.id, "video")} controls className="w-full rounded-lg bg-crust" />
            )}

            {r.summary && (
              <Section title="Summary" copy={r.summary}><p className="text-sm text-subtext">{r.summary}</p></Section>
            )}

            {r.facts.length > 0 && (
              <Section title="Key facts (with provenance)"
                copy={r.facts.map((f) => `${f.timestamp != null ? `[${f.timestamp}s] ` : ""}${f.text}`).join("\n")}>
                <table className="w-full text-sm">
                  <tbody>
                    {r.facts.map((f, i) => (
                      <tr key={i} className="border-b border-surface0/50">
                        <td className="py-1.5 pr-3 align-top font-mono text-xs text-peach">
                          {f.timestamp != null ? `${f.timestamp}s` : "—"}
                        </td>
                        <td className="py-1.5 text-subtext">{f.text}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Section>
            )}

            {r.transcript_text && (
              <Section title="Transcript" copy={r.transcript_text}>
                {(r.transcript_language || r.transcript_translated) && (
                  <div className="mb-1">
                    <Badge variant="genre">
                      {r.transcript_translated ? `translated · ${r.transcript_language || "?"}` : r.transcript_language}
                    </Badge>
                  </div>
                )}
                <p className="text-sm text-subtext">{r.transcript_text}</p>
              </Section>
            )}

            <Section title="Notes">
              <NoteBox id={id} initial={r.annotation?.note ?? ""} />
            </Section>

            {r.ocr_text?.length > 0 && (
              <Section title="On-screen text">
                <div className="flex flex-wrap gap-1.5">
                  {r.ocr_text.slice(0, 60).map((t, i) => (
                    <span key={i} className="rounded bg-surface0 px-1.5 py-0.5 text-xs text-subtext">{t}</span>
                  ))}
                </div>
              </Section>
            )}

            {r.caption && (
              <Section title="Caption"><p className="whitespace-pre-wrap text-sm text-subtext">{r.caption}</p></Section>
            )}

            {similar.length > 0 && (
              <Section title="More like this">
                <div className="flex flex-col gap-1">
                  {similar.map((s) => (
                    <button key={s.reel_id} onClick={() => setParams({ focus: s.reel_id })}
                      className="truncate text-left text-sm text-blue hover:underline">
                      → {s.title}
                    </button>
                  ))}
                </div>
              </Section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CopyBtn({ text, label }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  const copy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text).then(() => {
      setDone(true);
      setTimeout(() => setDone(false), 1200);
    }).catch(() => {});
  };
  return (
    <button onClick={copy} title="Copy" className="inline-flex items-center gap-1 text-xs text-overlay0 hover:text-mauve">
      {done ? <Check size={12} /> : <Copy size={12} />}{label && <span>{label}</span>}
    </button>
  );
}

function reelMarkdown(r: ReelDetail): string {
  const lines = [`# ${r.title || r.id}`, `${r.url}`, ""];
  if (r.genre) lines.push(`**Category:** ${r.genre}`);
  if (r.tags?.length) lines.push(`**Tags:** ${r.tags.map((t) => "#" + t).join(" ")}`);
  if (r.summary) lines.push("", "## Summary", r.summary);
  if (r.facts?.length) {
    lines.push("", "## Key facts");
    for (const f of r.facts) lines.push(`- ${f.timestamp != null ? `[${f.timestamp}s] ` : ""}${f.text}`);
  }
  if (r.transcript_text) lines.push("", "## Transcript", r.transcript_text);
  if (r.caption) lines.push("", "## Caption", r.caption);
  return lines.join("\n");
}

function NoteBox({ id, initial }: { id: string; initial: string }) {
  const [note, setNote] = useState(initial);
  const [saved, setSaved] = useState(true);
  useEffect(() => { setNote(initial); setSaved(true); }, [id, initial]);
  return (
    <div>
      <textarea
        value={note}
        onChange={(e) => { setNote(e.target.value); setSaved(false); }}
        onBlur={() => { if (!saved) { api.annotate(id, { note }).then(() => setSaved(true)).catch(() => {}); } }}
        placeholder="Your notes (auto-saves on blur)…"
        className="min-h-[70px] w-full rounded-md border border-surface0 bg-base p-2 text-sm text-text"
      />
      <div className="mt-1 text-xs text-overlay0">{saved ? "saved" : "editing…"}</div>
    </div>
  );
}

function Section({ title, children, copy }: { title: string; children: React.ReactNode; copy?: string }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-overlay0">{title}</h3>
        {copy && <CopyBtn text={copy} />}
      </div>
      {children}
    </div>
  );
}
