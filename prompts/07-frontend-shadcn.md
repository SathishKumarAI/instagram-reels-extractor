# Layer 07 — Frontend (Vite + React + shadcn)

You are a senior frontend engineer. Your objective is to build `web/`: a Vite +
React + TypeScript + Tailwind + shadcn/ui app (Catppuccin Mocha, dark default)
with three views — Knowledge Base, Reels (grid + detail), and Research Chat with
citations — talking to the FastAPI backend through a typed client.

<context>
  <depends_on>
    Layer 06 exposes: `GET /api/reels`, `GET /api/reels/{id}`,
    `GET /api/knowledge`, `GET /api/search?q=`, `POST /api/chat`, and
    `GET /api/media/{path}`. Response shapes mirror `api/schemas.py`.
  </depends_on>
  <serving>
    Dev: Vite on :5173 with a proxy `/api → http://localhost:8000`. Prod: build
    to `web/dist`, served by FastAPI on one port (Layer 06).
  </serving>
  <design>
    Catppuccin Mocha palette, dark by default. Clean, modern, information-dense
    but readable. Use shadcn/ui primitives (card, button, input, table, badge,
    sheet/dialog, scroll-area, skeleton) rather than hand-rolled components.
  </design>
</context>

## Instructions
1. **Scaffold `web/`.** Vite React-TS template; add Tailwind, shadcn/ui (init +
   needed components), and a Catppuccin Mocha theme (CSS variables mapped to
   shadcn tokens, dark as default). Configure `vite.config.ts` with the
   `/api → :8000` dev proxy and `build.outDir = dist`. Add `tsconfig` path alias
   `@/`.
2. **Typed API client (`src/lib/api.ts`).** A thin `fetch` wrapper plus typed
   functions: `listReels(params)`, `getReel(id)`, `getKnowledge()`,
   `search(q, topK?)`, `chat(question)`. Mirror the backend schemas as TS types
   in `src/lib/types.ts`. Media URLs come straight from the API
   (`/api/media/...`). Centralize error handling (surface 409 empty-index and
   404 reel-not-found as friendly UI states).
3. **App shell (`src/App.tsx` + layout).** A sidebar with three nav items
   (Knowledge · Reels · Research) and a top search box. Use a router
   (`react-router-dom`) for `/`, `/reels`, `/reels/:id`, `/research`. Apply the
   dark Mocha theme at the root.
4. **Knowledge Base view.** Fetch `/api/knowledge`; render topic cards (name +
   genre badge); each card shows the `overview` (when present), key facts, and
   source-reel chips that deep-link to the reel detail. A filter bar at the top
   queries `/api/search` and filters/links results.
5. **Reels view.** Responsive card grid from `/api/reels` (thumbnail, title,
   author, genre badge, like/view stats). Clicking a card opens
   `/reels/:id` (a detail panel or route) showing: summary, a **facts table with
   timestamps** (click a timestamp to seek the embedded `<video>`), transcript
   (collapsible), OCR text, caption, hashtags, the embedded `<video>` from
   `/api/media`, and a PDF download link. Show skeletons while loading and a
   friendly empty state.
6. **Research Chat view.** A message thread; user asks a question →
   `POST /api/chat`. Render each answer with inline/citation **source chips**
   (each chip deep-links to the reel detail) and an expandable "retrieved
   snippets" section listing the citations with scores + snippets. Handle the
   `answer=null` + `note="synthesis unavailable"` case by showing the note and
   still rendering the retrieved sources. No streaming (single response).
7. **Polish.** Loading skeletons, empty/error states (incl. the 409 empty-index
   "build the index first" hint), keyboard-submit in chat, and responsive
   layout. Keep components small and typed.
8. **Tests.** Vitest + Testing Library: a chat message component renders an
   answer with its citation chips and the expandable snippets section; the
   `answer=null` case renders the "synthesis unavailable" note plus sources.

## Constraints
- MUST use Vite + React + TS + Tailwind + shadcn/ui; Catppuccin Mocha, dark
  default.
- MUST consume the backend only through the typed `src/lib/api.ts` client; no
  scattered `fetch` calls; types mirror `api/schemas.py`.
- MUST render chat citations as deep-linking chips and surface the
  `synthesis unavailable` fallback gracefully.
- MUST make facts-table timestamps seek the embedded video.
- MUST build to `web/dist` and work behind the FastAPI single-port prod serving.
- MUST NOT add auth, SSR, a state-management library beyond React Query/local
  state, or token streaming in v1.
- MUST NOT hardcode the backend origin — use the `/api` proxy (dev) and relative
  paths (prod).

## Output format
Paste-ready files, each in a fenced block headed by its path, in this order:
the Vite/Tailwind/shadcn config (`vite.config.ts`, Tailwind config, theme CSS
with the Mocha variables), `src/lib/types.ts`, `src/lib/api.ts`, `src/App.tsx` +
layout/sidebar, the three views (Knowledge, Reels + ReelDetail, Research Chat),
the citation/message components, and the Vitest test. List the shadcn components
to add. End with the commands to scaffold, install, run dev (`npm run dev`),
build (`npm run build`), and test.

Reason briefly in a `<thinking>` block first, then output the files.
