# README and Dashboard Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the public Enterprise-RAG repository understandable to first-time users and make the existing workbench show them how to try its Stage A demo.

**Architecture:** Preserve the existing Vue 3 + Vue Router frontend and FastAPI backend. Rewrite the README around the user's first five minutes, then add a home-page onboarding area that links to existing routes and reports the existing API/demo states without changing service behavior.

**Tech Stack:** Markdown, Mermaid, Vue 3 Composition API, TypeScript, Vue Router, CSS, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-11-beginner-onboarding.md`

## Global Constraints

- Stage A uses read-only fixtures and deterministic mock workflows; no real LLM, OCR, vector database, or upload parsing is present.
- Do not change API schemas, backend routes, fixture data, persistence semantics, or the existing UI route paths.
- Do not add npm dependencies.
- Keep the Compose demo at `http://localhost:4173` with API `http://localhost:8000`; keep local Vite/API development at `http://127.0.0.1:5173` and `http://127.0.0.1:8000`.
- Preserve the current light neutral and blue visual language, while making first-use text and navigation easier to read.

---

### Task 1: Rewrite the README as a beginner's project map

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: current Compose configuration in `compose.yaml`, local requirements and commands in the existing README, frontend routes in `apps/web/src/router.ts`, and Stage A behavior in `docs/specs/spec-enterprise-rag-workbench-stage-a.md`.
- Produces: a public guide with a short purpose statement, Stage A capability boundaries, a Mermaid architecture diagram, page-purpose map, Windows Compose quick start, guided demo path, stop/data/troubleshooting notes, and an optional local SQLite developer path.

- [x] **Step 1: Reorder the README around the visitor's first questions.** Open with what the project is, who can use it, and a prominent “Stage A demo” boundary before any setup commands.
- [x] **Step 2: Explain the architecture and page map.** Add a Mermaid flow `Browser (Vue) → FastAPI/OpenAPI → application/domain workflows → database/adapters`; show fixtures and uploaded bytes as separate data paths. Add one row per visible route describing what a user does there.
- [x] **Step 3: Explain the project vocabulary.** Define RAG, Fixture, Chunk, Evidence, Citation, and Run in short plain-language entries tied to the current Stage A demo.
- [x] **Step 4: Add a Windows-first Compose quick start.** State Docker Desktop as the prerequisite; show clone, `cd Enterprise-RAG`, `docker compose up --build`, opening `http://localhost:4173`, and stopping with `docker compose down`. Explain that `.env` is optional for the local demo defaults and needed only for overrides; include a route for readers who already cloned the repository.
- [x] **Step 5: Add the five-minute demo path and truth boundaries.** Walk through the built-in `Demo Knowledge Base`, sample documents, retrieval Evidence, Agent answer citations, and Run details. Explicitly say uploaded files are saved but not parsed and successful demo traces do not mean parsing/indexing happened.
- [x] **Step 6: Keep developer setup after the beginner path.** Retain the SQLite two-terminal setup and OpenAPI/type-generation commands under clearly named developer sections; state the exact browser/API URLs for that mode.
- [x] **Step 7: Add concise recovery notes.** Explain how to inspect `docker compose ps` and `docker compose logs -f api web migrate`, identify ports 4173/8000, and clarify that Compose PostgreSQL data differs from local SQLite data.
- [x] **Step 8: Review each claim against the source files.** Confirm Compose defaults, port bindings, startup dependency, route names, and Stage A limitations match the repository before keeping the text.

**Completion criteria:** A new visitor can tell what is simulated, which page to open next, how to start and stop the demo, and how to inspect evidence without reading implementation code.

---

### Task 2: Make the home page an explicit first-run control panel

**Files:**
- Modify: `apps/web/src/pages/HomePage.vue`
- Modify: `apps/web/src/App.vue`
- Modify: `apps/web/src/pages/ProvidersPage.vue`
- Modify: `apps/web/src/style.css`

**Interfaces:**
- Consumes: `api.knowledgeBases()`, existing `api.runs()` state, existing routes `/knowledge-bases/:id/documents`, `/retrieval`, `/chat`, `/runs`, and `fixture-kb-enterprise`.
- Produces: an at-a-glance Stage A/API state and three direct first-use links while retaining existing knowledge-base creation, knowledge-base cards, and recent runs.

- [x] **Step 1: Add a first-use section to `HomePage.vue`.** Place it above the knowledge-base list. Include three numbered links: open the built-in sample documents, run retrieval, and ask a question / inspect citations. Resolve the sample-document URL from the fixture knowledge-base returned by the current API; if no fixture is present, keep the route link disabled with a clear explanation.
- [x] **Step 2: Separate demo truth from API connection state.** Show a textual `演示模式 · MOCK` explanation independent of API availability. Add a distinct connected/disconnected state driven by the result of `load()` and keep actionable retry feedback when the API request fails.
- [x] **Step 3: Clarify navigation and provider status labels.** Use plain Chinese page names for the overview, retrieval, Agent Q&A, run history, and model/component status. Add short section captions on desktop and preserve visible or accessible labels for every route at narrow widths. Explain on the provider page which adapter is the demo answer provider and which components are not connected.
- [x] **Step 4: Add focused styles to `style.css`.** Use the existing neutral/blue tokens, readable body and helper text, explicit focus-visible outlines, and a responsive three-to-one-column step layout. Respect `prefers-reduced-motion`; do not introduce a new font or icon package.
- [x] **Step 5: Preserve current interactions.** Keep the existing create-knowledge-base form, fixture cards, recent-run links, loading state, and API error recovery. Do not add a new route, tour overlay, or network/model behavior.
- [x] **Step 6: Review implementation against the spec.** Inspect the changed template and styles for keyboard-readable link names, text labels accompanying status colors, mobile navigation availability, and truthful demo wording.

**Completion criteria:** From the first screen a user can identify that the app is a mock demo, determine whether the API is reachable, follow a three-step experience path, and still reach all existing pages and dashboard functions.

---

## Plan self-review

- **Spec coverage:** README purpose, limitations, system map, route map, vocabulary, startup, walkthrough, persistence, and developer path are covered by Task 1. Home-page onboarding, status clarity, responsive navigation, provider wording, readability, and scope limits are covered by Task 2.
- **Scope:** Both deliverables are a single onboarding experience split at the documentation/UI boundary; no independent backend or API work is included.
- **Dependencies:** Task 1 and Task 2 consume existing repository behavior and can be reviewed separately. Task 2 uses the route and Stage A facts documented in the spec.
- **Validation boundary:** No automated test suite will be added or run as part of this request. Review the final diff and, if the user later requests runtime verification, launch the documented Compose demo.
