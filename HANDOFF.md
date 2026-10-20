# Handoff: Slide Explainer (paste everything below into the cloud session)

---

You are continuing work on **Slide Explainer**, repo `ishmam259/slide-explainer` (public, branch
`main`, latest commit `258c610`). Read `AGENTS.md`, `CLAUDE.md` and `README.md` first. Specs are in
`specs/001-slide-explainer/`; live-run results are in `specs/001-slide-explainer/validation.md`.

## Context

- This is my AI Workshop final project (solo): **A K M Ishmam Tahmid, ID 220041259**.
  **Submission deadline: 20 October 2026 (today).** Judges need: a presentation video (I record
  it myself), testable access (the GitHub repo plus `start.ps1` / `start.sh`), and a README with
  name, ID, title, description and tools (done).
- Submission folder name: `SlideExplainer-AKMIshmamTahmid_220041259`.
- The product is an agentic AI tool. It reads lecture slides (PPTX/PDF/images), interprets vague
  slides, researches lawful open sources, and writes a cited explanation document
  (PDF/Word/MD/HTML), plus grounded Q&A and quizzes.
  - Backend: Python 3.14 + uv, FastAPI, LangGraph, OpenAI `gpt-5.4-nano`.
  - Frontend: Next.js 16 + shadcn.

## Current state (all verified on 2026-10-18)

- `uv run pytest` passes (213 tests, offline: fake model and mocked web). `ruff check`,
  `mypy src` (strict), `npm run typecheck` and `npm run lint` are clean.
- **Demo mode** (`./start.sh` or `.\start.ps1`, no key) runs the whole workflow end to end using
  `SLIDEX_FAKE_LLM=1` and `SLIDEX_DEMO_WEB=1`. `SLIDEX_DEMO_WEB` serves placeholder pages from
  `backend/src/slidex/demo_web.py`. The header shows "demo mode · simulated costs".
- **Live run done:** `samples/vague-lecture.pdf` produced `samples/output/vague-lecture-explained.*`
  (64 pages, every block cited, slide 15's wrong CAP claim corrected). It cost $0.52 in total; a
  clean run costs about $0.40 with `SLIDEX_MAX_TOPICS=6 SLIDEX_SEARCHES_PER_TOPIC=1
  SLIDEX_PAGES_PER_TOPIC=3`.
- Live Q&A was verified: a covered question gets a cited answer, an off-topic question gets
  `answer.declined`.

## Not available in the cloud session

- **OpenAI key:** `backend/.env` is not in the repo. I've set `OPENAI_API_KEY` as an environment
  variable in this cloud environment, and the backend reads it from there (pydantic-settings).
  - Check it with `uv run python -c "from slidex.core.config import get_settings as g; print(bool(g().openai_api_key))"`.
    Never print, log, echo or commit the key itself, and never write it into a file.
  - If it isn't set, don't ask me to paste it in chat. Tell me, and keep working offline.
  - **Live budget for this whole session: $0.75.** Tests stay offline (`SLIDEX_FAKE_LLM=1`).
  - For live runs, always use `SLIDEX_MAX_TOPICS=6 SLIDEX_SEARCHES_PER_TOPIC=1
    SLIDEX_PAGES_PER_TOPIC=3`, and leave books over 300 pages unapproved.
  - Read the stage estimates (`GET /decks/{id}/estimate?stage=…`) before confirming anything.
  - Track spend with `SELECT sum(usd) FROM cost_entry` and stop at $0.70.
  - Tell me the cost of each live step.
- `data-live-sample/` (the processed live deck) and `VIDEO_SCRIPT.md` exist only on my laptop.
- LibreOffice may be missing, which affects PPTX intake only. Run
  `uv run playwright install chromium` before tests that render PDFs.

## Open tasks (pick in this order; stop and report if the time runs short)

1. **Sanity check (do first).** Fresh clone, then `cd backend && uv sync && uv run pytest`;
   `cd frontend && npm install && npm run typecheck && npm run lint && npm test`. Then run
   `./start.sh` and confirm demo mode works end to end:
   upload `samples/vague-lecture.pdf`, confirm research, approve sources, generate PDF and DOCX,
   ask a question. Fix anything a judge would hit.
   Then do one **live** check: `./start.sh --live`, upload `samples/vague-lecture.pdf` with the
   budget settings above, and run it to a PDF. Expect about $0.40. Compare the result with
   `samples/output/vague-lecture-explained.pdf`. Don't overwrite the committed sample unless the
   new output is clearly better and I say yes.
2. **T096:** Vitest unit tests in `frontend/tests/unit/`:
   - clarity-badge: icon and label present
   - estimate-card: totals, mono numbers
   - citation-chip: links
   - quiz-panel: answer hidden until hint_level 3 or explicit reveal
   - Zod upload form
3. **T053 / T054 / T087:** backend unit tests in `backend/tests/unit/`.
   - `test_index.py`: cosine top-k vs a NumPy reference; collapsed tree respects the token budget.
   - `test_estimate.py`: stage formulas; calibration EMA moves the ratio toward actual/estimated.
   - `test_quiz.py`: hint ladder 0→3, pointer at level 3, a correct answer resets, resume keeps state.
   Use the `app_ctx` fixture in `tests/conftest.py`.
4. **T095:** `backend/tests/integration/test_resume.py`: no duplicate CostEntry after a resume.
5. **T098:** accessibility pass. Known issue: the format checkboxes on the Document tab have no
   accessible name (Base UI checkbox next to a label). Read DESIGN.md before any UI change.
6. **T093 / T086:** the eval suites and `slidex eval run` / `slidex eval filler` are still stubs
   that exit with code 2. Low priority for the deadline.
7. When done, tick the finished tasks in `specs/001-slide-explainer/tasks.md`.
   - Tasks still open there: T047, T053, T054, T086, T087, T093, T095, T096, T097, T098, T100
     (partly done; see validation.md).
   - Done but not yet ticked: T027, T049, T051, T099. Tick those too.
   - Update GitHub issues #1–#9 to match.

## Rules

- Commit with conventional prefixes and push to `main` only after tests, lint and types pass.
  Don't add attribution lines to commits.
- Never commit `.env*`, `data/` or `data-*/`.
- Tests must never call paid APIs or the live web. Live calls happen only in the deliberate
  demo run above, within the $0.75 budget.
- Prompt changes are versioned by text: the model cache key includes the instructions.
- Every change you claim is done: state what you ran and the result.
