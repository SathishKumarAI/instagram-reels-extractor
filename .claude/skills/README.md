# .claude/skills — the two procedures this repo keeps getting wrong

Project-scoped skills. Claude Code loads them automatically for anyone working in
this repo; they travel with the clone, unlike `~/.claude/skills`.

| Skill | Loads when |
|---|---|
| `measuring-extraction-changes` | about to change the prompt, model, resolution, `max_tokens` or extraction inputs — or a record is missing something and nobody knows why |
| `splitting-oversized-modules` | a file passes ~500 lines, or one file holds several unrelated jobs |

Both are written from things that actually went wrong here on 2026-08-20:

- A prompt change was shipped on an aggregate metric that turned out to be
  measuring hashtag copying; the sub-population that mattered had got **worse**
  (`docs/research/CAPTION-ABLATION-2026-08-20.md`).
- A resolution experiment would have measured "no effect" because the frame cache
  ignored `max_width` — the cache would have answered, not the model.
- Splitting `cli.py` into `cli/` silently broke `python -m reels_scrap.cli`, the
  invocation every runbook uses.

**Status: not subagent-tested.** The skill-writing discipline says to run pressure
scenarios against a baseline before deploying a skill. These were written from
this session's evidence instead. Treat them as good notes, not as verified
behaviour change, until someone runs that test.
