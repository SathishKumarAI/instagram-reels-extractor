import { useEffect, useState } from "react";
import { api, type Candidate, type DiscoverStatus } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Check, Clock, Compass, ExternalLink, Play, X } from "lucide-react";
import { CollectionDot, accentFor } from "@/components/TagChip";

const TEXT_FOR: Record<string, string> = {
  mauve: "text-mauve", green: "text-green", peach: "text-peach", blue: "text-blue",
  pink: "text-pink", yellow: "text-yellow", teal: "text-teal", lavender: "text-lavender",
  flamingo: "text-flamingo", sapphire: "text-sapphire", maroon: "text-maroon", sky: "text-sky",
};

function CandidateCard({ c, onAct }: { c: Candidate; onAct: (a: string) => void }) {
  const accent = TEXT_FOR[accentFor(c.collection || "")] ?? "text-mauve";
  return (
    <Card className="overflow-hidden">
      <CardContent className="space-y-2 pt-4">
        <div className="flex items-center gap-2 text-xs">
          <CollectionDot name={c.collection || ""} />
          <span className={accent}>{c.collection || "unmatched"}</span>
          <span className="text-overlay0">{(c.score * 100).toFixed(0)}% match</span>
          <a
            href={c.url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-overlay0 hover:text-text"
          >
            open <ExternalLink size={11} />
          </a>
        </div>
        <div className="text-sm font-medium text-text">@{c.author || "unknown"}</div>
        <p className="line-clamp-4 text-xs leading-relaxed text-subtext">
          {c.caption || <span className="text-overlay0">no caption</span>}
        </p>
        <div className="text-[11px] text-overlay0">{c.why || c.source}</div>
        <div className="flex gap-2 pt-1">
          <Button size="sm" onClick={() => onAct("accept")}><Check size={13} /> Save</Button>
          <Button variant="ghost" size="sm" onClick={() => onAct("reject")}>
            <X size={13} /> No
          </Button>
          <Button variant="ghost" size="sm" onClick={() => onAct("snooze")}>
            <Clock size={13} /> Later
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DiscoverPage() {
  const [rows, setRows] = useState<Candidate[]>([]);
  const [status, setStatus] = useState<DiscoverStatus | null>(null);
  const [budget, setBudget] = useState(40);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");

  const load = () => api.discover("new").then(setRows).catch(() => setRows([]));
  useEffect(() => {
    load();
    const id = setInterval(() => {
      api.discoverStatus().then((s) => {
        setStatus((prev) => {
          if (prev?.running && !s.running) load();   // a run just finished
          return s;
        });
      }).catch(() => {});
    }, 3000);
    return () => clearInterval(id);
  }, []);

  const run = async () => {
    setErr("");
    try { setStatus(await api.discoverRun(budget)); }
    catch (e) { setErr(e instanceof Error ? e.message : "failed to start"); }
  };

  const act = async (c: Candidate, action: string) => {
    setRows((r) => r.filter((x) => x.id !== c.id));      // optimistic
    try {
      await api.discoverAction(c.id, action);
      if (action === "accept") setNote(`queued @${c.author} — runs on the next sync`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "action failed");
      load();
    }
  };

  const s = status?.summary;
  return (
    <div className="p-6">
      <div className="mb-1 flex items-center gap-2">
        <Compass size={20} className="text-mauve" />
        <h1 className="text-2xl font-bold text-text">Discover</h1>
        {status?.running && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-green/15 px-2 py-0.5 text-xs text-green">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green" /> harvesting
          </span>
        )}
      </div>
      <p className="mb-4 text-sm text-overlay0">
        Reels from creators you already save and from your most-used tags, ranked against
        each collection locally. Nothing is downloaded until you press Save.
      </p>

      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-center gap-3 pt-5">
          <Button onClick={run} disabled={status?.running}>
            <Play size={14} /> {status?.running ? "Running…" : "Find candidates"}
          </Button>
          <label className="flex items-center gap-2 text-xs text-overlay0">
            request budget
            <Input
              type="number"
              min={5}
              max={200}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="w-20"
            />
          </label>
          <span className="text-xs text-overlay0">
            ~3s between calls · the run stops on the first HTTP 429
          </span>
          {s && !status?.running && (
            <span className="text-xs text-subtext">
              last run: {s.found} found · {s.kept} kept · {s.requests_used}/{s.request_budget} requests
              {s.stopped_early ? ` · stopped: ${s.stopped_early}` : ""}
            </span>
          )}
          {(err || status?.error) && <span className="text-xs text-red">{err || status?.error}</span>}
          {note && <span className="text-xs text-green">{note}</span>}
        </CardContent>
      </Card>

      {rows.length === 0 ? (
        <p className="text-sm text-overlay0">
          Nothing waiting. Run a harvest — or everything found so far has been triaged.
        </p>
      ) : (
        <>
          <div className="mb-2 text-sm text-overlay0">{rows.length} waiting for review</div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {rows.map((c) => (
              <CandidateCard key={c.id} c={c} onAct={(a) => act(c, a)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
