# Layer 06 — API Backend (FastAPI)

You are a backend API engineer. Your objective is to build the `api/` package: a
thin FastAPI layer exposing reels, knowledge, search, chat, and media over HTTP,
served by `reels-scrap serve` via uvicorn, with CORS for the dev frontend and
static serving of the built React app in production.

<context>
  <depends_on>
    Layers 00–05 exist. All logic lives in the modules the API calls:
    reels in `output/reels/*.json` (via `core/models.Reel`), knowledge via
    `knowledge/aggregate`, search via `search/query`, chat via `chat/rag`,
    media files under `data/` (resolved via `core/paths`).
  </depends_on>
  <boundary>
    `api` is a THIN HTTP layer. It validates input, calls a module, and shapes
    the response. No scraping, extraction, embedding, or LLM logic lives here —
    it only orchestrates calls into the existing packages.
  </boundary>
  <contract>
    The backend↔frontend contract is the Pydantic schemas in `api/schemas.py`.
    Keep them stable and typed; the frontend's TS client mirrors them.
  </contract>
</context>

## Instructions
1. **`api/schemas.py`.** Pydantic response models mirroring the domain:
   `ReelSummary` (id, title, author, genre, thumbnail_url, likes, views,
   duration, url), `ReelDetail` (full: summary, facts[] with timestamp/frame,
   transcript, ocr_text, caption, hashtags, structured, video_url, pdf_url),
   `Topic`/`KnowledgeResponse` (topics with overview?, facts[], reel refs),
   `SearchHit`/`SearchResponse`, and `ChatRequest{question}` /
   `ChatResponse{answer?, citations[], note?}`. URLs point at `/api/media/...`.
2. **`api/app.py`.** Build the FastAPI app: include the routers, add CORS
   (allow the dev origin `http://localhost:5173`), and — in production — mount
   the built frontend (`web/dist`) as static files with an SPA fallback to
   `index.html`. Map domain errors to HTTP: `EmptyIndexError` → 409,
   `ReelNotFound` → 404, `SynthesisUnavailable` is NOT an error (chat returns
   200 with `answer=null` + note). A `/api/health` endpoint.
3. **`api/routers/reels.py`.**
   - `GET /api/reels` → paginated `list[ReelSummary]`, with optional `genre` and
     `q` (delegates `q` to `search`) query params, sorted sensibly.
   - `GET /api/reels/{id}` → `ReelDetail`; 404 via `ReelNotFound` if no sidecar.
4. **`api/routers/knowledge.py`.** `GET /api/knowledge` → `KnowledgeResponse`
   from `knowledge/aggregate` (read the cached `knowledge.json`, fall back to
   aggregating on demand). Include `overview` only when synthesis is present.
5. **`api/routers/search.py`.** `GET /api/search?q=...&top_k=...` →
   `SearchResponse` via `search/query.search`; 409 on `EmptyIndexError`.
6. **`api/routers/chat.py`.** `POST /api/chat` with `ChatRequest` →
   `ChatResponse` via `chat/rag.answer`. Always 200 on a successful retrieval,
   even when synthesis is unavailable (return `answer=null` + note + citations).
   409 only if the index is empty.
7. **`api/routers/media.py`.** `GET /api/media/{path:path}` → serve files under
   `data/` (videos, thumbnails, PDFs) via `core/paths`, with a path-traversal
   guard (resolved path MUST stay within `data_dir`) and correct content types /
   range support for video.
8. **`serve` command.** Implement `reels-scrap serve` to launch uvicorn on
   `api.app:app` (host/port/reload flags). Document that in dev the frontend runs
   on :5173 with a proxy to :8000, and in prod the backend serves `web/dist`.
9. **Tests.** `tests/test_api.py` using FastAPI `TestClient` with the Claude
   subprocess mocked: every endpoint returns its schema for fixture data;
   `GET /api/reels/{id}` 404s on a missing id; `GET /api/search` 409s on an empty
   index; `POST /api/chat` returns 200 with `answer=null` + note when the LLM
   call is mocked to fail; the media route rejects path traversal
   (`../` escapes 400/404).

## Constraints
- MUST keep the API thin — delegate all logic to existing modules.
- MUST define every response shape in `api/schemas.py` (the FE contract).
- MUST map errors per spec: empty index → 409, missing reel → 404; chat with no
  synthesis → 200 (not an error).
- MUST guard the media route against path traversal; serve only under `data_dir`.
- MUST add CORS for `http://localhost:5173` and serve `web/dist` with SPA
  fallback in production.
- MUST resolve all filesystem access through `core/paths`.
- MUST NOT add auth, sessions, a database, or websockets/SSE in v1.
- MUST NOT duplicate retrieval/aggregation/chat logic in the routers.

## Output format
Paste-ready files, each in a fenced block headed by its path, in this order:
`api/schemas.py`, `api/app.py`, `api/routers/reels.py`,
`api/routers/knowledge.py`, `api/routers/search.py`, `api/routers/chat.py`,
`api/routers/media.py`, the `serve` command addition, and `tests/test_api.py`.
End with the commands to add deps (`fastapi`, `uvicorn[standard]`,
`python-multipart` if needed) and run the tests, plus `reels-scrap serve`.

Reason briefly in a `<thinking>` block first, then output the files.
