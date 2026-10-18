# Validation — live run (T100, partial)

**Date:** 2026-10-17 · **Deck:** `samples/vague-lecture.pdf` (25 slides, deliberately vague) ·
**Models:** gpt-5.4-nano for every chat role, text-embedding-3-small ·
**Budget:** 6 topics × 1 search × 3 pages (reduced to stay under a $0.75 cap) ·
**Output:** `samples/output/vague-lecture-explained.{pdf,docx,html,md.zip}`

## Offline suites

`uv run pytest` — 213 passed (fake model, mocked web, no cost). `ruff check`, `mypy src`
(strict), `npm run typecheck`, `npm run lint` — clean.

## Live results

| Stage | Cost (USD) | Notes |
|---|---|---|
| Slide extraction (×2: re-run after a prompt fix) | 0.0416 | 25 slides, vision |
| Interpretation of vague slides | 0.0100 | 18 vague slides reconstructed with confidence |
| Research: search | 0.2856 | 12 search requests → 25 web-search tool calls ($0.01 each) |
| Research: fetch, safety, rank | 0.0163 | 8 usable open sources (MIT OCW ×4, LibreTexts ×2, Wikipedia, MIT OCW book) |
| Explanation (four generations while fixing bugs, last one at medium effort) | ~0.163 | 19 sections, 64-page PDF, 0 uncited blocks |
| **Total** | **0.517** | one clean end-to-end pass would cost about **$0.40** |

An 826-page MIT OCW book was found but left unapproved: indexing it would have cost
~$0.24 and broken the cap.

### Estimate vs actual

| Stage | Estimate | Actual | |
|---|---|---|---|
| Research | $0.173 | $0.302 | +75%: each search request ran ~2 web searches. Fixed: `TOOL_CALLS_PER_SEARCH = 2` in `estimate.py` (the per-stage calibration EMA also corrects this automatically after runs) |
| Generate (low effort) | $0.144 | $0.044 | −69%: estimate is conservative |

Outside ±30% for both stages before the fix; the research estimate is now within range.

## Bugs found only by the live run (all fixed, with regression tests)

1. **Document generation failed**: the explanation schema used a pydantic discriminated
   union → JSON Schema `oneOf`, which OpenAI structured outputs reject. Now a plain union;
   `tests/unit/test_schemas_openai.py` checks every output schema in strict mode.
2. **17/25 slides classified as `divider`** (single-phrase slides like "Quorums" were treated
   as section headers and skipped). Extraction prompt tightened → 18 vague, 6 divider, 1 clear.
3. **A wrong slide claim was restated as true** (slide 15, CAP "all three at the same time").
   Explanation prompt now requires a **Correction:** block; at low effort nano still softened it,
   at medium effort (the default) it states the correction with a citation.
4. Section titles repeated the number ("Slide 2: Slide 2 · …"); citation lines repeated the same
   source; empty "Diagram ()" blocks on slides without visuals. Fixed in `assemble.py`,
   `render/__init__.py::cited`, `explain/slide.py`.

## Not yet done

Eval suites (T093) and baselines; a live run of `clean_40.pptx` (needs LibreOffice, present on
this machine).
