# Implementation Plan: Slide Explainer with Source Research

**Branch**: `001-slide-explainer` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-slide-explainer/spec.md`

## Summary

A local, single-user web app that explains lecture slides in detail. The learner uploads a deck (PPTX, PDF, or images).

A Python backend:
- extracts every slide (native text, notes, and tables, plus a vision pass over the rendered image)
- interprets vague slides from their context
- researches authoritative, freely accessible books and web pages with OpenAI's web search
- organizes books into a RAPTOR summary tree, with figures explained
- generates a cited, filler-free explanation document in PDF, Word, Markdown, or HTML

A Next.js frontend (DESIGN.md) drives the flow, with cost estimates and approval gates. Q&A and quizzes are grounded in the same evidence.

Orchestration is a LangGraph state graph with a SQLite checkpointer, so every stage is resumable. All chat roles default to `gpt-5.4-nano` (the learner's choice; about $0.50 per 50-slide deck plus search fees), with per-role reasoning effort and a per-role upgrade path gated by evals. The cap is GPT-5.5. Details are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.14 (backend, uv-managed venv); TypeScript on Node 24 (frontend)

**Primary Dependencies**:
- **Backend**:
  - API and data: FastAPI 0.142, Pydantic 2.13, SQLAlchemy 2, sse-starlette 3.5
  - Model and orchestration: openai 3.22 (Responses API), LangGraph 1.2 + langgraph-checkpoint-sqlite 3.1
  - File handling: PyMuPDF 1.28, python-pptx 1.0.2, Pillow 12
  - Books and research: scikit-learn 1.9 + NumPy 2.5, tiktoken, httpx 0.28, trafilatura 2.2
  - Rendering: Jinja2, python-docx 1.2, Playwright 1.63 (Chromium)
  - Optional GPU OCR: rapidocr 3.9 + onnxruntime(-gpu) 1.30
- **External**: LibreOffice (headless PPTX → PDF)
- **Frontend**: Next.js 16.3, React 19.3, Tailwind 4.3, shadcn 4.21, openapi-typescript 7.13 + openapi-fetch 0.17, Zod 4, KaTeX 0.18

**Storage**: SQLite (`data/slidex.db`, WAL) for all entities, LangGraph checkpoints, caches, and embeddings (float32 BLOBs). Content-addressed file store `data/files/`.

**Testing**:
- **Backend**: pytest 9 (+ pytest-asyncio, respx), a fake/recorded OpenAI client, contract test against `contracts/openapi.yaml`, and an eval CLI.
- **Frontend**: Vitest 5 + Testing Library, Playwright E2E.
- **Static checks**: Ruff and mypy (strict) on the backend; `tsc` and ESLint on the frontend.

**Target Platform**:
- **Primary**: Windows 11 laptop (Iris Xe, no GPU, 14 GB RAM)
- **Secondary**: i5-13500HX + RTX 4050 6 GB, where local OCR is used
- **Also**: macOS/Linux compatible
- **Network**: backend bound to 127.0.0.1

**Project Type**: Web application (Python API + Next.js frontend), local-first single user

**Performance Goals**:
- 50-slide deck from upload to PDF in under 20 minutes (SC-001), with model calls at 6-way concurrency
- Vector search under 50 ms at ≤ 10k vectors
- UI progress events within 1 s of stage changes

**Constraints**:
- No GPU required; ≤ 4 GB RAM for the backend on a 300-slide deck (render and process slides one at a time)
- Models ≤ GPT-5.5 (allow-list)
- Only lawful, freely accessible sources used as evidence
- Web content treated as untrusted
- API key server-side only
- Estimate within ±30% (SC-010)

**Scale/Scope**:
- Decks up to 300 slides
- Books up to 1,000 pages
- ≤ 15 research topics × ≤ 8 pages per topic per run
- 1 user
- About 8 frontend screens and 30 API endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | How the design satisfies it | Status |
|---|---|---|
| I. Grounded & Cited | Evidence IDs are passed into every generation prompt. Output blocks must cite known IDs; unknown or missing citations are retried, then dropped and counted (R12). Q&A declines when retrieval finds no supporting evidence. RAPTOR tree + collapsed-tree retrieval for books (R7). Reconstructed blocks are typed separately with confidence (data-model `reconstructed`). | ✅ |
| II. Detailed, Never Padded | Block schema forces mechanism, diagram, formula, and example parts. `concept_first_seen` planning + `refer_back` blocks prevent repetition (R12). Filler lint (phrase list + cheap model check) regenerates offending blocks. | ✅ |
| III. Pedagogy First | Fixed block order per slide (slide says → explanation → diagrams → formulas → example → connection). Diagrams explained part by part (prompt + `diagram` block). Quiz hint ladder enforced in state (`hint_level`, `revealed`). No flashcards. | ✅ |
| IV. Contract-First | `contracts/openapi.yaml` is the source of truth, checked by a contract test. Frontend types are generated with openapi-typescript. Pydantic/Zod at boundaries. `responses.parse` with Pydantic for all structured LLM output. Key only in `backend/.env`. | ✅ |
| V. Test-First & Eval-Driven | Unit tests for extraction, page labels, chunking, clustering, dedup, citation validation, and all four renderers, written first. Recorded or fake model responses by default. Eval suites for vague interpretation, citations, diagrams, sources, and refusal, with baselines. | ✅ |
| VI. Cost & Resource | No GPU needed. CUDA auto-detect for local OCR (R4). Content-hash caches for every model call and fetch. Research budget. Per-stage cost ledger + calibrated estimator (R10). Model roles in one module. | ✅ |
| VII. Simplicity & Local-First | One SQLite file (entities, checkpoints, embeddings, caches). No Redis, Celery, or vector DB service. In-process worker thread. No side effects beyond model calls, search, and public fetches. | ✅ |
| VIII. Trustworthy & Lawful Sources | Paywall/login detection → further reading. Open Library for metadata only. robots.txt + rate limit. SSRF guard. Untrusted-content delimiters + injection/spam classifier → `blocked`. Authority rubric ranking. Disagreements surfaced (R6). | ✅ |

**Gate result (pre-research)**: PASS. **Gate result (post-design)**: PASS — no violations; Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-slide-explainer/
├── plan.md              # This file
├── research.md          # Phase 0 decisions (R1–R15)
├── data-model.md        # Phase 1 entities, state machine, validation rules
├── quickstart.md        # Phase 1 run + validation guide
├── contracts/
│   └── openapi.yaml     # Phase 1 API contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml                 # uv project; extras: gpu
├── .env.example                   # OPENAI_API_KEY, SLIDEX_* settings
├── src/slidex/
│   ├── main.py                    # FastAPI app factory, routers, lifespan (worker thread)
│   ├── cli.py                     # `slidex serve | eval …`
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings), paths, budgets
│   │   ├── models.py              # Model roles + ALLOWED_MODELS (≤ GPT-5.5)
│   │   ├── pricing.py             # Price table, CostLedger
│   │   ├── errors.py              # Problem types (RFC 9457) + codes
│   │   └── hardware.py            # CUDA / LibreOffice / Chromium detection
│   ├── db/
│   │   ├── base.py                # SQLAlchemy engine (WAL), session, schema_version
│   │   ├── tables.py              # ORM models per data-model.md
│   │   └── files.py               # Content-addressed file store
│   ├── llm/
│   │   ├── client.py              # AsyncOpenAI wrapper: parse(), cache, retry, ledger
│   │   ├── fake.py                # Fake/recorded client for tests (SLIDEX_FAKE_LLM)
│   │   ├── prompts/               # Versioned prompt templates (*.md)
│   │   └── schemas.py             # Pydantic output schemas (SlideExtraction, …)
│   ├── intake/
│   │   ├── pptx.py                # python-pptx extraction + LibreOffice render
│   │   ├── pdf.py                 # PyMuPDF text/render/page labels
│   │   ├── images.py              # Pillow normalize
│   │   └── ocr.py                 # TextRecognizer: LocalOcr (rapidocr) | provider
│   ├── understand/
│   │   ├── extract.py             # Pass A: per-slide vision extraction
│   │   ├── interpret.py           # Pass B: vague-slide interpretation
│   │   └── topics.py              # Topic consolidation
│   ├── research/
│   │   ├── plan_queries.py
│   │   ├── search.py              # Responses web_search discovery
│   │   ├── openlibrary.py         # Bibliographic metadata
│   │   ├── fetch.py               # httpx + robots + SSRF guard + trafilatura/PyMuPDF
│   │   ├── safety.py              # Untrusted wrapping, injection/spam classifier
│   │   ├── rank.py                # Relevance/authority ranking
│   │   └── disagree.py            # Disagreement detection
│   ├── books/
│   │   ├── parse.py               # Pages, labels, TOC
│   │   ├── chunk.py
│   │   ├── raptor.py              # PCA+GMM clustering, recursive summaries
│   │   └── figures.py             # Raster + vector figure capture, explanation
│   ├── retrieval/
│   │   ├── embed.py
│   │   └── index.py               # NumPy cosine VectorIndex, collapsed-tree retrieval
│   ├── explain/
│   │   ├── planner.py             # concept_first_seen, refer_back plan
│   │   ├── slide.py               # SlideExplanation generation
│   │   ├── validate.py            # Citation integrity + filler lint
│   │   └── assemble.py            # ExplanationDocumentModel (by_slide / by_topic)
│   ├── render/
│   │   ├── templates/             # Jinja2 HTML + print CSS (DESIGN.md tokens)
│   │   ├── html.py
│   │   ├── pdf.py                 # Playwright Chromium page.pdf
│   │   ├── docx.py                # python-docx (+ KaTeX PNG formulas)
│   │   └── markdown.py            # .md + images zip
│   ├── graph/
│   │   ├── deck_graph.py          # LangGraph pipeline with interrupts
│   │   ├── qa_graph.py            # Q&A + quiz
│   │   ├── worker.py              # Background runner, resume, cancel
│   │   └── events.py              # Broadcaster → SSE
│   ├── estimate.py                # Estimator + calibration
│   └── api/
│       ├── health.py  decks.py  slides.py  research.py  sources.py
│       ├── documents.py  runs.py  qa.py  quiz.py  files.py
│       └── deps.py
├── tests/
│   ├── unit/                      # Deterministic logic (written first)
│   ├── contract/test_openapi_contract.py
│   ├── integration/               # Graph runs with fake LLM + respx web
│   └── fixtures/                  # decks/, books/, web/, llm_recordings/
└── evals/
    ├── suites/                    # Golden sets (JSON/YAML)
    └── results/

frontend/
├── package.json                   # scripts: dev, build, typecheck, lint, test, test:e2e, gen:api
├── next.config.ts                 # rewrites /api/* → http://127.0.0.1:8000/*
├── components.json                # shadcn
├── src/
│   ├── app/
│   │   ├── layout.tsx  globals.css           # Geist fonts, DESIGN.md tokens (light/dark)
│   │   ├── page.tsx                           # Decks list + upload
│   │   └── decks/[deckId]/
│   │       ├── page.tsx                       # Slide overview (clarity, needs input, hints)
│   │       ├── research/page.tsx              # Estimate → confirm → topics/sources approve
│   │       ├── document/page.tsx              # Options, progress, downloads, history
│   │       └── learn/page.tsx                 # Q&A + quiz
│   ├── components/
│   │   ├── ui/                                # shadcn primitives
│   │   └── slidex/                            # upload-dropzone, slide-card, clarity-badge,
│   │                                          # estimate-card, source-row, run-progress,
│   │                                          # citation-chip, approval-card, quiz-panel
│   └── lib/
│       ├── api/schema.d.ts                    # generated (do not edit)
│       ├── api/client.ts                      # openapi-fetch client
│       └── sse.ts                             # EventSource hook
└── tests/                                     # vitest + playwright

data/                               # runtime (git-ignored): slidex.db, files/
```

**Structure Decision**: Web application with `backend/` (Python package `slidex`) and `frontend/` (Next.js) at the repository root. This matches the constitution's Technology section and AGENTS.md, which will be updated to this layout. `data/` is runtime state and is git-ignored. `awesome-design-md/` remains a read-only reference outside both apps.

## Delivery order (for /speckit-tasks)

1. **Foundation**: backend skeleton, config/model allow-list, DB, file store, LLM client with cache/ledger/fake, health, contract test, and the frontend skeleton with tokens + generated client.
2. **US1** (P1): intake (pptx/pdf/images), OCR paths, Pass A/B, topics, slide overview UI with hints.
3. **US2** (P1): estimate, search/fetch/safety/rank, Open Library, book RAPTOR + figures, disagreements, sources UI with approval.
4. **US3** (P1): planner, explanation generation + validation, assembly, the four renderers, document UI + downloads.
5. **US4** (P2): Q&A graph + streaming, quiz with hint ladder, learn UI.
6. **Polish**: eval suites + baselines, resume/cancel hardening, calibration, E2E, AGENTS.md/README updates.

## Complexity Tracking

No constitution violations. Not applicable.
