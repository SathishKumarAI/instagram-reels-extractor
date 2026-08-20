import { useEffect, useRef, useState } from "react";
import { api, type Source } from "@/lib/api";
import { ModelSelect, useProfiles } from "@/components/ModelSelect";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Download, Link2, Play, Plus, RefreshCw } from "lucide-react";

function SyncPanel() {
  const [backend, setBackend] = useState("claude-cli");
  const profiles = useProfiles();
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<string>("");
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  // resume the status view if a sync is already running (e.g. after a refresh)
  useEffect(() => {
    api.syncStatus().then((s) => { if (s.running) { setRunning(true); watch(); } }).catch(() => {});
    return () => { if (poll.current) clearInterval(poll.current); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const watch = () => {
    if (poll.current) clearInterval(poll.current);
    poll.current = setInterval(async () => {
      try {
        const s = await api.syncStatus();
        if (!s.running) {
          clearInterval(poll.current!); poll.current = null; setRunning(false);
          setStatus(s.error ? `failed: ${s.error}` : `done — ${s.ingested} new reel(s) across ${s.sources} source(s)`);
        } else {
          setStatus(`syncing via ${s.backend}…`);
        }
      } catch { /* keep polling */ }
    }, 2000);
  };

  const start = async () => {
    setStatus(""); setRunning(true);
    try {
      await api.sync(backend);
      setStatus(`started via ${backend}…`);
      watch();
    } catch (e) {
      setRunning(false);
      setStatus(e instanceof Error ? e.message : "failed to start");
    }
  };


  return (
    <Card className="mb-4">
      <CardContent className="space-y-3 pt-5">
        <div className="flex items-center gap-2 text-sm font-medium text-text">
          <RefreshCw size={16} /> Sync now — pull latest reels
        </div>
        <div className="text-xs text-overlay0">Model for this run:</div>
        <ModelSelect value={backend} onChange={setBackend} profiles={profiles} disabled={running} />
        <div className="flex items-center gap-3">
          <Button onClick={start} disabled={running}>
            <Play size={14} /> {running ? "Syncing…" : "Sync now"}
          </Button>
          {status && <span className="text-xs text-overlay0">{status}</span>}
        </div>
      </CardContent>
    </Card>
  );
}

function QuickAddReel() {
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    if (!url.trim()) return;
    setBusy(true); setMsg("");
    try {
      const r = await api.ingestUrl(url.trim());
      setMsg(r.note); setUrl("");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "failed");
    } finally { setBusy(false); }
  };
  return (
    <Card className="mb-4">
      <CardContent className="space-y-2 pt-5">
        <div className="flex items-center gap-2 text-sm font-medium text-text">
          <Download size={16} /> Quick-add one reel
        </div>
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="https://www.instagram.com/reel/…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && go()}
            className="max-w-md"
          />
          <Button onClick={go} disabled={busy || !url.trim()}>{busy ? "Adding…" : "Add"}</Button>
        </div>
        {msg && <p className="text-xs text-overlay0">{msg}</p>}
      </CardContent>
    </Card>
  );
}

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState("collection");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = () => api.sources().then(setSources).catch(() => setSources([]));
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!url.trim()) return;
    setBusy(true); setErr("");
    try {
      await api.addSource(url.trim(), name.trim(), type);
      setUrl(""); setName("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed to add");
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (s: Source) => {
    await api.toggleSource(s.name).catch(() => {});
    load();
  };

  const [syncing, setSyncing] = useState("");
  const [syncMsg, setSyncMsg] = useState<Record<string, string>>({});
  const syncOne = async (name: string) => {
    setSyncing(name);
    setSyncMsg((m) => ({ ...m, [name]: "starting…" }));
    try {
      await api.sync("claude-cli", [name]);
      const poll = setInterval(async () => {
        try {
          const st = await api.syncStatus();
          if (!st.running) {
            clearInterval(poll);
            setSyncing("");
            setSyncMsg((m) => ({ ...m, [name]: st.error ? `failed: ${st.error}` : `+${st.ingested} new` }));
            load();
          }
        } catch { /* keep polling */ }
      }, 2000);
    } catch (e) {
      setSyncing("");
      setSyncMsg((m) => ({ ...m, [name]: e instanceof Error ? e.message : "failed" }));
    }
  };

  return (
    <div className="p-6">
      <div className="mb-1 flex items-center gap-2">
        <h1 className="text-2xl font-bold text-text">Sources</h1>
      </div>
      <p className="mb-5 text-sm text-overlay0">
        Instagram saved-collection URLs to pull from. Saved to{" "}
        <code className="rounded bg-surface0 px-1">sources.json</code> — every{" "}
        <code className="rounded bg-surface0 px-1">reels-scrap sync</code> fetches the latest
        reels from each enabled source, deduped.
      </p>

      {/* sync now with backend choice */}
      <SyncPanel />

      {/* quick-add single reel */}
      <QuickAddReel />

      {/* add form */}
      <Card className="mb-6">
        <CardContent className="space-y-3 pt-5">
          <div className="flex items-center gap-2 text-sm font-medium text-text">
            <Plus size={16} /> Add a source
          </div>
          <Input
            placeholder="https://www.instagram.com/<you>/saved/<name>/<id>/"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <div className="flex flex-wrap gap-2">
            <Input
              placeholder="name (optional — auto from URL)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="max-w-xs"
            />
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="rounded-md border border-surface0 bg-base px-3 py-2 text-sm text-text"
            >
              <option value="collection">collection (reel)</option>
              <option value="saved">saved (reel)</option>
              <option value="urls">urls file (reel)</option>
              <option value="rss">rss / atom (text)</option>
              <option value="arxiv">arxiv (text)</option>
              <option value="github">github releases (text)</option>
            </select>
            <Button onClick={add} disabled={busy || !url.trim()}>
              {busy ? "Saving…" : "Save"}
            </Button>
          </div>
          {err && <p className="text-sm text-red">{err}</p>}
        </CardContent>
      </Card>

      {/* list */}
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm text-overlay0">{sources.length} registered</div>
        <Button variant="ghost" size="icon" onClick={load}><RefreshCw size={16} /></Button>
      </div>
      <div className="space-y-2">
        {sources.map((s) => (
          <Card key={s.name}>
            <CardContent className="flex items-center gap-3 py-3">
              <Link2 size={16} className="shrink-0 text-overlay0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-text">{s.name}</span>
                  <Badge variant="genre">{s.type}</Badge>
                  {s.reels != null && (
                    <span className="text-xs text-overlay0">{s.reels} reels</span>
                  )}
                  {s.last_run && (
                    <span className="text-xs text-overlay0">· synced {s.last_run}</span>
                  )}
                </div>
                <div className="truncate text-xs text-overlay0">{s.url}</div>
              </div>
              {syncMsg[s.name] && (
                <span className="shrink-0 text-xs text-overlay0">{syncMsg[s.name]}</span>
              )}
              <Button
                variant="ghost"
                size="sm"
                disabled={!!syncing}
                onClick={() => syncOne(s.name)}
                title="Sync just this source"
              >
                <Play size={13} /> {syncing === s.name ? "Syncing…" : "Sync"}
              </Button>
              <Button
                variant={s.enabled ? "default" : "ghost"}
                size="sm"
                onClick={() => toggle(s)}
              >
                {s.enabled ? "Enabled" : "Disabled"}
              </Button>
            </CardContent>
          </Card>
        ))}
        {sources.length === 0 && (
          <p className="text-sm text-overlay0">No sources yet. Add a saved-collection URL above.</p>
        )}
      </div>
    </div>
  );
}
