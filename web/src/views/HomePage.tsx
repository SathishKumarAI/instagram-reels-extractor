import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ReelSummary, type Stats } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clapperboard, Coins, FolderTree, Hash, Shuffle, Tag, type LucideIcon } from "lucide-react";

const fmt = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`);

function Stat({ icon: Icon, label, value, sub }: { icon: LucideIcon; label: string; value: string; sub?: string }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <div className="mb-1 flex items-center gap-2 text-overlay0"><Icon size={16} /><span className="text-xs">{label}</span></div>
        <div className="text-2xl font-bold text-text">{value}</div>
        {sub && <div className="text-xs text-overlay0">{sub}</div>}
      </CardContent>
    </Card>
  );
}

export default function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [reels, setReels] = useState<ReelSummary[]>([]);
  const nav = useNavigate();

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
    api.reels().then(setReels).catch(() => setReels([]));
  }, []);

  const starred = reels.filter((r) => r.starred).length;
  const recent = reels.slice(-8).reverse();

  return (
    <div className="p-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="mb-1 text-2xl font-bold text-text">Overview</h1>
          <p className="text-sm text-overlay0">Your Instagram knowledge base at a glance.</p>
        </div>
        <button
          onClick={() => { if (reels.length) nav(`/reels?focus=${reels[Math.floor(Math.random() * reels.length)].id}`); }}
          className="flex items-center gap-2 rounded-lg bg-surface0 px-3 py-2 text-sm text-subtext hover:bg-mauve/20 hover:text-mauve"
        >
          <Shuffle size={15} /> Surprise me
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Stat icon={Clapperboard} label="Reels" value={fmt(stats?.total_reels ?? reels.length)} sub={`${starred} starred`} />
        <Stat icon={FolderTree} label="Categories" value={`${stats?.categories.length ?? 0}`} />
        <Stat icon={Tag} label="Tags" value={`${stats?.top_tags.length ?? 0}+`} />
        <Stat icon={Coins} label="Vision tokens" value={fmt((stats?.tokens_in ?? 0) + (stats?.tokens_out ?? 0))} sub={stats?.cost_usd ? `~$${stats.cost_usd.toFixed(2)}*` : ""} />
        <Stat icon={Hash} label="Top tag" value={stats?.top_tags?.[0]?.[0] ?? "—"} sub={stats?.top_tags?.[0] ? `${stats.top_tags[0][1]} reels` : ""} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-overlay0">Categories</h2>
          <div className="space-y-1.5">
            {(stats?.categories ?? []).map((c) => (
              <button key={c.genre} onClick={() => nav(`/reels`)} className="flex w-full items-center justify-between rounded-lg px-3 py-2 hover:bg-surface0">
                <span className="flex items-center gap-2 text-text"><Badge variant="genre">{c.genre}</Badge></span>
                <span className="text-sm text-overlay0">{c.reels} reels · ~${c.cost_usd.toFixed(2)}</span>
              </button>
            ))}
          </div>
        </div>
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-overlay0">Recently added</h2>
          <div className="grid grid-cols-4 gap-2">
            {recent.map((r) => (
              <button key={r.id} onClick={() => nav(`/reels?focus=${r.id}`)} className="overflow-hidden rounded-lg">
                <img src={api.media(r.id, "thumbnail")} alt="" className="h-24 w-full bg-surface0 object-cover hover:opacity-80" onError={(e) => ((e.target as HTMLImageElement).style.opacity = "0")} />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
