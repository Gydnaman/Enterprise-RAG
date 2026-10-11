# README and Dashboard Onboarding Design

## Goal

Help a first-time, nontechnical visitor understand what Enterprise-RAG currently does, how its parts fit together, how to start the demo, and what to try in the visual workbench.

## Audience and product truth

- Audience: someone who can follow copy-and-paste setup steps but does not already know RAG, FastAPI, Vue, or the repository structure.
- This repository is Stage A of a local RAG workbench demonstration. Its sample corpus and retrieval/answer workflows are deterministic fixtures and mocks.
- Uploaded files are validated and stored as `uploaded_unprocessed`; this stage does not parse them or create chunks from them.
- There is no real LLM, OCR, vector database, authentication, multi-tenancy, or production queue in Stage A.

## README experience

Put the explanation before developer details. In order, the README should answer:

1. What the workbench is and who it is for.
2. Which capabilities are real in Stage A and which are simulated.
3. How the browser, API, workflow/domain layer, database, fixture corpus, and upload storage connect.
4. What each visible page is for.
5. How to start the Compose demo on Windows and open the workbench.
6. A short path through sample documents, retrieval, citations, Agent Q&A, and Run details.
7. How to stop the demo, where data is stored, how to troubleshoot startup, and how to start the SQLite developer setup.
8. Plain-language definitions for RAG, Fixture, Chunk, Evidence, Citation, and Run.

Use a Mermaid architecture diagram and a page-to-purpose table. Keep OpenAPI/type generation details in a developer section after the beginner path.

## Workbench experience

Keep the existing page routes and API behavior. Make the home page an explicit first-run landing area with:

- a clear Stage A `演示模式 · MOCK` status and a separate API connection state;
- three direct actions: open the built-in sample documents, try retrieval, and ask a question / inspect citations;
- a short explanation that uploads are stored but not parsed and that answers use the built-in read-only fixtures;
- the existing knowledge-base list and recent runs below the first-use actions.

Use plain Chinese labels before specialist terms, keep text comfortably readable, retain the existing light neutral and blue palette, and make navigation available at narrow widths. Keep provider status copy understandable to first-time users. Do not add a guided tour overlay or redesign all feature pages.

## Constraints

- Do not change API schemas, routes, fixtures, persistence, or backend behavior.
- Do not add npm dependencies.
- Keep Docker ports and the existing SQLite developer flow accurate to repository configuration.
- Do not describe Stage A as a production-ready RAG service.
