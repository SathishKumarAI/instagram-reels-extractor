import { useEffect, useRef, useState } from "react";
import { api, type SyncStatus } from "@/lib/api";
import { ModelSelect, useProfiles } from "@/components/ModelSelect";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Activity, Play } from "lucide-react";

const STAGE_LABEL: Record<string, string> = {
  enumerate: "Enumerate",
  ingest: "Download",
  process: "Extract + vision",
  site: "Docs",
  index: "Search index",
};
const STAGE_HINT: Record<string, string> = {
  enumerate: "read each saved collection",
  ingest: "yt-dlp pulls new reels",
  process: "frames → Claude vision",
  site: "rebuild docs + index pages",
  index: "embed for semantic search",
};

/** Live sync log: the newest lines, pinned to the bottom while it streams. */
function LogTail({ lines }: { lines: string[] }) {
  const box = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  const onScroll = () => {
    const el = box.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };
  useEffect(() => {
    const el = box.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <div
      ref={box}
      onScroll={onScroll}
      className="h-80 overflow-y-auto rounded-lg bg-crust p-3 font-mono text-[11px] leading-5 text-subtext"
    >
      {lines.length === 0 && <div className="text-overlay0">no run.log yet — start a sync</div>}
      {lines.map((l, i) => (
        <div
          key={i}
          className={
            /ERROR|failed/i.test(l) ? "text-red" : /INFO/.test(l) ? "" : "text-overlay0"
          }
        >
          {l}
        </div>
      ))}
    </div>
  );
}

function Pipeline({ s }: { s: SyncStatus }) {
  const stages = s.stages ?? [];
  const at = stages.indexOf(s.stage ?? "");
  const { done, total } = s.progress ?? {};
  return (
    <div className="flex flex-wrap gap-2">
      {stages.map((st, i) => {
        // done/current/pending is positional — the log only ever names one stage
        const state = at < 0 ? "pending" : i < at ? "done" : i === at ? "current" : "pending";
        return (
          <div
            key={st}
            className={`min-w-[9.5rem] flex-1 rounded-lg border p-3 ${
              state === "current"
                ? "border-mauve bg-mauve/10"
                : state === "done"
                  ? "border-green/40 bg-green/5"
                  : "border-surface0"
            }`}
          >
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${
                  state === "current"
                    ? "animate-pulse bg-mauve"
                    : state === "done"
                      ? "bg-green"
                      : "bg-surface2"
                }`}
              />
              <span
                className={`text-sm font-medium ${
                  state === "current" ? "text-mauve" : state === "done" ? "text-green" : "text-overlay0"
                }`}
              >
                {STAGE_LABEL[st] ?? st}
              </span>
            </div>
            <div className="mt-1 text-xs text-overlay0">{STAGE_HINT[st] ?? ""}</div>
            {state === "current" && total ? (
              <div className="mt-2">
                <div className="h-1.5 overflow-hidden rounded-full bg-surface0">
                  <div
                    className="h-full bg-mauve transition-all"
                    style={{ width: `${Math.round(((done ?? 0) / total) * 100)}%` }}
                  />
                </div>
                <div className="mt-1 text-xs text-mauve">
                  {done}/{total}
                </div>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function SourceTable({ s }: { s: SyncStatus }) {
  const rows = s.source_state ?? [];
  if (rows.length === 0) return <p className="text-sm text-overlay0">no sync has run yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-overlay0">
          <tr>
            <th className="py-1 pr-3 font-medium">Source</th>
            <th className="py-1 pr-3 font-medium">Seen</th>
            <th className="py-1 pr-3 font-medium">New</th>
            <th className="py-1 pr-3 font-medium">Ingested</th>
            <th className="py-1 pr-3 font-medium">Dead</th>
            <th className="py-1 font-medium">Last run</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-t border-surface0">
              <td className="py-1.5 pr-3">
                <div className="text-text">{r.name}</div>
                {r.error && <div className="text-xs text-red">{r.error}</div>}
              </td>
              <td className="py-1.5 pr-3 text-subtext">{r.current}</td>
              <td className="py-1.5 pr-3 text-subtext">{r.new || "—"}</td>
              <td className={`py-1.5 pr-3 ${r.ingested ? "text-green" : "text-overlay0"}`}>
                {r.ingested || "—"}
              </td>
              <td className={`py-1.5 pr-3 ${r.failed ? "text-peach" : "text-overlay0"}`}>
                {r.failed || "—"}
              </td>
              <td className="py-1.5 text-xs text-overlay0">{r.last_run ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SyncPage() {
  const [s, setS] = useState<SyncStatus | null>(null);
  const [backend, setBackend] = useState("claude-cli");
  const [err, setErr] = useState("");
  const profiles = useProfiles();

  useEffect(() => {
    let alive = true;
    const tick = () => api.syncStatus().then((x) => alive && setS(x)).catch(() => {});
    tick();
    // 2s while live, 10s when idle — polling a dead sync is pure waste
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const start = async () => {
    setErr("");
    try {
      await api.sync(backend);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed to start");
    }
  };

  const live = !!s?.live;
  const rows = s?.source_state ?? [];
  const totals = rows.reduce(
    (a, r) => ({
      ingested: a.ingested + r.ingested,
      failed: a.failed + r.failed,
      errors: a.errors + (r.error ? 1 : 0),
    }),
    { ingested: 0, failed: 0, errors: 0 },
  );
  const report = s?.report;

  return (
    <div className="p-6">
      <div className="mb-1 flex items-center gap-2">
        <h1 className="text-2xl font-bold text-text">Sync</h1>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs ${
            live ? "bg-green/15 text-green" : "bg-surface0 text-overlay0"
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${live ? "animate-pulse bg-green" : "bg-overlay0"}`} />
          {live ? "running" : "idle"}
        </span>
      </div>
      <p className="mb-5 text-sm text-overlay0">
        What the pipeline is doing right now. Follows syncs started here <em>and</em> from the
        CLI — both write <code className="rounded bg-surface0 px-1">output/run.log</code>.
      </p>

      {/* act */}
      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-center gap-3 pt-5">
          <Button onClick={start} disabled={live}>
            <Play size={14} /> {live ? "Syncing…" : "Sync now"}
          </Button>
          <ModelSelect
            value={backend}
            onChange={setBackend}
            profiles={profiles}
            disabled={live}
          />
          <span className="text-xs text-overlay0">
            {totals.ingested} ingested · {totals.failed} dead-lettered · {totals.errors} source
            error(s)
            {report?.summary ? ` · last run ${report.summary.clean}/${report.summary.total_reels} clean` : ""}
          </span>
          {(err || s?.error) && <span className="text-xs text-red">{err || s?.error}</span>}
        </CardContent>
      </Card>

      {/* pipeline */}
      <div className="mb-4">{s && <Pipeline s={s} />}</div>

      {/* review */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="pt-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-text">
              <Activity size={16} /> Live log
            </div>
            <LogTail lines={s?.log ?? []} />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <div className="mb-3 text-sm font-medium text-text">Per source — last run</div>
            <SourceTable s={s ?? ({} as SyncStatus)} />
            {report?.stages && (
              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                {Object.entries(report.stages).map(([stage, counts]) => (
                  <span key={stage} className="rounded-md bg-surface0 px-2 py-1 text-subtext">
                    {stage}: {counts.ok ?? 0} ok
                    {counts.error ? <span className="text-red"> · {counts.error} error</span> : null}
                  </span>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
