import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ReelSummary } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Archive, ArchiveRestore, Star } from "lucide-react";

type ColKey = "unread" | "starred" | "archived";
const COLS: { key: ColKey; label: string }[] = [
  { key: "unread", label: "To read" },
  { key: "starred", label: "Starred" },
  { key: "archived", label: "Archived" },
];

export default function KanbanPage() {
  const [reels, setReels] = useState<ReelSummary[]>([]);
  const nav = useNavigate();

  useEffect(() => { api.reels().then(setReels).catch(() => setReels([])); }, []);

  const set = (id: string, key: "starred" | "read" | "archived", val: boolean) => {
    setReels((rs) => rs.map((r) => (r.id === id ? { ...r, [key]: val } : r)));
    api.annotate(id, { [key]: val }).catch(() => {});
  };

  const cols: Record<ColKey, ReelSummary[]> = {
    unread: reels.filter((r) => !r.archived && !r.read && !r.starred),
    starred: reels.filter((r) => !r.archived && r.starred),
    archived: reels.filter((r) => r.archived),
  };

  return (
    <div className="p-6">
      <h1 className="mb-1 text-2xl font-bold text-text">Board</h1>
      <p className="mb-5 text-sm text-overlay0">Work your archive by status. Move cards with the buttons.</p>

      <div className="grid gap-4 md:grid-cols-3">
        {COLS.map((c) => (
          <div key={c.key} className="rounded-lg border border-surface0 bg-mantle/40 p-3">
            <div className="mb-3 flex items-center gap-2">
              <Badge variant="genre">{c.label}</Badge>
              <span className="text-xs text-overlay0">{cols[c.key].length}</span>
            </div>
            <div className="space-y-2">
              {cols[c.key].slice(0, 60).map((r) => (
                <div key={r.id} className="rounded-md border border-surface0 bg-base p-2">
                  <button onClick={() => nav(`/reels?focus=${r.id}`)}
                    className="line-clamp-2 text-left text-sm text-text hover:text-mauve">{r.title}</button>
                  <div className="mt-1 flex items-center gap-1 text-overlay0">
                    <span className="mr-auto truncate text-xs">{r.author}</span>
                    <button title="Star" onClick={() => set(r.id, "starred", !r.starred)}
                      className={r.starred ? "text-yellow" : "hover:text-yellow"}>
                      <Star size={13} fill={r.starred ? "currentColor" : "none"} />
                    </button>
                    <button title={r.archived ? "Unarchive" : "Archive"}
                      onClick={() => set(r.id, "archived", !r.archived)} className="hover:text-red">
                      {r.archived ? <ArchiveRestore size={13} /> : <Archive size={13} />}
                    </button>
                  </div>
                </div>
              ))}
              {cols[c.key].length === 0 && <p className="text-xs text-overlay0">empty</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
