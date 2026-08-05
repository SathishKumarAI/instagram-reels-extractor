# Setup — from a fresh machine to a working install

Local-first: reels, transcripts, summaries and search all live on your machine.
The only optional egress is Claude vision, and there is a local GPU path that
removes even that.

## 0. What you need

| | Why | Skip if |
|---|---|---|
| Python 3.12+ | the pipeline | — |
| Node 20+ | the web UI | you only use the CLI |
| An Instagram account | reading **your own** saved reels | — |
| A GPU + [Ollama](https://ollama.com) | free local vision (~6s/reel) | you use Claude vision |
| Claude Code CLI or `ANTHROPIC_API_KEY` | cloud vision (richer records) | you use local vision |

## 1. Install

**Windows** — one script, idempotent:

```powershell
.\scripts\setup-windows.ps1              # venv + deps + web + git hooks + local model + tests
.\scripts\setup-windows.ps1 -Schedule    # …plus nightly sync and weekly discovery
.\scripts\setup-windows.ps1 -Autostart   # …plus API at logon
```

**Linux / macOS**:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[cpu]"
(cd web && npm install)
git config core.hooksPath .githooks      # blocks credentials from being committed
pytest -q
```

## 2. Give it your Instagram session

Everything private — saved collections, your own reels — needs your logged-in
session. **No password is ever entered into this tool.**

**Linux/macOS:** point `auth.cookies_from_browser` at a browser logged into
Instagram (`chrome`, `firefox`, …) and you are done.

**Windows:** browser extraction does not work. Chrome 127+ encrypts cookies
app-bound and yt-dlp cannot decrypt them ([yt-dlp #10927](https://github.com/yt-dlp/yt-dlp/issues/10927)) —
closing Chrome does not help. Export instead:

1. Install a "Get cookies.txt" browser extension.
2. Open `instagram.com` (logged in), export, save as `cookies.txt` in the repo root.
3. Run with `--browser cookies.txt` (or set `auth.cookies_file: cookies.txt`).

> **`cookies.txt` is a live login.** Anyone with it is signed into your Instagram
> until you log out. It is gitignored and blocked by the pre-commit hook. Never
> paste it into a chat, an issue, a screenshot or a log. Rotate by logging out.
> Full rules: [`PRIVACY.md`](PRIVACY.md).

## 3. Tell it what to read

```bash
reels-scrap add-source "https://www.instagram.com/<you>/saved/<name>/<id>/"
reels-scrap list-sources
```

A reel saved **without** picking a collection lands only in the default
"All Posts" feed. Register that too, or those reels are invisible:

```json
{"name": "saved-all", "url": "https://www.instagram.com/<you>/saved/all-posts/",
 "type": "saved", "enabled": true, "limit": 200}
```

`sources.json` is gitignored — it names your private collections. Commit
`sources.example.json` instead.

## 4. Run

```bash
# cloud vision (richer records, costs Claude quota)
reels-scrap sync -c config.yaml --browser cookies.txt

# local GPU vision (free, ~6s/reel, no egress)
reels-scrap sync -c config-local.yaml

# API + UI
reels-scrap serve -c config.yaml --port 8000
(cd web && npm run dev)          # http://localhost:5173
```

Sync is **idempotent and incremental** — re-run any time; nothing is
re-downloaded and failures land in a dead-letter you can retry with
`--retry-failed`.

## 5. Local vision on your own GPU

```powershell
winget install Ollama.Ollama
ollama pull qwen2.5vl:7b-q8_0
ollama create reels-vision -f scripts/ollama-vision.Modelfile
```

The Modelfile exists because stock `qwen2.5vl:7b` has a 4096-token context and
rejects six frames outright. It sets 32k context and q8 weights (~9.4GB VRAM).
Point `config-local.yaml` at your endpoint if it is not `127.0.0.1:11434`.

**What you give up going local** — measured on this corpus, same frames:

| | facts | tags | summary | structured fields | sec | cost |
|---|---|---|---|---|---|---|
| Claude (sonnet) | 7.0 | 6.0 | 286 chars | 4.25 | 19.2 | ~$0.39/reel |
| local (qwen2.5vl 7B q8) | 5.0 | 5.0 | 205 chars | 1.75 | 7.9 | $0 |

The local model also occasionally invents a name Claude leaves out. Use the
**Compare** tab to see the claim-level difference on your own reels before
deciding. Run both and keep both: records store one `variant` per backend.

## 6. Check it is healthy

```bash
curl "http://127.0.0.1:8000/api/health?deep=true"
```

Reports disk headroom, search-index freshness, cookie age, local-vision
reachability and (with `deep`) whether the Instagram session still works. An
expired cookie is the single most common cause of "everything broke".

## 7. Discovery (optional, opt-in)

```bash
reels-scrap discover --browser cookies.txt --max-requests 40
```

Proposes reels from creators you already save and from your most-used hashtags,
scored locally against each collection. Nothing downloads until you accept one in
the Discover tab.

Instagram rate-limits hard. Every run has a request budget, sleeps ~3s between
calls, and **stops on the first HTTP 429**. Discovery reads more of Instagram
than you do by hand — that is why it is opt-in and capped. Keep it that way.
