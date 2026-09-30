# Quickstart & Validation: Slide Explainer

How to run the app and prove each user story works end to end. API shapes are in
[contracts/openapi.yaml](contracts/openapi.yaml); entities are in [data-model.md](data-model.md).

## Prerequisites

| Need | Check | Notes |
|---|---|---|
| Python 3.14 | `python --version` | Both laptops |
| uv | `uv --version` | `python -m pip install --user uv` |
| Node.js 24 + npm | `node --version` | |
| LibreOffice | `"C:\Program Files\LibreOffice\program\soffice.exe" --version` | PPTX rendering; path configurable via `SLIDEX_SOFFICE` |
| Chromium for Playwright | `uv run playwright install chromium` | PDF rendering + formula images |
| OpenAI API key | `backend/.env` → `OPENAI_API_KEY=` | **The learner adds this themselves**; models ≤ GPT-5.5 |
| (RTX 4050 laptop only) CUDA runtime | `uv run python -c "import onnxruntime as o; print(o.get_available_providers())"` | Should list `CUDAExecutionProvider`; install the `gpu` extra |

## Setup

```bash
cd backend
uv sync
uv run playwright install chromium
copy .env.example .env
uv run slidex serve
cd ../frontend
npm install
npm run gen:api
npm run dev
```

Notes:
- After copying `.env.example`, edit `.env` and set `OPENAI_API_KEY` before starting the backend.
- `uv run slidex serve` starts the backend on http://127.0.0.1:8000.
- `npm run gen:api` regenerates the TypeScript types from the backend's `/openapi.json`.
- `npm run dev` starts the frontend on http://localhost:3000.

On the RTX 4050 laptop, run `uv sync --extra gpu` instead of `uv sync`.

Health check: open http://localhost:3000/api/health. Expect `api_key_configured: true`, `libreoffice: true`, `renderer: true`, and `ocr_path: provider` on this laptop (`local_gpu` on the RTX 4050 laptop).

## Offline test suites (no API cost)

```bash
cd backend
uv run pytest
uv run ruff check
uv run mypy src
cd ../frontend
npm run typecheck
npm run lint
npm test
npm run test:e2e
```

Notes:
- `uv run pytest` runs unit, contract, and integration tests with recorded/fake model responses.
- `npm run test:e2e` runs Playwright against the backend in `SLIDEX_FAKE_LLM=1` mode.

Contract test: `tests/contract/test_openapi_contract.py` compares the app's `/openapi.json` against `specs/001-slide-explainer/contracts/openapi.yaml` (paths, methods, status codes, schema names).

## Validation scenarios (live, costs money; run deliberately)

Fixtures live in `backend/tests/fixtures/decks/`:

| File | Contents |
|---|---|
| `clean_40.pptx` | Clear deck with speaker notes, a table, and 3 diagrams |
| `vague_25.pdf` | Keyword-only slides, an unlabelled diagram, a "see lecture" slide |
| `photos/` | 8 phone photos of slides (skew, glare) |
| `formulas_15.pdf` | Image-only slides with equations |

Each scenario lists its steps, what to expect, and the requirement it checks.

### US1 — Understand a deck, even a bad one

1. **Upload `clean_40.pptx`**, with context "Distributed Systems, intermediate".
   - Expect: 40 slides listed in order, each with a render, text, notes, and tables.
   - Checks: FR-001, FR-003.
2. **Upload `vague_25.pdf`**.
   - Expect: keyword slides rated `vague`, each with an interpretation and confidence; at least one `needs_input`.
   - Checks: FR-006, FR-007, FR-008.
3. **Enter a hint** on a `needs_input` slide.
   - Expect: the interpretation updates, confidence rises, and `learner_hint` is shown.
   - Checks: FR-008.
4. **Upload `photos/`** (8 images).
   - Expect: 8 slides with text recognized and unreadable regions listed; `ocr_path` shows `provider_vision` (`local_ocr` on the GPU laptop).
   - Checks: FR-004, FR-032.
5. **Open a diagram slide**.
   - Expect: each visual has a description plus "conveys".
   - Checks: FR-005.

### US2 — Research sources

1. **Click "Research"** on the `clean_40` deck.
   - Expect: the estimate shows topics, the budget, and stage costs; nothing runs until you confirm.
   - Checks: FR-009.
2. **Confirm**.
   - Expect: the event stream shows progress; each topic gets ranked sources with type, authority, and a reason; paywalled books appear under "Further reading".
   - Checks: FR-010, FR-011, FR-012.
3. **Add a local book PDF** (any open textbook, 200+ pages), then approve.
   - Expect: the book is processed into a tree (theme → chapter → cluster → passage) with page labels, and figures are listed with explanations.
   - Checks: FR-013, FR-014, FR-015.
4. **Inspect disagreements** (the `vague_25` fixture contains one deliberately wrong claim).
   - Expect: the disagreement is listed with both positions and an assessment.
   - Checks: FR-016.
5. **Injection check** (run offline with a test page).
   - Expect: a fixture page containing "ignore previous instructions…" is marked `blocked`.
   - Checks: FR-017.

### US3 — Explanation document

1. **Generate slide-by-slide PDF + DOCX** for `clean_40`.
   - Expect: slide order kept; slide image + blocks; every block cited; diagrams walked through; formulas step by step.
   - Checks: FR-018, FR-019, FR-022.
2. **Generate by-topic HTML + MD** for `vague_25`.
   - Expect: vague slides show "What the slide says" and "Reconstructed" with confidence; disagreements shown; a source list at the end.
   - Checks: FR-020, FR-025, FR-026.
3. **Search the PDF** for a concept that appears on 3 slides.
   - Expect: the full explanation appears once, with "see Slide N" elsewhere.
   - Checks: FR-023.
4. **Filler check**: `uv run slidex eval filler <doc_id>`.
   - Expect: 0 blacklisted phrases; the reviewer pass rate is at least 95%.
   - Checks: FR-024, SC-007.

### US4 — Q&A and quiz

1. **Ask a question** covered by slide 12.
   - Expect: an answer with a "Slide 12" citation.
   - Checks: FR-027.
2. **Ask something unrelated** to the deck.
   - Expect: `declined: true` plus an offer to research.
   - Checks: FR-027, SC-009.
3. **Start a quiz on slides 10–15 and answer wrong three times.**
   - Expect: hint → stronger hint → pointer; the answer is revealed only after that.
   - Checks: FR-028.
4. **Close the browser, reopen the quiz.**
   - Expect: the same question and hint level.
   - Checks: FR-029.

### Cross-cutting

- **Resume**: kill the backend mid-research, restart, then `POST /runs/{id}/resume`. Expect completed topics not re-fetched and CostEntry showing no duplicate charges (FR-030).
- **Cost**: after each run, compare `Run.cost_usd` with the estimate; they should be within ±30% (SC-010).
- **Errors**: remove `OPENAI_API_KEY`, then upload. Expect a `api_key_missing` problem with a fix instruction (FR-033).

## Evals (live, explicit)

```bash
cd backend
uv run slidex eval run --suite vague_interpretation
uv run slidex eval run --suite citations
uv run slidex eval run --suite diagrams
uv run slidex eval run --suite sources
uv run slidex eval run --suite refusal
```

| Suite | Threshold (spec) |
|---|---|
| `vague_interpretation` | ≥ 85% (SC-003) |
| `citations` | ≥ 95% (SC-002) |
| `diagrams` | ≥ 90% (SC-005) |
| `sources` | ≥ 90% (SC-006) |
| `refusal` | ≥ 95% (SC-009) |

Results are written to `backend/evals/results/<date>-<suite>.json`. A regression versus the last committed baseline fails the command.
