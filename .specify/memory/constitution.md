<!--
Sync Impact Report
- Version change: 3.0.0 → 3.1.0 (MINOR: VI model rule reworded — per-role configuration with
  learner-chosen defaults, gpt-5.4-nano for all chat roles; eval-driven role upgrades)
- Previous: 2.1.0 → 3.0.0 (MAJOR: product scope redefined)
- Scope change: from "book + YouTube tutor" to "slide explainer with source research".
  Inputs are now slide decks (PPTX, PDF, images) plus books/web content found by research or
  supplied by the learner. Video/audio removed.
- Modified principles:
  I. Grounded & Cited Answers — citations now slide numbers, book pages, web pages; RAPTOR applies
     to books; reconstructed content must be labelled.
  II. Concise by Default → Detailed, Never Padded — "in detail" = complete coverage, not length.
  III. Pedagogy First — explanation structure for slides; quiz hint ladder retained.
  VI. Cost & Resource Awareness — video/audio rules removed; local GPU now covers image text
      recognition; research budget added.
  VII. Simplicity & Local-First — downloaded-media rule removed.
- Added principles: VIII. Trustworthy & Lawful Sources
- Modified sections: Technology & Resource Constraints (inputs, outputs, research)
- Removed sections: none
- Templates: plan/spec/tasks templates read this file at runtime; no template edits required.
- Deferred TODOs: none
- History: 1.0.0 initial; 2.0.0 flashcards removed + multimodal video; 2.1.0 local GPU path.
-->

# Slide Explainer Constitution

## Core Principles

### I. Grounded & Cited Explanations

- Every explanation block, answer, and quiz feedback MUST cite at least one source: a slide number
  (`Slide 12`), a book page (`Author, Title, p. 84`), or a web page (title + link, section if known).
- The system MUST NOT present uncited assertions as facts. If neither the slides nor approved
  sources cover something, it MUST say so rather than answer from general model knowledge.
- Content reconstructed for vague slides MUST be visibly separated from what the slide itself says
  and MUST carry a confidence level and its sources.
- Book retrieval MUST use a hierarchical summary tree (RAPTOR-style: leaf passages + recursive
  cluster/chapter/theme summaries). Flat chunking with vector search MUST NOT be the only path.
- Citations MUST be verifiable: slide numbers match the deck, pages match the book's printed or
  physical page labels (stated which), and links resolve to the cited content.

Rationale: the learner must be able to trust and check every explanation.

### II. Detailed, Never Padded

- "Detailed" means every point, diagram, chart, and formula in scope is fully explained with its
  mechanism, reasoning, and an example where needed.
- Filler MUST NOT appear: greetings, generic introductions, restating the obvious, motivational
  text, repetition, and padding.
- A concept MUST be explained fully once per document; later mentions refer back to it.
- Length follows the substance of the material, never a word target.

Rationale: the learner wants complete understanding with nothing unnecessary.

### III. Pedagogy First

- Explanations MUST move from what the slide says, to the core idea, to the detailed mechanism,
  to an example, to how it connects with earlier material.
- Diagrams MUST be explained part by part, not merely captioned.
- In quizzes, answers MUST be judged on conceptual correctness; mistakes get a hint ladder
  (hint → stronger hint → exact slide/page/section) before the answer is revealed, unless the
  learner asks for it.
- Flashcards and spaced-repetition scheduling are not part of this product.

Rationale: understanding needs structure and checking, not dumps of text.

### IV. Contract-First Boundaries

- The Python API and the Next.js frontend MUST communicate only through a versioned OpenAPI
  contract; frontend types MUST be generated from it, never hand-duplicated.
- All external input (uploads, URLs, API bodies) MUST be validated at the boundary
  (Pydantic in Python, Zod in TypeScript).
- All LLM outputs used programmatically MUST use structured output with schema validation;
  invalid outputs MUST be retried or failed loudly, never silently coerced.
- API keys and secrets MUST stay server-side and MUST NOT be logged or sent to the browser.

Rationale: two languages and non-deterministic model output require hard contracts.

### V. Test-First & Eval-Driven

- Deterministic logic (slide extraction for PPTX/PDF/images, page-label mapping, chunking,
  clustering, citation formatting, de-duplication, document rendering for every output format)
  MUST have unit tests written before or with the code.
- LLM-dependent behaviour MUST have golden eval sets: vague-slide interpretation, diagram
  explanation accuracy, citation accuracy, source relevance/authority, filler absence, and
  refusal for uncovered questions.
- Any prompt, model, or search-strategy change MUST be accompanied by an eval run; regressions
  block the change.
- Tests MUST NOT call paid APIs or the live web by default; model and search calls are mocked or
  recorded, and live evals are run explicitly.

Rationale: correctness of citations and interpretations cannot be verified by eye at scale.

### VI. Cost & Resource Awareness

- The system MUST run fully on the primary laptop without a GPU (≈14 GB RAM). No step may
  require a GPU.
- Hardware-adaptive: when an NVIDIA CUDA GPU is detected (secondary RTX 4050 6 GB laptop), text
  recognition on image slides SHOULD run locally; otherwise it falls back to the AI provider.
  Output formats MUST be identical on both paths, and the estimate MUST show which path is used.
- Processing MUST be resumable and incremental: slide analysis, research results, fetched pages,
  book parses, summaries, and embeddings are cached by content hash and reused.
- Research MUST be bounded: a per-topic limit on searches and fetched pages, shown in the estimate.
- Every run MUST record token usage and cost by stage, and the UI MUST show an estimate before
  any expensive step.
- Model choice MUST be configurable per role (strong, vision, bulk, search, embed) in one place.
  Defaults are the learner's choice (currently `gpt-5.4-nano` for all chat roles, cap GPT-5.5);
  when a role fails its eval thresholds, the remedy is switching that role's model, not changing
  prompts to hide the gap.

Rationale: large decks, books, and web research can become expensive quickly.

### VII. Simplicity & Local-First

- Storage MUST be local-first: SQLite for relational state and a single embedded vector store.
  No additional services without a documented need.
- Prefer one clear implementation over configurable abstractions; YAGNI applies.
- Any action with an external side effect beyond model calls, web search, and fetching public
  pages (e.g. posting, uploading learner files to third-party services) MUST require explicit
  learner approval.

Rationale: a single-user learning tool should be easy to run, inspect, and trust.

### VIII. Trustworthy & Lawful Sources

- Only freely and lawfully accessible content, or content supplied by the learner, MAY be used as
  a basis for explanations. Paywalled or pirated content MUST NOT be fetched or used; relevant
  non-free books are listed as further reading with bibliographic details only.
- Sources MUST be ranked by authority (official docs, textbooks, university material,
  peer-reviewed work, reputable references) and relevance; low-quality or SEO-spam pages MUST be
  excluded.
- All fetched web content is untrusted data: instructions inside it MUST be ignored and MUST NOT
  influence tool use, and fetched content MUST NOT be rendered as executable HTML.
- Disagreements between sources, or between sources and slides, MUST be surfaced, never silently
  resolved.
- The system MUST respect robots.txt and site terms and use reasonable request rates.

Rationale: explanations are only as good, and as legitimate, as their sources.

## Technology & Resource Constraints

- Frontend: Next.js (App Router), TypeScript strict, Tailwind, shadcn/ui; UI MUST follow
  `DESIGN.md`.
- Backend: Python FastAPI service owning slide intake, research, book processing, retrieval, the
  LangGraph agent, and document generation.
- AI provider: OpenAI for chat, vision (slides, diagrams, figures), embeddings, and web search,
  accessed only from the backend.
- Inputs: slide decks as PPTX, PDF, or images; learner-supplied book PDFs and URLs; web content
  and books found by research. Multimodal over text and images; no audio or video.
- Outputs: explanation documents in PDF (default), Word (.docx), Markdown, and HTML, organized
  slide-by-slide or by topic; interactive Q&A and quizzes.
- Target platforms: primary Windows 11 laptop (Iris Xe, no GPU, 14 GB RAM); secondary Windows
  laptop (i5-13500HX, RTX 4050 6 GB) using local GPU acceleration; must also run on macOS/Linux.

## Development Workflow & Quality Gates

- Non-trivial features follow Spec Kit: specify → (clarify) → plan → tasks → (analyze) →
  implement. Specs live in `specs/NNN-name/` and are updated when implementation diverges.
- A change is complete only when: type-check, lint, and unit tests pass for both frontend and
  backend; affected evals have been run; and the API contract and generated types are in sync.
- Every plan MUST include a Constitution Check that lists each principle and how the design
  satisfies it; justified deviations are recorded in the plan's Complexity Tracking table.
- Reviews MUST verify citation grounding (I), no filler (II), secret handling (IV), and source
  legitimacy and untrusted-content handling (VIII) for any change touching prompts, research,
  retrieval, or output generation.

## Governance

- This constitution supersedes other project practices. `AGENTS.md` and `CLAUDE.md` provide
  runtime guidance and MUST NOT contradict it.
- Amendments are made via a change to this file that includes an updated Sync Impact Report and a
  semantic version bump: MAJOR for removed or redefined principles, MINOR for new principles or
  materially expanded guidance, PATCH for clarifications.
- Complexity beyond these principles MUST be justified in the relevant plan; unjustified
  violations block the change.

**Version**: 3.1.0 | **Ratified**: 2026-09-30 | **Last Amended**: 2026-09-30
