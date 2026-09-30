# Research: Slide Explainer with Source Research

**Feature**: `001-slide-explainer` · **Date**: 2026-09-30 · **Spec**: [spec.md](spec.md)

All Technical Context unknowns are resolved below. Versions were checked against PyPI / npm on 2026-09-30.

## R1. AI models (learner's key allows up to GPT-5.5)

- **Decision (learner choice, 2026-09-30): `gpt-5.4-nano` for every chat role.** Roles stay separate in one config module (`backend/src/slidex/core/models.py`) so each can be switched later via env vars without code changes:

  | Role | Default model | Reasoning effort | Used for |
  |---|---|---|---|
  | `strong` | `gpt-5.4-nano` | `medium` | Vague-slide interpretation, slide explanations, disagreement assessment, Q&A answers, quiz grading |
  | `vision` | `gpt-5.4-nano` | `low` | Per-slide extraction (text cleanup, LaTeX, visual descriptions, topic, clarity), book figure explanations |
  | `bulk` | `gpt-5.4-nano` | `none` | RAPTOR cluster summaries, source ranking, query planning, safety classification, filler check |
  | `search` | `gpt-5.4-nano` + `web_search` tool | `low` | Source discovery |
  | `embed` | `text-embedding-3-small` | — | All embeddings (nano has no embeddings) |

  `gpt-5.4-nano` (snapshot `gpt-5.4-nano-2026-03-17`): $0.20 input / $0.02 cached / $1.25 output per 1M tokens; 400k context; supports image input, structured outputs, function calling, web search, and reasoning effort `none…xhigh`. An allow-list (`ALLOWED_MODELS`) rejects anything above GPT-5.5 at startup.
- **Rationale**: The learner wants the cheapest option. Nano supports every capability the pipeline needs. Quality-critical roles compensate with higher reasoning effort, and grounding is enforced mechanically anyway (citation validation, R12).
- **Quality guardrail**: The eval suites (SC-002/003/005/006/009) are the arbiter. If a role misses its threshold on nano, the fix is a one-line env change for that role only, e.g. `SLIDEX_MODEL_STRONG=gpt-5.4-mini` ($0.75/$4.5) or `gpt-5.5` ($5/$30). The estimate screen always shows the active models and cost.
- **Alternatives considered**: GPT-5.5 for explanations (~$3–4 per deck vs ~$0.20 on nano). gpt-5.4-mini for vision (better on dense diagrams; kept as the first fallback). Local LLMs (too weak; no GPU on the primary laptop).
- **Rough cost** for a 50-slide deck + 1 open textbook (300 pages) + ~60 web pages, all on nano:
  - slide extraction ≈ $0.05
  - interpretation ≈ $0.02
  - research ≈ $0.15, plus web-search tool fees (≈ 30 calls)
  - book RAPTOR + figures ≈ $0.10
  - explanations ≈ $0.20
  - **Total ≈ $0.50 plus search tool fees.** The estimator (R10) computes the exact figure per run.

## R2. API style: OpenAI Responses API + structured outputs

- **Decision**: `openai` Python SDK 3.x. Use `client.responses.parse(model=…, input=[…], text_format=PydanticModel)` for every structured step. Images go in as `input_image` with base64 data URLs, `detail: "high"` for slides and figures. Use `AsyncOpenAI` with a semaphore (default concurrency 6) and exponential backoff on 429/5xx.
- **Rationale**: This matches Constitution IV (validated structured outputs), and the Responses API is where `web_search` lives.
- **Alternatives**: Chat Completions (no built-in web search). LangChain model wrappers (an extra abstraction layer; LangGraph doesn't need them).

## R3. Slide intake and rendering

- **Decision**:
  - **PPTX**: `python-pptx` 1.0.2 extracts text frames (reading order by shape position), tables, speaker notes, and picture shapes. LibreOffice (installed at `C:\Program Files\LibreOffice\program\soffice.exe`; the path is configurable) runs headless `--convert-to pdf` to get a faithful render with animations flattened. PyMuPDF then renders each page to PNG (150 DPI) as the slide image.
  - **PDF**: PyMuPDF 1.28 gives text with positions, embedded images, page labels, and a 150-DPI render per page. If a page has fewer than 20 characters of text layer, it's treated as image-only.
  - **Images**: Pillow 12 applies EXIF orientation, converts to RGB, and downsizes to at most 2000 px. Upload order is used as slide order, and the learner can reorder.
- **Rationale**: Native text is exact and free. The rendered image lets the vision model see layout and diagrams. LibreOffice is the only reliable free PPTX renderer on Windows and is already installed.
- **Alternatives**: PowerPoint COM automation (not installed). Rendering PPTX shapes ourselves (unreliable for SmartArt/charts). `pdfplumber` (slower and no rendering).

## R4. Text recognition (OCR) with hardware-adaptive path

- **Decision**: One `TextRecognizer` interface with two implementations:
  - `LocalOcr`: `rapidocr` 3.9 on `onnxruntime-gpu`. It's chosen only when `onnxruntime.get_available_providers()` includes `CUDAExecutionProvider` (the RTX 4050 laptop).
  - `ProviderOcr`: no separate call. The per-slide vision extraction (R5) already returns the transcribed text for image-only slides.

  On GPU, local OCR text is passed into the vision call as a hint, and **text-only image slides with OCR confidence ≥ 0.9 skip the vision call entirely**. That's where the zero-provider-cost OCR saving comes from (SC-012). Formulas always go to the vision model; OCR engines can't produce LaTeX.
- **Rationale**: This satisfies Constitution VI. Identical output schema (`SlideExtraction`) on both paths.
- **Alternatives**: PaddleOCR (heavy install), Surya (torch plus about 2 GB of models, overkill), Tesseract (not installed; weak on slides).

## R5. Slide understanding (two passes)

- **Decision**:
  - **Pass A (per slide, `vision` role)**: slide image + native text + notes → `SlideExtraction`: cleaned text, formulas (LaTeX), tables, visuals[] (kind, description, what it conveys, unreadable parts), topic, concepts[], clarity (`clear|vague|unreadable`), divider flag.
  - **Pass B (deck-level, `strong` role)**: runs only for slides rated `vague`/`unreadable`. It uses a window of ±3 neighbouring slide extractions, deck title, learner context, and hints → `SlideInterpretation`: likely meaning, confidence 0–1, rationale. Confidence < 0.5 → `needs_input`.
  - Then a cheap deck-level topic consolidation (`bulk`) merges near-duplicate topics into ≤ 15 research topics.
- **Rationale**: Most slides are clear and only need cheap extraction. The expensive reasoning goes to the vague ones, which are the learner's core pain.

## R6. Source research

- **Decision**:
  1. **Query planning** (`bulk`): per topic, 2 queries (a textbook/lecture-notes query, a documentation/reference query), informed by the course context.
  2. **Discovery** (`search`): Responses API with `tools=[{"type":"web_search"}]`. Candidate URLs are read from `url_citation` annotations plus a structured candidate list. A first pass is restricted with `filters.allowed_domains` to open-textbook and university domains (openstax.org, libretexts.org, open.umn.edu/opentextbooks, ocw.mit.edu, *.edu, arxiv.org, wikipedia.org, official docs added per topic); a second pass is unrestricted.
  3. **Book metadata**: Open Library search API for bibliographic records of relevant non-free books ("Further reading"). No full text is fetched.
  4. **Fetching**: `httpx` with a custom User-Agent, `urllib.robotparser` checks, 1 request/second per host, 20-second timeout, 5 MB cap. HTML → main text via `trafilatura` 2.2; PDFs → PyMuPDF (if the PDF is 80 pages or longer and freely licensed, it's treated as a book and goes through RAPTOR). Detected paywalls/login walls → `further_reading`.
  5. **Sanitizing**: fetched text is stored as data. Before any model call it's wrapped in `<untrusted_source id=…>` delimiters, with a system rule that its contents are never instructions. A cheap classifier pass (`bulk`) flags pages containing agent-directed instructions or SEO spam, which are excluded.
  6. **Ranking** (`bulk`): relevance (0–1, to topic + slides) and authority (0–1, rubric: official docs/textbook/university/peer-reviewed > reputable reference > blog). Keep the top 5 per topic, each with a one-line reason.
  7. **Disagreement detection** (`strong`, only on topics with ≥ 2 kept sources): claims compared against each other and against the slide text.
- **Budget**: ≤ 2 searches and ≤ 8 fetched pages per topic, and ≤ 15 topics per run (configurable). All shown in the estimate.
- **Rationale**: Covers Constitution VIII (lawful, authoritative, untrusted-content handling) with provider-native search, so no extra search API key is needed.
- **Alternatives**: Tavily/Exa/Brave search APIs (an extra key and account). Scraping Google (against terms of service). Z-Library/LibGen (unlawful; explicitly excluded).

## R7. Book processing (RAPTOR)

- **Decision**:
  - **Parse**: PyMuPDF gives per-page text blocks and page labels (`page.get_label()`, falling back to the physical number, flagged `label_kind`).
  - **Chunk**: ~350-token leaves on paragraph boundaries (counted with tiktoken).
  - **Embed**: `text-embedding-3-small`.
  - **Cluster**: standardize → PCA to 32 dimensions → scikit-learn `GaussianMixture`, with the component count chosen by BIC and soft assignment at probability ≥ 0.1 (RAPTOR style). Clusters over 3000 tokens are re-clustered.
  - **Summarize**: each cluster summarized by `bulk` into a structured summary with the page range as the union. Recurse until ≤ 3 nodes; the top level is "themes". The chapter level uses the PDF outline (`doc.get_toc()`) when it exists.
  - **Retrieve**: "collapsed tree" retrieval, a cosine top-k across all levels with a token budget.
- **Figures**: embedded raster images (`page.get_images`), plus vector figures found with `page.cluster_drawings()`. Drawing clusters smaller than 5% of the page area are dropped. Each region is rendered at 200 DPI, the caption comes from the nearest text block starting with "Figure/Fig./Table", and it's explained by `vision` with surrounding page text as context. Decorative images (under 80 px or repeated on 3+ pages) are skipped.
- **Rationale**: RAPTOR as required by Constitution I. PCA+GMM avoids UMAP/numba and keeps dependencies light.

## R8. Vector store

- **Decision**: Embeddings are stored as `float32` BLOBs in the same SQLite database (`embedding` table). Search is exact cosine in NumPy over rows filtered by source/deck, cached in memory per request. The interface is `VectorIndex.search(owner_ids, query_vec, k, token_budget)`.
- **Rationale**: Scale is small (a 1,000-page book is about 4–5k vectors; 60 web pages about 1.5k), so brute force is well under 50 ms. One database file (Constitution VII). The interface allows swapping in sqlite-vec later if needed.
- **Alternatives**: Chroma (a separate on-disk store and heavier dependencies), pgvector (a Postgres service), sqlite-vec (still 0.x; unnecessary at this scale).

## R9. Orchestration & resumability

- **Decision**: LangGraph 1.2 `StateGraph` for the deck pipeline, with `langgraph-checkpoint-sqlite` (`SqliteSaver`) and `thread_id = deck_id`.
  - **Nodes**: `intake → extract_slides → interpret_vague → consolidate_topics → [interrupt: estimate/confirm research] → research → rank_and_disagree → [interrupt: approve sources] → process_books → plan_document → explain_slides → render`.
  - **Work reuse**: every node checks the per-item cache (content-hash keyed tables) before calling a model, so a resumed run skips finished slides, pages, and clusters (FR-030).
  - **Separate graphs**: a small Q&A/quiz graph (thread `qa:{deck_id}`) for US4.
  - **Execution**: a single background worker thread in the FastAPI process runs graphs. Progress events go to an in-memory broadcaster, streamed to the UI over Server-Sent Events (`sse-starlette`).
- **Rationale**: Interrupts map cleanly to the learner-approval steps. The checkpointer gives crash-safe resume without Celery or Redis (Constitution VII).
- **Alternatives**: A hand-rolled job table (would reimplement checkpointing). Celery+Redis (extra services).

## R10. Cost accounting & estimate

- **Decision**: A `pricing.py` table (per model: input, cached input, output, and web-search fee per call) with a `CostLedger` that records `usage` from every response by `(run_id, stage)`.
- **Estimator**: deterministic formulas using calibration constants stored in the database and updated after each run with an exponential moving average of actual/estimated. Examples:
  - slides × (image tokens by detail + ~800 output)
  - vague share (default 25%) × Pass B tokens
  - topics × (2 searches + 8 pages × avg page tokens × ranking)
  - book pages × 550 tokens × summary ratio
  - slides × explanation tokens
- **Rationale**: SC-010 (±30%) needs calibration. The deterministic base keeps the estimate free to compute.

## R11. Document generation (PDF, Word, Markdown, HTML)

- **Decision**: One canonical `ExplanationDocument` Pydantic model (sections → blocks: text, list, formula (LaTeX), code, table, image, citation refs, callouts for "What the slide says" / "Reconstructed" / "Disagreement").
  - **Markdown**: markdown-it-compatible, with `$…$` math and relative image paths, zipped with images.
  - **HTML**: Jinja2 templates styled with the DESIGN.md tokens (print-friendly light theme), KaTeX 0.18 rendered **server-side at build time** in the headless browser. Self-contained, with images inlined.
  - **PDF**: the same HTML printed with Playwright 1.63 Chromium (`page.pdf`, A4, header/footer with page numbers, clickable links). KaTeX renders correctly because it's a real browser.
  - **Word (.docx)**: `python-docx` 1.2 with headings/lists/tables/images/hyperlinks. Formulas are rendered to PNG through the same Playwright/KaTeX page (`element.screenshot`) and inserted inline; the LaTeX goes in the alt text.
- **Rationale**: One content model with four renderers means identical content across formats (FR-018). Chromium gives the best fidelity for math and links on Windows without GTK (WeasyPrint needs Pango/GTK on Windows).
- **Alternatives**: WeasyPrint (GTK dependency pain on Windows), ReportLab (manual layout, no math), pandoc (not installed; adds a system dependency).

## R12. Explanation generation & citation integrity

- **Decision**:
  - **Plan** (`plan_document`): walk slides in order and build a `concept_first_seen` map from `SlideExtraction.concepts` (embeddings are used to merge synonyms). Each slide gets `explain_fully` vs `refer_back_to: slide N` per concept (FR-023).
  - **Retrieve**: per slide, pull context from the collapsed tree of approved books + web sections (k ≈ 8, 3k-token budget), plus relevant book figures.
  - **Generate** (`strong`): `SlideExplanation` structured output. Every block has `citations: [evidence_id]` referencing only evidence IDs supplied in the prompt.
  - **Validate**:
    - any unknown evidence ID → retry once, then drop the block and flag it
    - a block without citations → rejected (FR-022)
    - filler lint: a phrase blacklist plus a `bulk` check → regenerate the offending block (FR-024)
  - Vague slides produce two parts: `slide_says` and `reconstructed` (with confidence).
- **Rationale**: Constitution I and II are enforced mechanically, not just prompted.

## R13. Backend stack & tooling

- **Decision**:
  - **Runtime**: Python 3.14 (system install) in a project venv managed by **uv** (installed via `pip install uv`), with the `pyproject.toml` + `uv.lock` committed.
  - **API and data**: FastAPI 0.142, Pydantic 2.13, SQLAlchemy 2 ORM on SQLite (WAL mode), with `Base.metadata.create_all` plus a `schema_version` table. Alembic is deferred until a second schema version exists.
  - **Tests and lint**: pytest 9 + pytest-asyncio; `respx` for httpx mocks; a fake OpenAI client that replays recorded fixtures. Ruff for lint/format; mypy (strict on `slidex/`).
- **Rationale**: All dependencies publish Python 3.14 wheels. uv gives reproducible installs on both laptops.

## R14. Frontend stack

- **Decision**:
  - **Framework and UI**: Next.js 16.3 (App Router), React 19.3, TypeScript, Tailwind 4.3, shadcn 4.21 (via CLI), Geist fonts. Theme tokens from DESIGN.md go in `app/globals.css`.
  - **API client**: `openapi-typescript` 7.13 generates `src/lib/api/schema.d.ts` from the backend's `/openapi.json`, and `openapi-fetch` 0.17 is the typed client. Zod 4 validates forms.
  - **Backend access**: Next.js `rewrites` proxy `/api/*` → `http://127.0.0.1:8000/*` (same-origin, no CORS, SSE passes through). The browser never sees the OpenAI key.
  - **Tests**: Vitest 5 + Testing Library for components; Playwright 1.63 for E2E against the mocked backend (`SLIDEX_FAKE_LLM=1`).
- **Rationale**: This matches AGENTS.md/DESIGN.md and Constitution IV (generated types).

## R15. Security & privacy specifics

- **Secrets**: `OPENAI_API_KEY` is read only by the backend from `backend/.env` (git-ignored). `backend/.env.example` documents the variables. The learner adds the key themselves.
- **Uploads**: allowed MIME types/extensions (`.pptx`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`); size cap 200 MB per file; zip-bomb guard for PPTX (uncompressed size ≤ 1 GB); filenames are never used as paths (content-hash storage).
- **Rendering**: model output is Markdown only, rendered with HTML disabled in the UI and escaped in Jinja2 templates. Fetched HTML is never rendered.
- **Network**: fetches only to `http(s)` public hosts; private/loopback IP ranges are blocked (SSRF guard).
- **Server**: the backend binds to `127.0.0.1` only.
