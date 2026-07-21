import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Stats } from "@/lib/api";

export default function TagsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [edit, setEdit] = useState(false);
  const [msg, setMsg] = useState("");
  const nav = useNavigate();

  const load = () => api.stats().then(setStats).catch(() => setStats(null));
  useEffect(() => { load(); }, []);

  const tags = stats?.top_tags ?? [];
  const max = tags.length ? tags[0][1] : 1;

  const onTag = async (t: string) => {
    if (!edit) { nav(`/reels?tag=${encodeURIComponent(t)}`); return; }
    const to = prompt(`Rename / merge "#${t}" → (empty = delete):`, t);
    if (to === null) return;
    const r = await api.renameTag(t, to).catch(() => null);
    if (r) { setMsg(`#${t} → ${to || "(deleted)"} · ${r.reels_updated} reels`); load(); }
  };

  return (
    <div className="p-6">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text">Tags</h1>
        <button onClick={() => setEdit((e) => !e)}
          className={`rounded-md px-3 py-1 text-sm ${edit ? "bg-mauve text-crust" : "bg-surface0 text-subtext hover:text-text"}`}>
          {edit ? "Done" : "Edit tags"}
        </button>
      </div>
      <p className="mb-4 text-sm text-overlay0">
        {tags.length} tags · {edit ? "click a tag to rename/merge/delete across all reels." : "click to filter reels."}
      </p>
      {msg && <p className="mb-3 text-xs text-green">{msg}</p>}

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {tags.map(([t, n]) => {
          const size = 0.8 + (n / max) * 1.4; // rem
          return (
            <button
              key={t}
              onClick={() => onTag(t)}
              style={{ fontSize: `${size}rem` }}
              className={`font-medium transition-colors ${edit ? "text-peach hover:text-red" : "text-subtext hover:text-mauve"}`}
              title={`${n} reels`}
            >
              #{t}<sub className="ml-0.5 text-[0.6em] text-overlay0">{n}</sub>
            </button>
          );
        })}
        {tags.length === 0 && <p className="text-overlay0">No tags yet — run extraction with vision on.</p>}
      </div>
    </div>
  );
}
