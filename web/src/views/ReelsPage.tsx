import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type ReelDetail, type ReelSummary } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { fmtNum } from "@/lib/utils";
import { ExternalLink, FileText, Heart, MessageCircle, X } from "lucide-react";

export default function ReelsPage() {
  const [reels, setReels] = useState<ReelSummary[]>([]);
  const [q, setQ] = useState("");
  const [params, setParams] = useSearchParams();
  const focus = params.get("focus");

  useEffect(() => {
    api.reels().then(setReels).catch(() => setReels([]));
  }, []);

  const filtered = reels.filter(
    (r) =>
      !q ||
      r.title.toLowerCase().includes(q.toLowerCase()) ||
      r.author.toLowerCase().includes(q.toLowerCase()) ||
      r.genre.toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <div className="p-6">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">Reels</h1>
          <p className="text-sm text-overlay0">{reels.length} archived</p>
        </div>
        <Input
          placeholder="Filter by title, author, genre…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-xs"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {filtered.map((r) => (
          <Card
            key={r.id}
            className="cursor-pointer overflow-hidden transition-colors hover:border-mauve"
            onClick={() => setParams({ focus: r.id })}
          >
            <img
              src={api.media(r.id, "thumbnail")}
              alt=""
              className="h-40 w-full bg-surface0 object-cover"
              onError={(e) => ((e.target as HTMLImageElement).style.opacity = "0")}
            />
            <CardContent>
              <div className="mb-1 flex items-center gap-2">
                {r.genre && <Badge variant="genre">{r.genre}</Badge>}
              </div>
              <div className="line-clamp-2 text-sm font-medium text-text">{r.title}</div>
              <div className="mt-1 text-xs text-overlay0">{r.author}</div>
              <div className="mt-2 flex gap-3 text-xs text-subtext">
                <span className="flex items-center gap-1"><Heart size={12} />{fmtNum(r.likes)}</span>
                <span className="flex items-center gap-1"><MessageCircle size={12} />{fmtNum(r.comments)}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {focus && <ReelDrawer id={focus} onClose={() => setParams({})} />}
    </div>
  );
}

function ReelDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const [r, setR] = useState<ReelDetail | null>(null);
  useEffect(() => {
    setR(null);
    api.reel(id).then(setR).catch(() => setR(null));
  }, [id]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-crust/60" onClick={onClose}>
      <div
        className="h-full w-full max-w-2xl overflow-y-auto border-l border-surface0 bg-base p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-xl font-bold text-text">{r?.title ?? id}</h2>
          <Button variant="ghost" size="icon" onClick={onClose}><X size={18} /></Button>
        </div>
        {!r ? (
          <p className="text-overlay0">Loading…</p>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2 text-sm text-subtext">
              {r.genre && <Badge variant="genre">{r.genre}</Badge>}
              <span>{r.author}</span>
              <a href={r.url} target="_blank" className="flex items-center gap-1 text-blue hover:underline">
                <ExternalLink size={13} /> original
              </a>
              {r.has_pdf && (
                <a href={api.media(r.id, "pdf")} target="_blank" className="flex items-center gap-1 text-peach hover:underline">
                  <FileText size={13} /> PDF
                </a>
              )}
            </div>

            {r.video_path && (
              <video src={api.media(r.id, "video")} controls className="w-full rounded-lg bg-crust" />
            )}

            {r.summary && (
              <Section title="Summary"><p className="text-sm text-subtext">{r.summary}</p></Section>
            )}

            {r.facts.length > 0 && (
              <Section title="Key facts (with provenance)">
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
              <Section title="Transcript"><p className="text-sm text-subtext">{r.transcript_text}</p></Section>
            )}

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
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-overlay0">{title}</h3>
      {children}
    </div>
  );
}
