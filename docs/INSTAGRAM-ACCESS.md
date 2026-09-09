# Giving the tool access to your Instagram

> Four ways to hand this tool a logged-in session, what each one risks, how to harden
> it, and what to do when it stops working. **No password is ever typed into this tool
> — not in any of the four.**

Your saved reels and your collections are private. Instagram has **no official API that
exposes them**: the Basic Display API is retired, and the Graph API covers Business and
Creator publishing, not your own saved posts. So every path below reuses the session
your browser already has. That is a real trade-off, and this page states it rather than
hiding it.

## The four approaches

| | Exported `cookies.txt` | Browser extraction | instaloader session | No auth |
|---|---|---|---|---|
| Works on | everywhere | **Linux/macOS only** | everywhere | everywhere |
| Secret at rest | a file in the repo root | none — read live, held in memory | `~/.config/instaloader`, outside the repo | none |
| Reaches your saved reels | yes | yes | yes | **no** |
| Survives a reboot | yes | yes (browser keeps it) | yes | n/a |
| Effort to rotate | re-export | log out, log in | re-run `login` | n/a |
| Blast radius if leaked | **full account** | full account | full account | none |
| Pick it when | **Windows — the only path that works** | Linux, and you want nothing on disk | you want the secret outside the project | public reels by URL |

### 1. Exported `cookies.txt` — the Windows path

Chrome 127+ encrypts its cookie store app-bound, and yt-dlp cannot decrypt it
([yt-dlp #10927](https://github.com/yt-dlp/yt-dlp/issues/10927)). Closing Chrome does
not help; nor does running as administrator. Export instead:

1. Install a "Get cookies.txt" extension (pick one that is open source and exports the
   **Netscape** format).
2. Open `instagram.com` while logged in, export, and save the file as `cookies.txt` in
   the repo root.
3. Keep the `#HttpOnly_` rows — **that is where `sessionid` lives.** An export that
   strips them looks fine and fails with `no Instagram 'sessionid' cookie`.
4. Run with `--browser cookies.txt`, or set `auth.cookies_file: cookies.txt`
   (`config-local.yaml` already does).

```bash
PYTHONUTF8=1 .venv-win/Scripts/python.exe -m reels_scrap.cli sync -c config.yaml --browser cookies.txt
```

### 2. Browser extraction — Linux/macOS, nothing on disk

```yaml
auth:
  cookies_from_browser: "chrome"     # firefox | chrome | brave | edge
  browser_profile: "Default"         # name the profile — see below
```

The cookie is read out of the browser at run time and stays in memory. Two traps:

- **Name the profile.** Without one, yt-dlp picks the most-recently-used profile, which
  is often not the one logged into Instagram.
- On Linux, Chrome needs `secretstorage` (bundled) and the **browser closed** while the
  cookie is read.

### 3. instaloader session — the secret lives outside the repo

```bash
reels-scrap login <your-username>
```

This shells out to `instaloader --login`, which prompts for your password and 2FA
**interactively, locally**, and stores an encrypted session under
`~/.config/instaloader`. This codebase only ever *loads* that session; it never reads,
stores or logs a password. Then set `source.login: true` and `source.username` in your
config.

Worth choosing when you would rather no credential material sat inside a project
directory that you might zip, copy to another machine, or share.

### 4. No auth — public reels only

The default. Put public reel URLs in `reels.txt` and run the pipeline; yt-dlp fetches
them without any session. You lose access to your saved collections, which is most of
what this tool is for — but it is the only configuration with **zero** credential risk.

## The threat model, stated plainly

`sessionid` is not a read-only token scoped to saved posts. **It is your account.**
Anyone who holds a valid one can, without your password and without triggering 2FA:

- read your DMs, your saved collections, your close-friends lists;
- post, delete, follow, and message as you;
- keep doing all of that until that session is explicitly logged out.

Which is why the rules below are not decoration.

### Hardening checklist

- [ ] **Never** paste it into a chat, an issue, a screenshot, a log, a bug report or a
      commit. Not a fragment of it — the value is the whole secret.
- [ ] **Never** put it in a cloud-synced folder. A repo under OneDrive, Dropbox, iCloud
      or Google Drive uploads `cookies.txt` to a third party the moment you save it.
- [ ] **Never** back it up. A `cookies.txt.bak`, a dated copy, a `.zip` of the repo —
      each is a second live login with the same power and none of the protection.
      This repo gitignores `*.bak` and `cookies*.bak` for exactly that reason.
- [ ] **Tighten the file permissions** so other accounts on the machine cannot read it:

      ```powershell
      icacls cookies.txt /inheritance:r /grant:r "$($env:USERNAME):(R,W)"   # Windows
      ```

      ```bash
      chmod 600 cookies.txt                                                  # Linux/macOS
      ```

- [ ] **Enable the pre-commit hook** on every clone — it blocks the file, and the
      `sessionid`-shaped value, even via `git add -f`:

      ```bash
      git config core.hooksPath .githooks
      ```

- [ ] **Rotate on any doubt.** Instagram → Settings → Accounts Centre → Password and
      security → **Where you're logged in** → log out the session. That invalidates
      **every** copy of the cookie at once, everywhere, immediately. It is the only
      revocation that actually works: deleting the file does nothing to the session.

### What this tool does with it

| | |
|---|---|
| Reads it | to enumerate your saved feed and download reels you already saved |
| Sends it to | `instagram.com` only |
| Writes it | never — it is read, held in memory, and dropped |
| Logs it | never — errors print the *source* (`cookies.txt`), never the value |
| Egress | the cookie never leaves the machine; only sampled **frames** do, and only if you use cloud vision ([PRIVACY.md](PRIVACY.md#data-egress--the-one-external-call)) |

## When it expires

A session dies on its own schedule — a password change, a suspicious-login prompt, or
Instagram simply deciding. **The expiry timestamp inside `cookies.txt` is not the
answer**: a file claiming a 2027 expiry can already be dead, because the invalidation
happens server-side.

The symptom is unmistakable — **every** source fails identically:

```
auth: network error: Exceeded 30 redirects.
✗ saved-all: Exceeded 30 redirects.
✗ topic-research: Exceeded 30 redirects.
…20 identical lines…
0 new reel(s) ingested across 20 source(s).
```

Logged out, Instagram bounces the request around its login redirect until yt-dlp gives
up counting. Other faces of the same cause: `no Instagram 'sessionid' cookie`,
`status: fail` from `i.instagram.com`, or a collection page that returns logged-out HTML.

**Fix:** re-export `cookies.txt` (step 1 above) and re-run. Sync is incremental, so
nothing is lost and nothing is re-downloaded.

Check it before a long run rather than after:

```bash
curl "http://127.0.0.1:8000/api/health?deep=true"    # cookie age + a live session probe
```

## Rate limits are part of access

Instagram rate-limits hard, and a 429 while logged in is worse than a 429 while
anonymous. The rules this repo holds to:

- **Never parallelise Instagram calls.** Ingest is sequential on purpose; only
  extraction is concurrent.
- **Sleep between pages**, and **stop on the first `HTTP 429`** rather than hammering.
- `discover` reads more of Instagram than you do by hand — which is why it is opt-in,
  carries a request budget (`--max-requests`), and stops on the first 429.

## See also

- [PRIVACY.md](PRIVACY.md) — what is private, what leaves the machine, what git must never see
- [SETUP.md](SETUP.md) — the install this fits into
- [SYNC.md](SYNC.md) — what a sync run actually does with the session
- [README.md](../README.md#your-data-stays-yours) — the three layers keeping personal files out of git
