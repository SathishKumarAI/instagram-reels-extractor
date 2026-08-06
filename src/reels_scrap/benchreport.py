"""Turn stored variants into a report: the numbers, then why the numbers differ.

The numbers come from code. The narrative comes from a model reading the actual
claims the arms disagreed on — and ships next to the numbers so any sentence in it
can be checked against them. If the analysis call fails, the report still stands;
it just says so.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .config import Config
from .observability import log

REPORT_DIR = Path("docs/research")

ANALYSIS_PROMPT = """You are analysing why different vision-language models describe the same short video differently.

Each example below is one reel. `reference` is what a large cloud model (claude-sonnet-4-6) extracted; `candidate` is what a smaller local model extracted from the identical frames and transcript. `only_reference` are claims the reference made that the candidate did not; `only_candidate` the reverse.

<examples>
{examples}
</examples>

For each model named in the examples, answer in at most 120 words:
1. What kind of claim does it systematically miss? Quote one.
2. What does it add that the reference did not? Quote one, and say whether it looks grounded in the frames or invented.
3. The single most likely mechanical cause - resolution of on-screen text, context length, instruction following, or world knowledge.

Then, in at most 150 words, state what the evidence supports about which model to use for this corpus, and what it does not support.

MUST: ground every statement in a quoted claim from the examples.
MUST NOT: speculate about training data, or rank models on anything the examples do not show.
Write markdown with a `### <model>` heading per model."""


def analyse(examples: list[dict], backend: str = "claude-cli") -> str:
    """Ask Claude to explain the disagreements. Returns "" when unavailable."""
    from .llm import LLMError, claude_text

    if not examples:
        return ""
    payload = json.dumps(examples, indent=1, ensure_ascii=False)
    try:
        return claude_text(
            ANALYSIS_PROMPT.format(examples=payload), backend=backend, max_tokens=2000
        ).strip()
    except (LLMError, Exception) as e:      # a missing CLI must not lose the metrics
        log.warning("bench analysis unavailable: %s", e)
        return ""


_CAVEATS = """\
- **One variable.** Every arm ran over the same fixed sample, the same cached
  frames and the same prompt. Only the model changed.
- **`empty` is a failure that parsed.** A variant with no claims at all is
  counted here, not averaged in as a processed reel.
- **`salvaged` means the answer came out of a reasoning trace**, not a finished
  reply — a reasoning model whose budget ran out mid-thought.
- **Agreement is not accuracy.** It measures whether two models made the same
  claim, not whether either is right. Claims are matched by content: frame
  pointers ("Frame 3 shows…") and reporting verbs are stripped first, and two
  claims quoting the same on-screen label count as one.
- **The reference arm is not ground truth.** `claude-cli` is the arm the corpus
  was built with, so every other model is described relative to it.
- **Cost is a price, not a bill.** See `docs/research/COSTS.md`.
- **Seconds are wall-clock on one busy workstation** (RTX 5070 Ti, 16GB, one
  model resident at a time). Treat them as ratios, not benchmarks.
"""


def _metrics_table(rows: list[dict]) -> str:
    head = ("| model | reels | facts | tags | summary chars | structured fields | "
            "empty | salvaged | sec | $/reel |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n")
    body = "".join(
        f"| `{r['backend']}` | {r['reels']} | {r['avg_facts']} | {r['avg_tags']} | "
        f"{r['avg_summary_chars']} | {r['avg_structured_fields']} | "
        f"{r.get('empty', 0)} | {r.get('salvaged', 0)} | {r['avg_seconds']} | "
        f"${r.get('cost_per_reel', 0):.4f} |\n"
        for r in rows
    )
    return head + body


def _agreement_table(agree: dict[str, dict], reference: str) -> str:
    head = (f"| model | reels vs `{reference}` | agreement | missed/reel | added/reel |\n"
            "|---|---|---|---|---|\n")
    body = ""
    for e in sorted(agree.values(), key=lambda x: -(x["agreement"] or 0)):
        score = "no overlap" if e["agreement"] is None else f"{e['agreement']:.0%}"
        body += (f"| `{e['profile']}` | {e['reels']} | {score} | "
                 f"{e['missed_per_reel']} | {e['added_per_reel']} |\n")
    return head + body


def _runs_table(stats: dict[str, dict], scored: set[str], sample_size: int) -> str:
    if not stats:
        return "_No run log yet — variants were written before the bench existed._\n"
    head = "| model | reels ok | failed | avg sec | note |\n|---|---|---|---|---|\n"
    body = ""
    for k, v in sorted(stats.items()):
        attempted = v["ok"] + v["failed"]
        if k not in scored and v["ok"] == 0:
            note = f"**arm abandoned** — {attempted} attempts, no usable output"
        elif attempted < sample_size:
            note = f"stopped at {attempted}/{sample_size}"
        else:
            note = ""
        body += f"| `{k}` | {v['ok']} | {v['failed']} | {v['avg_seconds']} | {note} |\n"
    return head + body


def build_report(cfg: Config, with_analysis: bool = True, examples: int = 40,
                 reference: str = "claude-cli") -> str:
    from .bench import load_sample, run_stats
    from .compare import agreement, disagreement_examples, scoreboard

    try:
        sample = load_sample(cfg)
        reel_ids, strata = sample.reel_ids, sample.strata
    except FileNotFoundError:
        reel_ids, strata = None, {}

    board = scoreboard(cfg, reel_ids=reel_ids)
    agree = agreement(cfg, reference=reference, reel_ids=reel_ids)
    stats = run_stats(cfg)
    ex = disagreement_examples(cfg, reference=reference, limit=examples, reel_ids=reel_ids)
    narrative = analyse(ex) if with_analysis else ""

    today = datetime.now(tz=UTC).date().isoformat()
    strata_line = ", ".join(f"{k} {v}" for k, v in strata.items()) or "n/a"
    parts = [
        f"# Bench — vision models, {today}\n",
        "Generated by `reels-scrap bench report`. Method and prompts: "
        "`docs/research/README.md`, `docs/research/prompts/`.\n",
        f"- Sample: **{len(reel_ids) if reel_ids else 'whole corpus'}** reels ({strata_line})\n"
        f"- Reference arm: `{reference}`\n"
        f"- Reels carrying at least one variant: **{board['reels_compared']}**\n",
        "\n## Metrics\n\nEvery average is over the reels that arm actually produced. "
        "`local` is not a separate model: it is the same `reels-vision` weights as "
        "stored by the earlier corpus backfill, before this session's extraction "
        "fixes — keep it as a before/after, not as an eighth arm.\n\n",
        _metrics_table(board["backends"]),
        f"\n## Agreement with `{reference}`\n\n"
        "Claims are matched by containment, not exact text — the same claim phrased "
        "with more detail still counts as shared. Only reels where both arms "
        "produced a variant are counted.\n\n",
        _agreement_table(agree, reference),
        "\n## Attempts\n\nFailures are listed, not averaged away. One row per reel: "
        "an arm that was re-run after a fix counts once, at its latest result.\n\n",
        _runs_table(stats, {r["backend"] for r in board["backends"]},
                    len(reel_ids) if reel_ids else 0),
        "\n## How to read this\n\n" + _CAVEATS,
    ]
    if narrative:
        parts += [f"\n## Why they differ\n\nWritten from {len(ex)} disagreeing claims "
                  "sampled across the arms; every statement should be checkable against "
                  "the tables above.\n\n", narrative, "\n"]
    elif with_analysis:
        parts += ["\n## Why they differ\n\n_Analysis unavailable — the metrics above "
                  "stand on their own._\n"]
    return "".join(parts)


def write_report(cfg: Config, with_analysis: bool = True, examples: int = 40,
                 reference: str = "claude-cli", directory: Path = REPORT_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / f"BENCH-{datetime.now(tz=UTC).date().isoformat()}.md"
    p.write_text(build_report(cfg, with_analysis, examples, reference), encoding="utf-8")
    return p
