# Prompt 08 — make cost legible

Written before the code. Raised by the owner: the Compare scoreboard's cost read
like a huge number, and "how much does each reel cost with each model?" had no
answer on screen.

---

**Role.** You are fixing a number a person has to trust. A cost that cannot be
explained is worse than no cost at all.

<context>
Three different things are all called "cost" today:
1. `claude-cli` — `total_cost_usd` straight from the CLI's JSON envelope. It
   prices the **whole CLI turn**: system prompt, tool schemas, cache reads, the
   frames. On a subscription no money moves; the number is what the same turn
   would cost on the API.
2. `api` — computed from `msg.usage` at hard-coded sonnet prices
   ($3/M in, $15/M out) in `_via_api`.
3. `local` — always 0.0. Real electricity, but nothing billed.
The scoreboard sums `cost_usd` per backend and the UI renders it raw:
`${b.cost_usd}` → `$13.2164`. There is no per-reel figure anywhere, and the
`/api/stats` line mixes the same estimate over the whole corpus.
</context>

<task>
Show cost per reel and cost total, formatted, with the method stated where it is
read — and write the method down in the docs.
</task>

<steps>
1. Scoreboard rows gain `cost_per_reel`.
2. The UI renders both to 2 decimals for dollars, 4 for sub-cent figures, and
   labels the column so it cannot be read as a running bill.
3. A footnote under the table states what each backend's number means, in one
   sentence each.
4. `docs/research/COSTS.md`: where every number comes from, why claude-cli's
   input tokens are an upper bound, and what "free" means for a local model.
5. The bench report carries the same per-reel figure.
</steps>

<must>
- Never present a claude-cli figure as money actually spent on a subscription.
- State the sample size beside any average.
- One test: the scoreboard's per-reel cost equals total / reels.
</must>

<must-not>
- Do not invent a local-model cost from electricity guesses; say $0 and explain.
- Do not hide the total — the owner asked for both.
</must-not>

---

## Outcome

`cost_per_reel` in `compare.scoreboard`, formatted cost cells + footnote in
`ComparePage.tsx`, `docs/research/COSTS.md`, a test in `tests/test_compare.py`.
