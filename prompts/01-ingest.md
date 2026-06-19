# Layer 01 — Ingest

You are a Python data-acquisition engineer. Your objective is to build the
`ingest/` package: pluggable fetchers that produce `Reel` records plus media on
disk from Instagram reels — public via yt-dlp, private/profile/hashtag/saved via
instaloader, and a named-collection fetcher that reads a private feed/collection
endpoint using exported browser cookies.

<context>
  <depends_on>
    Layer 00 exists: `core/models.Reel`, `core/config`, `core/paths`,
    `core/errors`, `core/observability`. Media goes under
    `paths.input_media` (reuse `reel_media_dir(id)`); records are saved via
    `Reel.save(paths.output_reels)`.
  </depends_on>
  <boundary>
    `ingest` returns `Reel` records + media on disk and knows NOTHING about
    extraction. It fills only identity + metadata + media-path fields of `Reel`.
    Extraction (transcript/ocr/vision) happens in Layer 02.
  </boundary>
  <id_scheme>
    `Reel.id` is the Instagram shortcode (e.g. the `C9xAbCdEfGh` in
    `instagram.com/reel/<code>/`). All fetchers MUST derive the same id for the
    same reel so stages dedupe and resume correctly.
  </id_scheme>
</context>

## Instructions
1. **`ingest/base.py`.** Define an abstract `Ingestor` interface:
   `fetch(self) -> Iterator[Reel]`, plus shared helpers: `shortcode_from_url`,
   `download_path(id)` (under `paths.input_media`), and a
   `dedupe(reel) -> bool` that skips reels whose `output/reels/<id>.json` already
   exists (resume-by-sidecar). Define a `make_ingestor(config) -> Ingestor`
   factory that dispatches on `config.source.type`.
2. **`ingest/ytdlp.py` — public reels.** `YtDlpIngestor` uses `yt-dlp` to
   download the mp4 + thumbnail and pull metadata (author/uploader, title,
   description→caption, view_count, like_count, duration, upload_date) without
   login. Source = a URL list file (`config.source.urls_file`, resolved under
   `paths.input_urls` and/or repo root). Map yt-dlp's `info` dict into a `Reel`;
   save media to `reel_media_dir(id)` and set `video_path`/`thumbnail_path`
   relative to `data_dir`. Support cookies (`config.auth.cookies_from_browser`
   or `cookies_file`) for reels that need a logged-in session, but do not
   require them.
3. **`ingest/instaloader_src.py` — private/profile/hashtag/saved.**
   `InstaloaderIngestor` handles `config.source.type` in
   {`profile`, `hashtag`, `saved`} and login-gated reels. Use `instaloader`:
   - load/reuse a session from `paths.input_cache` (don't re-login each run);
   - `profile`: iterate a target handle's reels up to `config.source.limit`;
   - `hashtag`: iterate a hashtag's recent posts, filtering to reels/videos;
   - `saved`: iterate the logged-in user's saved posts.
   Download video + thumbnail to `reel_media_dir(id)`, map post fields
   (owner→author, caption, hashtags, mentions, likes, comments, views, duration,
   date) into `Reel`. Respect rate limits; on a soft-ban/login error raise
   `IngestError` with a clear message.
4. **`ingest/collection.py` — named collections.** Port the standalone script
   into a module `CollectionIngestor`. It reads a *named* Instagram
   collection/saved-feed via the private collection endpoint using exported
   **browser cookies** (`config.auth.cookies_from_browser` or `cookies_file`):
   resolve the collection id from its name/URL, page through the feed endpoint
   with the cookie-authenticated session, and yield reel URLs. Provide
   `fetch_collection(url_or_name, out_file)` that writes the resolved reel URLs
   to `paths.input_urls/<slug>.txt` (so a subsequent `urls` run ingests them) AND
   a path to yield `Reel` records directly. Handle pagination cursors and a
   graceful stop when the endpoint rate-limits.
5. **CLI wiring.** Implement `reels-scrap fetch-collection <url-or-name>` (calls
   `collection.fetch_collection`, prints the written file + count) and make the
   `ingest` step of `run` call `make_ingestor(config).fetch()`, saving each
   `Reel` via `Reel.save(paths.output_reels)` and recording counts in the
   `RunReport`.
6. **Resilience + provenance.** Every fetcher: skips already-ingested reels
   (dedupe), logs each download via `get_logger`, records per-reel
   success/skip/failure in the `RunReport`, and never aborts the whole batch on a
   single failed reel.
7. **Tests.** `tests/test_ingest.py`: `shortcode_from_url` parsing for
   reel/reels/p URL forms; the factory dispatches by `source.type`;
   `dedupe` skips when a sidecar JSON exists; a yt-dlp `info`-dict → `Reel`
   mapper test with a fixture dict (mock the network/download). For
   instaloader/collection, mock the client and assert field mapping +
   pagination-stop behavior.

## Constraints
- MUST fill only identity/metadata/media fields — no transcript/ocr/vision here.
- MUST resolve every path through `core/paths`; media under `input/media`,
  records under `output/reels`.
- MUST use the IG shortcode as `Reel.id` consistently across all fetchers.
- MUST be resumable: re-running skips reels whose sidecar JSON already exists.
- MUST degrade per-reel, never crash the batch on one bad reel.
- MUST NOT hard-code cookies, credentials, or a browser; read them from config.
- MUST NOT call any LLM or extraction code in this layer.

## Output format
Paste-ready files, each in a fenced block headed by its path, in this order:
`ingest/base.py`, `ingest/ytdlp.py`, `ingest/instaloader_src.py`,
`ingest/collection.py`, the `cli.py` additions (show only the changed/added
commands), and `tests/test_ingest.py`. End with the exact commands to add the
ingest deps (`yt-dlp`, `instaloader`) and run the tests, and a one-line example:
`reels-scrap fetch-collection <url>` then `reels-scrap run`.

Reason briefly in a `<thinking>` block first, then output the files.
