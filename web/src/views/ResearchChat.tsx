import { useState } from "react";
import { api, type Answer } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Send, Loader2, ExternalLink } from "lucide-react";

interface Turn {
  role: "user" | "assistant";
  content: string;
  answer?: Answer;
}

export default function ResearchChat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  async function ask() {
    const question = q.trim();
    if (!question || busy) return;
    setQ("");
    setBusy(true);
    const history = turns.map((t) => ({ role: t.role, content: t.content }));
    setTurns((p) => [...p, { role: "user", content: question }]);
    try {
      const answer = await api.chat(question, history);
      setTurns((p) => [
        ...p,
        { role: "assistant", content: answer.answer ?? answer.note ?? "(no answer)", answer },
      ]);
    } catch (e) {
      setTurns((p) => [...p, { role: "assistant", content: `Error: ${e}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-surface0 p-6">
        <h1 className="text-2xl font-bold text-text">Research Chat</h1>
        <p className="text-sm text-overlay0">Ask questions across the reel archive — answers cite their sources.</p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {turns.length === 0 && (
          <p className="text-overlay0">Try: “What self-hosting tools were mentioned and what do they do?”</p>
        )}
        {turns.map((t, i) => (
          <div key={i} className={t.role === "user" ? "flex justify-end" : ""}>
            <div
              className={
                t.role === "user"
                  ? "max-w-[80%] rounded-xl bg-mauve/15 px-4 py-2 text-sm text-text"
                  : "max-w-[85%] space-y-3 rounded-xl bg-mantle px-4 py-3 text-sm text-subtext"
              }
            >
              <div className="whitespace-pre-wrap">{t.content}</div>
              {t.answer?.citations && t.answer.citations.length > 0 && (
                <div className="space-y-1.5 border-t border-surface0 pt-2">
                  <div className="text-xs uppercase tracking-wide text-overlay0">Sources</div>
                  {t.answer.citations.map((c) => (
                    <div key={c.reel_id} className="flex items-start gap-2 text-xs">
                      <Badge variant="score">{c.score.toFixed(2)}</Badge>
                      <a href={c.url} target="_blank" className="flex items-center gap-1 text-blue hover:underline">
                        {c.title.slice(0, 48)} <ExternalLink size={11} />
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-overlay0">
            <Loader2 className="animate-spin" size={16} /> synthesising…
          </div>
        )}
      </div>

      <div className="border-t border-surface0 p-4">
        <div className="flex gap-2">
          <Input
            placeholder="Ask a research question…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
          />
          <Button onClick={ask} disabled={busy}><Send size={16} /></Button>
        </div>
      </div>
    </div>
  );
}
