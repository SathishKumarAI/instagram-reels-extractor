"""Replace real collection names / handles / ids in tracked files with stand-ins.

`sources.json` is gitignored, but docs, comments, tests and examples slowly
accumulate the real names — and some of them (health conditions, a job search)
say more about the owner than the code does. Run this before publishing, and
after any doc-writing session.

    python scripts/scrub-personal.py [--check]

--check exits 1 if anything would change, so CI can gate on it.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# real -> stand-in. Add to this as collections are created; the point is that the
# published repo reads as a generic tool, not as a profile of its owner.
SUBSTITUTIONS = {
    "phd-opportunities": "topic-research",
    "internships": "topic-jobs",
    "me-challenging-me": "topic-habits",
    "core-workouts": "topic-fitness",
    "polymetrics": "topic-drills",
    "books-to-read": "topic-books",
    "tech-guff": "example-profile",
    "_tech_guff_": "some_creator",
    "sathish_786_": "your-handle",
    "18354529171213909": "10000000000000001",
    "17949637341189585": "10000000000000002",
    "18050573570734007": "10000000000000003",
    "18095255279194694": "10000000000000004",
}
EXTS = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ".ts", ".tsx"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    args = ap.parse_args()

    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stdout.split()
    # untracked docs count too — they are about to be committed
    files += [str(p) for p in Path("docs").glob("*.md")] + ["STATUS.md", "CLAUDE.md"]

    hits: dict[str, int] = {}
    for f in sorted(set(files)):
        p = Path(f)
        if not p.is_file() or p.suffix not in EXTS or p.name == Path(__file__).name:
            continue
        before = p.read_text(encoding="utf-8", errors="replace")
        after = before
        for real, stand_in in SUBSTITUTIONS.items():
            after = re.sub(rf"\b{re.escape(real)}\b", stand_in, after)
        if after != before:
            hits[f] = sum(1 for r in SUBSTITUTIONS if re.search(rf"\b{re.escape(r)}\b", before))
            if not args.check:
                p.write_text(after, encoding="utf-8")

    for f, n in hits.items():
        print(f"{n:2d} pattern(s)  {f}")
    if args.check and hits:
        print(f"\n{len(hits)} file(s) still carry personal names — run without --check")
        return 1
    print(f"{len(hits)} file(s) {'would be' if args.check else ''} scrubbed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
