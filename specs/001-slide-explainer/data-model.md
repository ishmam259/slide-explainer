# Data Model: Slide Explainer with Source Research

**Feature**: `001-slide-explainer` · **Storage**: a single SQLite database (`data/slidex.db`, WAL) plus a content-addressed file store (`data/files/<sha256[:2]>/<sha256>.<ext>`). See [research.md](research.md) R8, R9 and R13.

IDs are ULIDs (sortable text) unless noted. Timestamps are ISO-8601 UTC. `*_hash` = SHA-256 hex. JSON columns hold Pydantic-validated payloads.

## Entity overview

```
Deck 1─* Slide 1─* Visual
Deck 1─* Topic *─* Slide                (topic_slide)
Deck 1─* DeckSource *─1 Source          (approval state per deck)
Source 1─* BookNode (tree)   Source 1─* WebSection   BookNode/WebSection 1─1 Embedding
Source 1─* Visual (book figures)
Topic *─* Source (via DeckSource.topic_ids)
Deck 1─* Disagreement
Deck 1─* ExplanationDocument 1─* DocSection
Deck 1─* QaThread 1─* QaTurn ; Deck 1─* QuizSession 1─* QuizItem
Deck 1─* Run 1─* CostEntry
Cache: ModelCallCache (content-hash keyed), FetchCache
```

## Deck

| Field | Type | Rules |
|---|---|---|
| id | ULID | PK |
| title | text | 1–200 chars; defaults to the file title or first slide title |
| file_kind | enum `pptx \| pdf \| images` | |
| file_hashes | JSON `list[str]` | uploaded originals (images: one per file, in order) |
| context | JSON `DeckContext` | `course?`, `level?` (`intro \| intermediate \| advanced \| graduate`), `topic?`, `notes?` (≤ 2000 chars) |
| slide_count | int | 1–300 (FR-001) |
| status | enum | see state machine |
| created_at, updated_at | ts | |

**State machine** (`status`):
`uploaded → extracting → awaiting_input? → ready_for_research → awaiting_research_confirm → researching → awaiting_source_approval → processing_sources → ready → generating → ready`.
Any state can go to `failed` (with `error`) and back to its previous state on resume. `awaiting_input` happens only when slides are `needs_input` and the learner chooses to answer; the learner may skip.

## Slide

| Field | Type | Rules |
|---|---|---|
| id | ULID | PK |
| deck_id | FK Deck | |
| number | int | 1-based, unique per deck |
| image_hash | str | 150-DPI PNG render |
| native_text | text | from the PPTX/PDF text layer; empty for images |
| notes | text | speaker notes (PPTX) |
| extraction | JSON `SlideExtraction` | see below; null until extracted |
| clarity | enum `clear \| vague \| unreadable \| divider` | from extraction |
| interpretation | JSON `SlideInterpretation?` | only for vague/unreadable |
| needs_input | bool | `interpretation.confidence < 0.5` |
| learner_hint | text? | ≤ 500 chars; setting it re-runs interpretation for this slide |
| ocr_path | enum `native \| local_ocr \| provider_vision` | FR-032 transparency |
| extraction_hash | str | hash(image_hash + native_text + notes + prompt_version) → cache key |

`SlideExtraction`: `text` (cleaned, reading order), `formulas: [{latex, unreadable: bool}]`, `tables: [{rows: list[list[str]]}]`, `visuals: [{id, kind: diagram|chart|photo|screenshot|code|other, description, conveys, unreadable_parts?}]`, `topic`, `concepts: list[str]` (1–12), `clarity`, `unreadable_regions: list[str]`.

`SlideInterpretation`: `meaning` (≤ 1200 chars), `confidence` (0–1), `rationale`, `used: {neighbours: list[int], context: bool, hint: bool}`.

## Visual

Covers slide visuals and book figures (FR-005, FR-015).

| Field | Type | Rules |
|---|---|---|
| id | ULID | PK |
| origin | enum `slide \| book` | |
| slide_id | FK? | when origin = slide |
| source_id | FK? Source | when origin = book |
| page_label, page_index | text?, int? | book figures; `label_kind: printed \| physical` |
| bbox | JSON `[x0,y0,x1,y1]` | page coordinates |
| image_hash | str | crop render (200 DPI) |
| kind | enum | as in SlideExtraction |
| caption | text? | nearest "Figure/Fig./Table …" block |
| explanation | text | part-by-part explanation |
| decorative | bool | skipped from outputs when true |

## Topic

| Field | Type | Rules |
|---|---|---|
| id | ULID | PK |
| deck_id | FK | |
| name | text | unique per deck (case-insensitive) |
| slide_numbers | JSON `list[int]` | non-empty |
| research_status | enum `pending \| searching \| done \| no_reliable_source` | FR/US2-AS5 |
| queries | JSON `list[str]` | ≤ 2 (budget, R6) |

## Source

Global (reusable across decks; deduplicated by `url_normalized` or `file_hash`).

| Field | Type | Rules |
|---|---|---|
| id | ULID | PK |
| kind | enum `book \| documentation \| paper \| lecture_notes \| article \| encyclopedia \| other` | |
| origin | enum `web \| learner_file \| learner_url \| open_library` | |
| title, authors, publisher, year | text / JSON / text / int? | bibliographic fields |
| url, url_normalized | text? | unique when present |
| file_hash | str? | learner PDFs and downloaded open PDFs |
| isbn | text? | Open Library records |
| access | enum `usable \| further_reading \| blocked` | FR-011; `blocked` = robots/paywall/injection/spam |
| blocked_reason | text? | |
| content_hash | str? | of the extracted text; cache key for processing |
| page_count | int? | books |
| processing_status | enum `pending \| fetching \| processing \| ready \| failed` | |

## DeckSource (per-deck selection and ranking)

| Field | Type | Rules |
|---|---|---|
| deck_id, source_id | FKs | composite PK |
| topic_ids | JSON `list[ULID]` | topics it supports |
| relevance, authority | float 0–1 | R6 ranking |
| reason | text | ≤ 200 chars, shown to the learner |
| added_by | enum `research \| learner` | |
| approved | bool | default true for research top-5; learner can toggle (FR-013) |

## BookNode (RAPTOR tree)

| Field | Type | Rules |
|---|---|---|
| id | ULID | PK |
| source_id | FK | |
| level | int | 0 = leaf passage; increasing upwards; `kind: passage \| cluster \| chapter \| theme` |
| parent_ids | JSON `list[ULID]` | soft clustering allows multiple parents |
| text | text | leaf text or summary |
| page_start, page_end | text | page labels; `label_kind` |
| token_count | int | |
| figure_ids | JSON `list[ULID]` | figures on covered pages |

## WebSection

Chunked content of fetched web pages and short PDFs.

| Field | Type | Rules |
|---|---|---|
| id | ULID | PK |
| source_id | FK | |
| heading_path | text | e.g. "Consistency › CAP theorem" (for citation anchors) |
| anchor | text? | URL fragment if found |
| text | text | ≤ 400 tokens |
| order | int | |

## Embedding

| Field | Type | Rules |
|---|---|---|
| owner_type | enum `book_node \| web_section \| slide \| concept` | |
| owner_id | ULID | composite PK with owner_type |
| model | text | e.g. `text-embedding-3-small` |
| dim | int | 1536 |
| vector | BLOB float32 | length = dim × 4 |

## Disagreement

| Field | Type | Rules |
|---|---|---|
| id | ULID | PK |
| deck_id | FK | |
| topic_id | FK | |
| claim | text | |
| positions | JSON `list[{statement, evidence_ids: list[str]}]` | ≥ 2 entries |
| involves_slide | int? | slide number when a slide is one side |
| assessment | text | which position is better supported and why |

## ExplanationDocument

| Field | Type | Rules |
|---|---|---|
| id | ULID | PK |
| deck_id | FK | |
| organization | enum `by_slide \| by_topic` | |
| formats | JSON `list[pdf \| docx \| md \| html]` | ≥ 1 |
| slide_range | JSON `[from, to]?` | defaults to all |
| status | enum `queued \| generating \| rendering \| ready \| failed` | |
| content | JSON `ExplanationDocumentModel` | canonical model (R11) |
| files | JSON `{format: file_hash}` | rendered outputs |
| cost_usd | decimal | |
| created_at | ts | earlier versions are kept (spec edge case) |

`ExplanationDocumentModel` → `sections: [DocSection]`, `sources: [SourceRef]`, `further_reading: [SourceRef]`.
`DocSection`: `slide_numbers`, `title`, `slide_image_hash?`, `blocks: [Block]`.
`Block` (discriminated union on `type`):
- `slide_says` (text)
- `explanation` (markdown)
- `diagram` (visual_id, markdown)
- `formula` (latex, steps markdown)
- `example` (markdown)
- `connection` (markdown, refers_to_slides)
- `refer_back` (concept, slide)
- `reconstructed` (markdown, confidence)
- `disagreement` (disagreement_id)
- `book_figure` (visual_id, markdown)

Every block except `refer_back` must have `citations: list[EvidenceRef]` with length ≥ 1 (FR-022).
`EvidenceRef`: `{kind: slide|book|web, slide?: int, source_id?, page_label?, section_id?, url?}`.

## QaThread / QaTurn (US4)

- **QaThread**: `id`, `deck_id`, `created_at`.
- **QaTurn**: `id`, `thread_id`, `role: learner|assistant`, `text`, `citations: list[EvidenceRef]`, `declined: bool` (uncovered → FR-027), `created_at`.

## QuizSession / QuizItem (US4)

- **QuizSession**: `id`, `deck_id`, `slide_from`, `slide_to`, `status: active|completed`, `current_index`.
- **QuizItem**:

  | Field | Type | Rules |
  |---|---|---|
  | id | ULID | PK |
  | session_id | FK | |
  | index | int | position in the quiz |
  | question | text | |
  | reference_answer | text | hidden from the learner until revealed |
  | evidence | JSON `list[EvidenceRef]` | |
  | attempts | JSON `list[{answer, verdict: correct\|partial\|incorrect, misconception?, hint_level}]` | |
  | hint_level | int 0–3 | 3 = pointer to exact slide/page/section |
  | revealed | bool | only after hint_level = 3 or an explicit request (FR-028) |

## Run / CostEntry

- **Run**: `id`, `deck_id`, `kind: extract|research|process_sources|generate|qa`, `status: running|paused|completed|failed`, `estimate: RunEstimate`, `started_at`, `ended_at`, `error?`.
  - `RunEstimate` = `{stages: [{stage, model, calls, input_tokens, output_tokens, tool_calls, usd, path: provider|local}], total_usd}`
- **CostEntry**: `run_id`, `stage` (`slide_extraction | interpretation | research_search | research_fetch_rank | book_processing | figure_explanation | explanation | render | qa`), `model`, `input_tokens`, `cached_tokens`, `output_tokens`, `tool_calls`, `usd`, `at`.

## Caches

- **ModelCallCache**: `key = sha256(model + prompt_version + canonical input JSON + image hashes)` → `output JSON`, `usage`. Used by every model call (FR-030).
- **FetchCache**: `url_normalized` → `status`, `content_type`, `text_hash`, `fetched_at`, `robots_allowed`. Re-fetched after 30 days.
- **Calibration**: `stage` → `ratio_ema` (actual/estimated), used by the estimator (R10).

## Validation rules traced to requirements

| Rule | Requirement |
|---|---|
| Upload type in {pptx, pdf, png, jpg, jpeg, webp}; ≤ 300 slides; ≤ 200 MB/file | FR-001, R15 |
| Every non-`refer_back` block has ≥ 1 citation, and each citation resolves to a known slide/BookNode/WebSection/Visual | FR-022, Constitution I |
| `reconstructed` blocks only on vague/unreadable slides, with a confidence | FR-020 |
| A concept is fully explained in exactly one section; other sections use `refer_back` | FR-023 |
| Sources with `access ≠ usable` are never used as evidence | FR-011, Constitution VIII |
| Quiz answer not revealed while `hint_level < 3`, unless the learner explicitly requests it | FR-028 |
| Model IDs must be in `ALLOWED_MODELS` (≤ GPT-5.5) | R1 |
