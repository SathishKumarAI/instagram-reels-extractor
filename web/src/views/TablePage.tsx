import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ReelSummary } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fmtNum } from "@/lib/utils";
import { Archive, ArrowDown, ArrowUp, Copy, Download, ExternalLink, Star } from "lucide-react";

type Key = keyof ReelSummary;
const COLS: { key: Key; label: string; num?: boolean }[] = [
  { key: "title", label: "Title" },
  { key: "author", label: "Author" },
  { key: "genre", label: "Category" },
  { key: "tags", label: "Tags" },
  { key: "likes", label: "Likes", num: true },
  { key: "comments", label: "Comments", num: true },
  { key: "duration", label: "Dur (s)", num: true },
  { key: "tokens_in", label: "Tok in", num: true },
  { key: "tokens_out", label: "Tok out", num: true },
];

export default function TablePage() {
  const [reels, setReels] = useState<ReelSummary[]>([]);
  const [q, setQ] = useState("");
  const [genre, setGenre] = useState("");
  const [account, setAccount] = useState("");
  const [minLikes, setMinLikes] = useState(0);
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "likes", dir: -1 });
  const [sel, setSel] = useState<Set<string>>(new Set());
  const navigate = useNavigate();

  useEffect(() => {
    api.reels().then(setReels).catch(() => setReels([]));
  }, []);

  const allGenres = useMemo(
    () => [...new Set(reels.map((r) => r.genre).filter(Boolean))].sort(),
    [reels],
  );
  const allAccounts = useMemo(
    () => [...new Set(reels.map((r) => r.author).filter(Boolean))].sort(),
    [reels],
  );

  const rows = useMemo(() => {
    const f = reels.filter(
      (r) =>
        (!q ||
          r.title.toLowerCase().includes(q.toLowerCase()) ||
          r.author.toLowerCase().includes(q.toLowerCase()) ||
          r.genre.toLowerCase().includes(q.toLowerCase()) ||
          r.tags.some((t) => t.includes(q.toLowerCase()))) &&
        (!genre || r.genre === genre) &&
        (!account || r.author === account) &&
        (!minLikes || (r.likes ?? 0) >= minLikes),
    );
    const { key, dir } = sort;
    return [...f].sort((a, b) => {
      const av = a[key], bv = b[key];
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      return String(av ?? "").localeCompare(String(bv ?? "")) * dir;
    });
  }, [reels, q, genre, account, minLikes, sort]);

  const toggle = (key: Key) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: -1 }));

  const toggleSel = (id: string) =>
    setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allSelected = rows.length > 0 && rows.every((r) => sel.has(r.id));
  const selectAll = () =>
    setSel(allSelected ? new Set() : new Set(rows.map((r) => r.id)));
  const selIds = [...sel];

  const bulkFlag = (key: "starred" | "archived", val: boolean) => {
    selIds.forEach((id) => api.annotate(id, { [key]: val }).catch(() => {}));
    setReels((rs) => rs.map((r) => (sel.has(r.id) ? { ...r, [key]: val } : r)));
  };
  const copySelected = () => {
    const lines = rows.filter((r) => sel.has(r.id))
      .map((r) => `- ${r.title} — ${r.url}${r.tags.length ? "  " + r.tags.map((t) => "#" + t).join(" ") : ""}`);
    navigator.clipboard.writeText(lines.join("\n")).catch(() => {});
  };

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">Table</h1>
          <p className="text-sm text-overlay0">{rows.length} of {reels.length} reels · click a header to sort</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            className="rounded-md border border-surface0 bg-base px-2 py-2 text-sm text-text"
          >
            <option value="">All categories</option>
            {allGenres.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <select
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            className="rounded-md border border-surface0 bg-base px-2 py-2 text-sm text-text"
          >
            <option value="">All accounts</option>
            {allAccounts.map((a) => (
              <option key={a} value={a}>@{a}</option>
            ))}
          </select>
          <Input type="number" min={0} placeholder="min likes"
            value={minLikes || ""} onChange={(e) => setMinLikes(Number(e.target.value) || 0)}
            className="w-24" />
          <Input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
          <a href="/api/export.csv" download>
            <Button variant="default" size="sm"><Download size={15} /> Export CSV</Button>
          </a>
        </div>
      </div>

      {sel.size > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-mauve/40 bg-mauve/10 px-3 py-2 text-sm">
          <span className="font-medium text-mauve">{sel.size} selected</span>
          <Button variant="ghost" size="sm" onClick={() => bulkFlag("starred", true)}><Star size={13} /> Star</Button>
          <Button variant="ghost" size="sm" onClick={() => bulkFlag("archived", true)}><Archive size={13} /> Archive</Button>
          <Button variant="ghost" size="sm" onClick={copySelected}><Copy size={13} /> Copy list</Button>
          <a href={`/api/export.csv?ids=${selIds.join(",")}`} download><Button variant="ghost" size="sm"><Download size={13} /> CSV</Button></a>
          <a href={`/api/export.md?ids=${selIds.join(",")}`} download><Button variant="ghost" size="sm">MD</Button></a>
          <Button variant="ghost" size="sm" onClick={() => setSel(new Set())}>Clear</Button>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-surface0">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-mantle">
            <tr className="text-left text-overlay0">
              <th className="p-2"><input type="checkbox" checked={allSelected} onChange={selectAll} /></th>
              <th className="p-2 font-medium">#</th>
              {COLS.map((c) => (
                <th
                  key={c.key}
                  onClick={() => toggle(c.key)}
                  className={`cursor-pointer select-none whitespace-nowrap p-2 font-medium hover:text-text ${c.num ? "text-right" : ""}`}
                >
                  <span className="inline-flex items-center gap-1">
                    {c.label}
                    {sort.key === c.key && (sort.dir === -1 ? <ArrowDown size={12} /> : <ArrowUp size={12} />)}
                  </span>
                </th>
              ))}
              <th className="p-2 font-medium">Link</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.id}
                className={`border-t border-surface0/50 hover:bg-surface0/40 ${sel.has(r.id) ? "bg-mauve/10" : ""}`}
              >
                <td className="p-2"><input type="checkbox" checked={sel.has(r.id)} onChange={() => toggleSel(r.id)} /></td>
                <td className="p-2 text-overlay0">{i + 1}</td>
                <td className="max-w-xs p-2">
                  <button className="line-clamp-1 text-left text-text hover:text-mauve"
                    onClick={() => navigate(`/reels?focus=${r.id}`)}>{r.title}</button>
                </td>
                <td className="whitespace-nowrap p-2 text-subtext">{r.author}</td>
                <td className="p-2">{r.genre && <Badge variant="genre">{r.genre}</Badge>}</td>
                <td className="max-w-[16rem] p-2">
                  <div className="flex flex-wrap gap-1">
                    {r.tags.slice(0, 3).map((t) => (
                      <span key={t} className="rounded bg-surface0 px-1 text-[10px] text-subtext">#{t}</span>
                    ))}
                  </div>
                </td>
                <td className="p-2 text-right tabular-nums text-subtext">{fmtNum(r.likes)}</td>
                <td className="p-2 text-right tabular-nums text-subtext">{fmtNum(r.comments)}</td>
                <td className="p-2 text-right tabular-nums text-subtext">{r.duration ? Math.round(r.duration) : "—"}</td>
                <td className="p-2 text-right tabular-nums text-peach">{r.tokens_in || "—"}</td>
                <td className="p-2 text-right tabular-nums text-peach">{r.tokens_out || "—"}</td>
                <td className="p-2">
                  <a href={r.url} target="_blank" className="text-blue hover:underline"><ExternalLink size={14} /></a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <div className="py-12 text-center text-sm text-overlay0">No reels match these filters.</div>
        )}
      </div>
    </div>
  );
}
