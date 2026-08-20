# Plan — from "saved reels" to a research tool you can publish from

Written 2026-08-04 in response to two asks: **the outputs read vague and miss
on-screen text**, and **"can this become my own Google — pulling in relevant
material on its own, and feeding what I publish?"**

Nothing here is built yet. Review it, cut what you don't want, and I'll build the
parts you keep.

---

## 1. Why the output is vague — measured, not guessed

| signal | coverage | consequence |
|---|---|---|
| transcript text | **10.5%** (71/674) | for ~9 in 10 reels, **every spoken word is missing** |
| OCR text | **3.4%** (23/674) | on-screen text rests entirely on the vision model |
| frames extracted | 20.8 per reel | … but only **6 are sent** — 71% thrown away |
| reels over 30s | 77 | six frames covering ~64 seconds |
| summary length | 255 chars median | the schema literally asks for "1-2 factual sentences" |

Median reel is 38s. We look at it roughly **once every 8 seconds**. Burned-in
captions change every 1-3 seconds. So the model sees a slideshow of a video.

### The experiment that changed the diagnosis

Same reel (62s, a ranked list with burned-in captions), local model, 6 vs 16 frames:

```
 6 frames → 6 facts   "top 5 GITHUB REPOSITORIES" / "no. 1 PROJECT BASED LEARNING" / …
16 frames → 16 facts  "top 5 GITHUB REPOSITORIES" / "years now and" / "clutch" /
                      "aspiring" / "you'll ever" / "recommend" / …
```

**More frames made it worse.** The extra "facts" are fragments of auto-generated
subtitles caught mid-sentence. So the fix is *not* more frames.

What that tells us: the on-screen text you are watching is mostly the **spoken
audio rendered as subtitles**. Reading it frame-by-frame is a lossy way to
recover speech. The complete, ordered, punctuated version of that same content is
in the audio track — which we currently ignore for 89.5% of the corpus.

### So the quality plan is, in order of measured impact

| # | Change | Why it is first | Effort |
|---|---|---|---|
| Q1 | **Audio transcripts on the GPU** (`faster-whisper`, CUDA) | recovers the actual substance for ~600 reels that have none. The 5070 Ti idles today; `large-v3` runs faster than realtime | M |
| Q2 | **Split the prompt: overlay text vs subtitle stream** | tell the model that title cards/labels are *content* and subtitle lines are *speech* — stop it emitting "years now and" as a fact | S |
| Q3 | **Sample frames where the picture changes**, not every N seconds (`ffmpeg select='gt(scene,0.3)'`) | catches every title card and slide change; skips 15 near-identical frames of a talking head | M |
| Q4 | **Richer summary contract** — 3-5 sentences + `key_points[]` + a verbatim `on_screen_text` block | the current schema *asks* for vague. "1-2 factual sentences" is a spec, and we are meeting it | S |
| Q5 | **Fact hygiene** — drop fragments under N words, merge duplicates across frames | the 16-frame run showed exactly this failure mode | S |
| Q6 | **Quality score per record** (has transcript? facts ≥5? structured filled?) surfaced in the UI | makes thin records visible instead of silently wrong | S |
| Q7 | **Re-process the corpus** once Q1-Q5 land | ~674 reels × (whisper + vision) on GPU ≈ 3-4 hours, $0 | L |

Expected after Q1+Q4: summaries go from 255 chars of gist to a paragraph grounded
in what was actually *said*, plus the on-screen text quoted verbatim.

**Cost:** `faster-whisper` + CUDA wheels are a real install (~2GB) and the current
`.venv-win` has no torch. It is the single highest-value change on this list.

---

## 2. Getting material without you hunting for it

Today: you save reels by hand, the tool downloads what you saved. One direction,
one platform.

### Already built
- **Discovery** (`reels-scrap discover`) — candidates from your most-used hashtags
  and from creators you save repeatedly, scored locally against each collection's
  centroid. Request-budgeted, stops on the first HTTP 429.
- **Text sources already supported by the ingest layer**: `rss`, `arxiv`, `github`.
  These accept a URL and flow through the same pipeline — **no new code needed to
  start following Substacks and blogs today**, just `add-source <feed-url> --type rss`.

### Proposed additions

| # | Source | Why it fits | Effort |
|---|---|---|---|
| S1 | **Substack / any newsletter** via its RSS feed | already supported — needs a UI to add them and a "text" card design | S |
| S2 | **YouTube** (channel or playlist) | yt-dlp already downloads it; captions come free, so quality beats reels | M |
| S3 | **Instagram Explore feed** | already personalised to you; one more harvest signal for Discover | M |
| S4 | **Reddit / HN** by subreddit or keyword | JSON APIs, no auth, no rate-limit drama | S |
| S5 | **arXiv by topic** | supported type; wants a saved-query UI | S |
| S6 | **Podcast feeds** | audio → the same whisper path as Q1 | M |
| S7 | **A "read later" bookmarklet / paste box** | anything on the web, one paste, into the same corpus | S |

The point: one corpus, many sources, **one schema**. A Substack post and a reel
both become {summary, key points, facts with provenance, tags, collection}.

---

## 3. The "personal Google" layer

Retrieval today is one semantic index over summaries and facts. To make it the
thing you *reach for*:

| # | Capability | What it changes |
|---|---|---|
| R1 | **Hybrid search** (BM25 + vector) | exact names — a repo, a tool, a person — currently lose to fuzzy vector matches |
| R2 | **Local RAG chat** (retrieval → local model → citations) | ask questions of your corpus without Claude quota; Claude becomes an explicit "deep answer" button |
| R3 | **Entity extraction + linking** | every tool/repo/person/paper mentioned becomes a node; "everything I've saved about Claude Code" stops depending on tags |
| R4 | **Timeline view** | what you were interested in, month by month — your own trend line |
| R5 | **Contradiction / duplicate surfacing** | five reels making the same claim, or two disagreeing, shown as one card |
| R6 | **Weekly digest** | "here is what you saved, what it was about, what's worth acting on" as markdown |
| R7 | **Ask-across-sources** | one answer citing a reel, a Substack post and an arXiv paper together |

R1 and R2 are the two that change daily use. R3 is what makes it feel like a
research tool instead of a search box.

---

## 4. From research to output — what you publish

This is the part that turns a library into leverage.

| # | Feature | Flow |
|---|---|---|
| O1 | **Idea inbox** | mark any reel/fact "use this" → it lands in an ideas queue with its citation |
| O2 | **Cluster → draft** | pick a cluster ("AI coding tools, last 30 days") → a draft post with every claim linked to the reel and timestamp it came from |
| O3 | **Format targets** | same draft rendered for LinkedIn / X thread / newsletter / blog — different lengths, same citations |
| O4 | **Attribution built in** | every generated line keeps its source; nothing is publishable without provenance |
| O5 | **"What did I miss"** | before you post, show saved material on that topic you never opened |
| O6 | **Publish log** | what you posted, from which sources, when — so you don't repeat yourself |

O4 is the constraint that makes the rest safe: this corpus is other people's work.
Drafts must carry citations by construction, not by discipline.

---

## 5. Suggested order

**Track A — quality first (2-3 sessions).** Q1 → Q4 → Q2 → Q5 → Q6, then Q7
re-process. Everything downstream reads these records; improving retrieval before
the records are good is polish on sand.

**Track B — reach (1-2 sessions), can run in parallel.** S1 (Substack via RSS —
mostly UI), then S2 YouTube, then S4 Reddit/HN. Each is a source type plus a card.

**Track C — the research layer (2-3 sessions).** R1 hybrid search → R2 local RAG →
R6 weekly digest. R3 entity linking after, it is the biggest single piece.

**Track D — output (1-2 sessions).** O1 idea inbox → O2 cluster-to-draft with O4
citations. Only worth doing once A and C are real.

---

## 6. What I need from you

1. **Whisper install** — Track A hinges on it, and it puts ~2GB of CUDA wheels in
   the venv. Yes or no?
2. **Which sources actually matter** — name 3-5 Substacks/YouTube channels/
   subreddits you would want followed. Guessing here wastes a session.
3. **What you publish, and where** — the output track is shaped entirely by that.
   LinkedIn posts read nothing like a newsletter.
4. **Re-process appetite** — after Track A, 674 reels take 3-4 GPU hours at $0.
   Overnight run, or only new reels going forward?

Every item here is in `docs/BACKLOG-120.md` (Epics N-Q) so nothing depends on this
conversation surviving.
