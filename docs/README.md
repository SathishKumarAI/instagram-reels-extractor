# Documentation index

> Every document in this repo, what question it answers, and whether it is still true.
> Start with the path that matches what you are doing — not with the file list.

## Start here

| I want to… | Read, in this order |
|---|---|
| **Get it running** | [SETUP.md](SETUP.md) → [INSTAGRAM-ACCESS.md](INSTAGRAM-ACCESS.md) → [SYNC.md](SYNC.md) |
| **Use it day to day** | [USAGE.md](USAGE.md) → [../README.md](../README.md#when-something-goes-wrong) |
| **Run vision for free on my own GPU** | [LOCAL-VISION.md](LOCAL-VISION.md) → [research/MODELS.md](research/MODELS.md) |
| **Change the code** | [ARCHITECTURE.md](ARCHITECTURE.md) → the `change → file` table in the package README → [../CLAUDE.md](../CLAUDE.md) |
| **Change what the model extracts** | [research/CAPTION-ABLATION-2026-08-20.md](research/CAPTION-ABLATION-2026-08-20.md) → `.claude/skills/measuring-extraction-changes/` |
| **Publish this repo** | [PRIVACY.md](PRIVACY.md#before-making-the-repo-public) |
| **Know where work stopped** | [../STATUS.md](../STATUS.md) → [WORKLOG.md](WORKLOG.md) |

## Operating the tool

| Doc | Answers |
|---|---|
| [SETUP.md](SETUP.md) | Fresh machine to working install: Windows script, Linux venv, hooks, health check, local model |
| [INSTAGRAM-ACCESS.md](INSTAGRAM-ACCESS.md) | The four ways to hand it a session, their blast radius, hardening, and what "Exceeded 30 redirects" means |
| [SYNC.md](SYNC.md) | Why sync never duplicates a reel, what one run does, and the two-track (lean / heavy) environment |
| [USAGE.md](USAGE.md) | Every command, every `config.yaml` knob, and the gotcha table |
| [LOCAL-VISION.md](LOCAL-VISION.md) | Serving an open-weights VLM yourself and pointing the pipeline at it |
| [PRIVACY.md](PRIVACY.md) | What is private, the single egress point, the git guard rails, the pre-publish checklist |
| [DEPLOY.md](DEPLOY.md) | Docker with your data bind-mounted, and the Claude-CLI-in-a-container gotcha |

## Understanding the system

| Doc | Answers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Module map, what each package must **not** do, data flow, the backend/frontend JSON contract |
| [SCALING.md](SCALING.md) | How ~100 reels/hour is reached around a vision stage that throttles past 2 parallel calls |
| [OPTIMIZATION.md](OPTIMIZATION.md) | Where the vision cost goes (frames, tokens) and which knobs actually move it |
| [PRD.md](PRD.md) | The product intent: a private, searchable knowledge base you own |
| [PLAN-2026-08.md](PLAN-2026-08.md) | The current requirements and phasing, written after the Windows port |
| [BACKLOG-120.md](BACKLOG-120.md) | The live feature list — 174 items across 12 epics, with priority/effort/value |
| [WORKFLOW-RESEARCH.md](WORKFLOW-RESEARCH.md) | The 2026-08-04 diagnosis: why outputs read vague, and the transcript/OCR coverage gaps |
| [WORKLOG.md](WORKLOG.md) | Dated session log — what changed, and what it measured |

### Code-level maps

Each of these is a `change → file` table. Read the table instead of the code.

| Map | Covers |
|---|---|
| [`src/reels_scrap/extract/README.md`](../src/reels_scrap/extract/README.md) | prompts, JSON salvage, backends, frames, transcript, OCR |
| [`src/reels_scrap/api/README.md`](../src/reels_scrap/api/README.md) | every HTTP route group, and the `127.0.0.1`-only rule |
| [`src/reels_scrap/cli/README.md`](../src/reels_scrap/cli/README.md) | which file owns which command, and the exit codes |
| [`.claude/skills/README.md`](../.claude/skills/README.md) | the two project-scoped agent skills and their status |

## The research project

Which vision model should read a reel, and **why** do models disagree about what a reel
says? [research/README.md](research/README.md) is the entry point.

| Doc | Holds |
|---|---|
| [research/README.md](research/README.md) | Method, the rules the project keeps, and the map of the folder |
| [research/PLAN.md](research/PLAN.md) | Six phases, what each had to prove, and who decided what |
| [research/MODELS.md](research/MODELS.md) | Every model: architecture, role in the experiment, and the knobs that change its answer |
| [research/COSTS.md](research/COSTS.md) | Three different things called "cost", and where each number is produced |
| [research/UI-TABS.md](research/UI-TABS.md) | All 13 tabs: what each reads and the one thing worth knowing |
| [research/BENCH-2026-08-06.md](research/BENCH-2026-08-06.md) | **The current bench** — 8 arms, 30 reels, identical frames, plus the written why-they-differ pass |
| [research/BENCH-2026-08-05.md](research/BENCH-2026-08-05.md) | The first run, kept for comparison |
| [research/CAPTION-ABLATION-2026-08-20.md](research/CAPTION-ABLATION-2026-08-20.md) | Does the caption reach the model? — and the same-day correction that split the metric by marker kind |
| [research/OCR-IN-PROMPT-2026-08-20.md](research/OCR-IN-PROMPT-2026-08-20.md) | The OCR stage wrote to nothing for months; what feeding it back cost and gained |
| [research/prompts/](research/prompts/) | One file per build step: the prompt written **before** the code |

## How decisions get made here

The rules below are why the numbers in these docs can be trusted — and why some
questions are still open rather than quietly answered.

| Rule | Why it exists |
|---|---|
| **Measure, do not infer.** | Reading a config and believing it behaves that way is how a session gets burned. `frame_max_width: 1440` *looked* better and lost to 720 on every metric. |
| **The bench produces evidence; it does not decide.** | Switching the production backend is a separate, deliberate change made by the owner — never a side effect of a good-looking table. |
| **Failures are data.** | A model that fails a reel gets an error row, not a quietly thinner average. `deepseek-ocr` is reported as an abandoned arm, not omitted. |
| **Never trust an aggregate.** | "Sponsorship recall 0.169 → 0.453" was mostly hashtag copying. Split by marker kind, v1 had made sponsorship *worse*. The harness now reports `by_kind` so no future change is judged on the aggregate. |
| **One variable at a time.** | The bench reuses one seeded, stratified sample and identical cached frames, so the model is the only thing that changed. |
| **State the ceiling.** | A collection is only visible as deep as the saved-feed scan (`COLLECTION_SCAN = 1000`). Saying so is cheaper than a mystery later. |
| **A found bug gets fixed or filed, never silently left.** | Nine pipeline bugs surfaced from running one experiment for real — each had been making some model look worse than it is. |

**Open decisions, which are the owner's to make** (both from [../STATUS.md](../STATUS.md)):

1. Does a local model become the sync default? The evidence is gathered; the call is not made.
2. Re-extract the back catalogue under the new prompt, or improve only going forward?
   719 of 755 records predate the prompt changes.

## Historical — kept for the reasoning, not as instructions

These describe earlier states of the project. Read them for *why* something was done;
do **not** follow their commands.

| Doc | Superseded by |
|---|---|
| [../SUMMARY.md](../SUMMARY.md) (2026-06-18) | [../README.md](../README.md) + [ARCHITECTURE.md](ARCHITECTURE.md) |
| [../TICKETS.md](../TICKETS.md) | [BACKLOG-120.md](BACKLOG-120.md) |
| [PROJECT-STATUS.md](PROJECT-STATUS.md) (2026-07-11) | [../STATUS.md](../STATUS.md) |
| [BACKLOG.md](BACKLOG.md), [BACKLOG-50.md](BACKLOG-50.md) | [BACKLOG-120.md](BACKLOG-120.md) |
| [superpowers/specs/](superpowers/specs/) | the shipped system — kept as the approved design that preceded it |
| [`prompts/`](../prompts/) | rebuild-from-scratch prompt templates, one per subsystem |

## External resources worth having open

| Link | For |
|---|---|
| [yt-dlp cookies guide](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp) | exporting a Netscape `cookies.txt` correctly |
| [yt-dlp #10927](https://github.com/yt-dlp/yt-dlp/issues/10927) | why Chrome cookie extraction cannot work on Windows |
| [Ollama](https://ollama.com) · [model library](https://ollama.com/library) | serving the local vision model |
| [Qwen2.5-VL](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) | the weights behind the `reels-vision` build |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | the transcript stage (CTranslate2, not torch) |
| [fastembed](https://github.com/qdrant/fastembed) | the local embedding model behind search |
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | the CLI the cloud vision path drives |
| [mkdocs-material](https://squidfunk.github.io/mkdocs-material/) | the rendered docs site |

## House style for these docs

Anything added here should match what is already true of them:

- **Lead with the answer.** The first paragraph says what the page is for; the table
  follows. No warm-up.
- **Tables over prose** for anything enumerable — knobs, endpoints, symptoms, files.
- **Numbers carry their source.** "5.2 facts/reel" is followed by the sample size and
  the run that produced it, or it does not appear.
- **Say the trap.** Every page that can waste an hour names how, in the words that
  appear on screen when it happens.
- **When a change invalidates a doc, fix the doc in the same commit.** A stale map costs
  more than no map.
