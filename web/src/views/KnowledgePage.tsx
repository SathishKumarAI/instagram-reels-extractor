import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Knowledge } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function KnowledgePage() {
  const [kb, setKb] = useState<Knowledge | null>(null);
  const [err, setErr] = useState<string>();

  useEffect(() => {
    api.knowledge().then(setKb).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <Shell><p className="text-red">{err}</p></Shell>;
  if (!kb) return <Shell><p className="text-overlay0">Loading…</p></Shell>;

  return (
    <Shell sub={`${kb.total_reels} reels · ${kb.topics.length} topics`}>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {kb.topics.map((t) => (
          <Card key={t.name}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="capitalize">{t.name}</CardTitle>
                <Badge variant="genre">{t.reel_count} reels</Badge>
              </div>
              {t.overview && <p className="mt-2 text-sm text-subtext">{t.overview}</p>}
            </CardHeader>
            <CardContent>
              {t.hashtags.length > 0 && (
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {t.hashtags.slice(0, 6).map((h) => (
                    <Badge key={h} variant="tag">#{h}</Badge>
                  ))}
                </div>
              )}
              {t.facts.length > 0 && (
                <ul className="mb-3 space-y-1.5">
                  {t.facts.slice(0, 5).map((f, i) => (
                    <li key={i} className="text-sm text-subtext">
                      <span className="text-overlay0">•</span> {f.text}{" "}
                      <Link to={`/reels?focus=${f.reel_id}`} className="text-blue hover:underline">
                        [{f.reel_id}]
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap gap-1.5">
                {t.reels.slice(0, 8).map((r) => (
                  <Link
                    key={r.id}
                    to={`/reels?focus=${r.id}`}
                    className="rounded-md bg-surface0 px-2 py-1 text-xs text-subtext hover:text-text"
                    title={r.title}
                  >
                    {r.title.slice(0, 24)}
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </Shell>
  );
}

function Shell({ children, sub }: { children: React.ReactNode; sub?: string }) {
  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-text">Knowledge Base</h1>
        {sub && <p className="text-sm text-overlay0">{sub}</p>}
      </div>
      {children}
    </div>
  );
}
