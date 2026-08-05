import { useEffect, useState } from "react";
import {
  api,
  type BatchStatus,
  type CompareResult,
  type ReelSummary,
  type Scoreboard,
  type Variant,
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Cloud, Cpu, Play, Scale, X } from "lucide-react";

const ICON: Record<string, typeof Cloud> = { "claude-cli": Cloud, local: Cpu };

function Metric({ label, a, b, better }: {
  label: string; a: number | string; b: number | string; better?: "high" | "low";
}) {
  const na = typeof a === "number" ? a : NaN;
  const nb = typeof b === "number" ? b : NaN;
  let winner: "a" | "b" | null = null;
  if (better && !Number.isNaN(na) && !Number.isNaN(nb) && na !== nb) {
    winner = (better === "high") === (na > nb) ? "a" : "b";
  }
  const cell = (v: number | string, side: "a" | "b") => (
    <span className={winner === side ? "font-semibold text-green" : "text-subtext"}>{v}</span>
  );
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-surface0 py-1.5 text-sm last:border-0">
      <span className="text-overlay0">{label}</span>
      <span className="flex gap-6 tabular-nums">{cell(a, "a")}{cell(b, "b")}</span>
    </div>
  );
}

function VariantCard({ v }: { v: Variant }) {
  const Icon = ICON[v.backend] ?? Cloud;
  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <div className="flex items-center gap-2">
          <Icon size={16} className="text-mauve" />
          <span className="font-medium text-text">{v.backend}</span>
          <span className="text-xs text-overlay0">{v.model}</span>
          <span className="ml-auto text-xs text-overlay0">
            {v.elapsed_s}s · {v.frames} frames
            {Number(v.tokens?.cost_usd) > 0 ? ` · $${v.tokens.cost_usd}` : " · $0"}
          </span>
        </div>
        <p className="text-sm leading-relaxed text-subtext">{v.summary || "—"}</p>
        <div className="flex flex-wrap gap-1.5">
          {v.tags.map((t) => (
            <span key={t} className="rounded-md bg-surface0 px-1.5 py-0.5 text-xs text-subtext">{t}</span>
          ))}
        </div>
        <ol className="space-y-1 text-xs text-subtext">
          {v.facts.map((f, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-overlay0">{i + 1}.</span>
              <span>{f.text}</span>
            </li>
          ))}
          {v.facts.length === 0 && <li className="text-overlay0">no facts returned</li>}
        </ol>
      </CardContent>
    </Card>
  );
}

function Diff({ result }: { result: CompareResult }) {
  const d = result.diff;
  if (!d?.a || !d?.b) return null;
  const col = (title: string, items: string[], tone: string) => (
    <div className="min-w-0 flex-1">
      <div className={`mb-1.5 text-xs font-medium ${tone}`}>{title} ({items.length})</div>
      <ul className="space-y-1 text-xs text-subtext">
        {items.map((t, i) => <li key={i}>· {t}</li>)}
        {items.length === 0 && <li className="text-overlay0">none</li>}
      </ul>
    </div>
  );
  return (
    <Card className="mt-4">
      <CardContent className="pt-5">
        <div className="mb-3 text-sm font-medium text-text">
          Claim diff — what one model saw and the other did not
        </div>
        <div className="flex flex-wrap gap-6">
          {col(`only ${d.a}`, d.only_a ?? [], "text-peach")}
          {col(`only ${d.b}`, d.only_b ?? [], "text-blue")}
          {col("agreed", (d.shared ?? []).map((s) => s.a), "text-green")}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ComparePage() {
  const [reels, setReels] = useState<ReelSummary[]>([]);
  const [reelId, setReelId] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [board, setBoard] = useState<Scoreboard | null>(null);
  const [batch, setBatch] = useState<BatchStatus | null>(null);
  const [n, setN] = useState(10);

  const loadBoard = () => api.scoreboard().then(setBoard).catch(() => {});
  useEffect(() => {
    api.reels().then((r) => { setReels(r); if (r.length) setReelId(r[0].id); }).catch(() => {});
    loadBoard();
    const id = setInterval(() => {
      api.compareStatus().then((s) => {
        setBatch(s);
        if (!s.running) loadBoard();
      }).catch(() => {});
    }, 3000);
    return () => clearInterval(id);
  }, []);

  const runOne = async () => {
    if (!reelId) return;
    setBusy(true); setErr(""); setResult(null);
    try {
      setResult(await api.compare(reelId));
      loadBoard();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "compare failed");
    } finally { setBusy(false); }
  };

  const runBatch = async () => {
    setErr("");
    try { setBatch(await api.compareBatch(n)); }
    catch (e) { setErr(e instanceof Error ? e.message : "batch failed"); }
  };

  const names = result ? Object.keys(result.variants) : [];
  const [va, vb] = names.map((k) => result!.variants[k]);

  return (
    <div className="p-6">
      <div className="mb-1 flex items-center gap-2">
        <Scale size={20} className="text-mauve" />
        <h1 className="text-2xl font-bold text-text">Compare</h1>
      </div>
      <p className="mb-5 text-sm text-overlay0">
        Same reel, same frames, two models. The claim diff below is the part that matters —
        it shows what the free local model actually misses.
      </p>

      {/* act */}
      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-center gap-3 pt-5">
          <select
            value={reelId}
            onChange={(e) => setReelId(e.target.value)}
            className="max-w-sm flex-1 rounded-md border border-surface0 bg-base px-3 py-2 text-sm text-text"
          >
            {reels.map((r) => (
              <option key={r.id} value={r.id}>{r.title?.slice(0, 70) || r.id}</option>
            ))}
          </select>
          <Button onClick={runOne} disabled={busy || !reelId}>
            <Play size={14} /> {busy ? "Running both…" : "Compare this reel"}
          </Button>
          <span className="text-xs text-overlay0">~35s — Claude is the slow half</span>
        </CardContent>
      </Card>

      {err && <p className="mb-3 text-sm text-red">{err}</p>}
      {result && Object.entries(result.errors).map(([b, e]) => (
        <p key={b} className="mb-2 text-sm text-red">{b}: {e}</p>
      ))}

      {result && va && vb && (
        <>
          <Card className="mb-4">
            <CardContent className="pt-5">
              <div className="mb-2 flex justify-end gap-6 text-xs font-medium text-overlay0">
                <span>{va.backend}</span><span>{vb.backend}</span>
              </div>
              <Metric label="facts" a={va.facts.length} b={vb.facts.length} better="high" />
              <Metric label="tags" a={va.tags.length} b={vb.tags.length} better="high" />
              <Metric label="summary chars" a={va.summary.length} b={vb.summary.length} better="high" />
              <Metric label="structured fields" a={Object.keys(va.structured || {}).length} b={Object.keys(vb.structured || {}).length} better="high" />
              <Metric label="seconds" a={va.elapsed_s} b={vb.elapsed_s} better="low" />
              <Metric label="cost $" a={Number(va.tokens?.cost_usd ?? 0)} b={Number(vb.tokens?.cost_usd ?? 0)} better="low" />
            </CardContent>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <VariantCard v={va} />
            <VariantCard v={vb} />
          </div>
          <Diff result={result} />
        </>
      )}

      {/* review — the scoreboard is what decides the default backend */}
      <Card className="mt-6">
        <CardContent className="pt-5">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium text-text">Scoreboard</span>
            <span className="text-xs text-overlay0">
              {board?.reels_compared ?? 0} reel(s) compared
              {board?.avg_disagreement != null &&
                ` · ${Math.round(board.avg_disagreement * 100)}% of claims disputed`}
            </span>
            <div className="ml-auto flex items-center gap-2">
              <Input
                type="number"
                value={n}
                min={1}
                max={200}
                onChange={(e) => setN(Number(e.target.value))}
                className="w-20"
              />
              <span className="text-xs text-overlay0">
                ≈ ${(n * 0.39).toFixed(2)} of Claude quota
              </span>
              {batch?.running ? (
                <Button variant="ghost" onClick={() => api.compareCancel().then(setBatch)}>
                  <X size={14} /> Stop ({batch.done}/{batch.total})
                </Button>
              ) : (
                <Button onClick={runBatch}><Play size={14} /> Batch compare</Button>
              )}
            </div>
          </div>

          {batch?.running && (
            <div className="mb-3">
              <div className="h-1.5 overflow-hidden rounded-full bg-surface0">
                <div
                  className="h-full bg-mauve transition-all"
                  style={{ width: `${Math.round((batch.done / Math.max(1, batch.total)) * 100)}%` }}
                />
              </div>
              <div className="mt-1 text-xs text-overlay0">{batch.current || "starting…"}</div>
            </div>
          )}

          {board && board.backends.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-overlay0">
                  <tr>
                    <th className="py-1 pr-3 font-medium">Backend</th>
                    <th className="py-1 pr-3 font-medium">Reels</th>
                    <th className="py-1 pr-3 font-medium">Facts</th>
                    <th className="py-1 pr-3 font-medium">Tags</th>
                    <th className="py-1 pr-3 font-medium">Summary</th>
                    <th className="py-1 pr-3 font-medium">Fields</th>
                    <th className="py-1 pr-3 font-medium">Sec</th>
                    <th className="py-1 font-medium">Cost</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {board.backends.map((b) => (
                    <tr key={b.backend} className="border-t border-surface0">
                      <td className="py-1.5 pr-3">
                        <div className="text-text">{b.backend}</div>
                        <div className="text-xs text-overlay0">{b.model}</div>
                      </td>
                      <td className="py-1.5 pr-3 text-subtext">{b.reels}</td>
                      <td className="py-1.5 pr-3 text-subtext">{b.avg_facts}</td>
                      <td className="py-1.5 pr-3 text-subtext">{b.avg_tags}</td>
                      <td className="py-1.5 pr-3 text-subtext">{b.avg_summary_chars}</td>
                      <td className="py-1.5 pr-3 text-subtext">{b.avg_structured_fields}</td>
                      <td className="py-1.5 pr-3 text-subtext">{b.avg_seconds}</td>
                      <td className={`py-1.5 ${b.cost_usd > 0 ? "text-peach" : "text-green"}`}>
                        ${b.cost_usd}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-overlay0">
              Nothing compared yet. Run a batch — averages over one reel are not evidence.
            </p>
          )}
          {batch?.errors?.length ? (
            <p className="mt-2 text-xs text-red">{batch.errors.length} error(s): {batch.errors[0]}</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
