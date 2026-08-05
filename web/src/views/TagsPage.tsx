import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type TagRow } from "@/lib/api";
import { CollectionLegend, TagChip } from "@/components/TagChip";

type Sort = "count" | "alpha";

export default function TagsPage() {
  const [tags, setTags] = useState<TagRow[]>([]);
  const [edit, setEdit] = useState(false);
  const [msg, setMsg] = useState("");
  const [filter, setFilter] = useState("");        // collection filter, "" = all
  const [sort, setSort] = useState<Sort>("count");
  const nav = useNavigate();

  const load = () => api.tags().then(setTags).catch(() => setTags([]));
  useEffect(() => { load(); }, []);

  // collections ordered by how many tags they own — the legend reads top-down
  const collections = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of tags) for (const col of t.collections) c[col.name] = (c[col.name] ?? 0) + 1;
    return Object.entries(c).sort((a, b) => b[1] - a[1]).map(([n]) => n);
  }, [tags]);

  const shown = useMemo(() => {
    const rows = filter ? tags.filter((t) => t.collections.some((c) => c.name === filter)) : tags;
    return [...rows].sort((a, b) =>
      sort === "alpha" ? a.tag.localeCompare(b.tag) : b.count - a.count || a.tag.localeCompare(b.tag),
    );
  }, [tags, filter, sort]);

  const onTag = async (t: string) => {
    if (!edit) { nav(`/reels?tag=${encodeURIComponent(t)}`); return; }
    const to = prompt(`Rename / merge "#${t}" → (empty = delete):`, t);
    if (to === null) return;
    const r = await api.renameTag(t, to).catch(() => null);
    if (r) { setMsg(`#${t} → ${to || "(deleted)"} · ${r.reels_updated} reels`); load(); }
  };

  return (
    <div className="p-6">
      {/* orient */}
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text">Tags</h1>
        <button
          onClick={() => setEdit((e) => !e)}
          className={`rounded-md px-3 py-1 text-sm ${
            edit ? "bg-mauve text-crust" : "bg-surface0 text-subtext hover:text-text"
          }`}
        >
          {edit ? "Done" : "Edit tags"}
        </button>
      </div>
      <p className="mb-3 text-sm text-overlay0">
        {shown.length} of {tags.length} tags ·{" "}
        {edit ? "click a tag to rename, merge or delete it across every reel." : "click to filter reels."}{" "}
        Colour = the collection a tag mostly lives in; a split rail means it spans two.
      </p>
      <div className="mb-4"><CollectionLegend names={collections} /></div>

      {/* act */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-md border border-surface0 bg-base px-2 py-1 text-sm text-text"
        >
          <option value="">all collections</option>
          {collections.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as Sort)}
          className="rounded-md border border-surface0 bg-base px-2 py-1 text-sm text-text"
        >
          <option value="count">most used</option>
          <option value="alpha">A→Z</option>
        </select>
      </div>
      {msg && <p className="mb-3 text-xs text-green">{msg}</p>}

      {/* review */}
      <div className="flex flex-wrap gap-2">
        {shown.map((t) => (
          <TagChip
            key={t.tag}
            tag={t.tag}
            count={t.count}
            collections={t.collections}
            size="md"
            onClick={() => onTag(t.tag)}
          />
        ))}
        {shown.length === 0 && (
          <p className="text-sm text-overlay0">
            {tags.length ? "No tags in that collection." : "No tags yet — run a sync with vision on."}
          </p>
        )}
      </div>
    </div>
  );
}
