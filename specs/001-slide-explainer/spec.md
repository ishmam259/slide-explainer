# Feature Specification: Slide Explainer with Source Research

**Feature Branch**: `001-slide-explainer`

**Created**: 2026-09-30

**Status**: Draft

**Input**: User description: "The AI agent checks the learner's slides (PPTX, PDF, or images), finds relevant books and content on the internet, and then explains the slides in detail in a PDF or any other file format needed. Slides can be very bad or very vague. It explains slides and books in detail, with no unnecessary content. Book and slide diagrams must be explained too. Multimodal: text and images. No flashcards. No YouTube."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand a slide deck, even a bad one (Priority: P1)

The learner uploads a lecture deck — a PowerPoint file, a PDF, or a set of slide images (photos or screenshots). Optionally they add context: course name, level, and what the lecture is about. The system reads every slide: text, speaker notes, tables, formulas, and images. Diagrams, charts and pictures are interpreted; image-only slides are read with text recognition. It then shows the deck's structure: each slide's topic, the concepts it touches, and a clarity rating. Vague slides (a few keywords, fragments, "see lecture", unlabelled diagrams, low-resolution screenshots) are flagged, and the system proposes what each one is most likely about, based on the neighbouring slides, the deck title, and the course context.

**Why this priority**: Everything else depends on correctly understanding the slides — especially poor ones, which are the reason the learner needs help.

**Independent Test**: Upload a 40-slide deck that includes keyword-only slides, an unlabelled diagram, and a photographed slide; verify every slide is listed with extracted content, topic, clarity rating, and that vague slides get a plausible, clearly-marked interpretation.

**Acceptance Scenarios**:

1. **Given** a PPTX deck, **When** it is uploaded, **Then** the system extracts each slide's text, speaker notes, tables, formulas, and images in slide order.
2. **Given** a deck of slide photos or an image-only PDF, **When** it is uploaded, **Then** the text on each slide is recognized and the slides are processed like any other deck.
3. **Given** a slide containing a diagram, chart, or picture, **When** it is processed, **Then** the system describes what the visual shows and what it is meant to convey.
4. **Given** a slide with only keywords (e.g. "CAP — tradeoffs — Dynamo"), **When** it is processed, **Then** it is marked "vague", and the system proposes the likely intended topic and meaning, using neighbouring slides and course context, labelled as an interpretation with a confidence level.
5. **Given** a slide the system cannot interpret with reasonable confidence, **When** the deck overview is shown, **Then** that slide is flagged "needs your input" and the learner can type a one-line hint that is used from then on.

---

### User Story 2 - Research relevant books and web sources (Priority: P1)

For the topics found in the deck, the system searches for relevant sources: books (open textbooks and freely available book content, plus bibliographic references for others), and web content (official documentation, university lecture notes, papers, reputable encyclopedias and tutorials). It shows a ranked source list per topic, explaining why each source was picked. The learner can remove sources, add their own (book PDFs, URLs), and approve. Before anything expensive runs, the learner sees an estimated cost.

**Why this priority**: Vague slides can only be explained properly with good outside sources; the learner explicitly asked for the agent to find books and internet content.

**Independent Test**: With a processed deck, run research; verify each topic has ranked, relevant, accessible sources with reasons, that the learner can add a local book PDF and remove a source, and that the cost estimate appears before research runs.

**Acceptance Scenarios**:

1. **Given** a processed deck, **When** the learner starts research, **Then** the system shows the topics it will research and an estimated cost, and waits for confirmation.
2. **Given** research completes, **When** the learner opens the source list, **Then** each topic shows its sources ranked by relevance and authority, each with title, author/publisher, type (book, documentation, paper, notes, article), link, and a one-line reason.
3. **Given** a relevant book whose full text is not freely available, **When** it is found, **Then** it is listed as "Further reading" with its reference details, and its content is not used as a basis for explanations.
4. **Given** the learner adds their own book PDF, **When** it is processed, **Then** it is organized into a multi-level summary hierarchy (sections → chapters → themes) with page references and becomes a ranked source for matching topics, including its figures and diagrams.
5. **Given** a topic for which no trustworthy source is found, **When** research completes, **Then** the topic is marked "No reliable source found" rather than filled with unsupported content.
6. **Given** two sources that disagree with each other or with a slide, **When** research completes, **Then** the disagreement is recorded and later surfaced in the explanation.

---

### User Story 3 - Get a detailed explanation document (Priority: P1)

The learner chooses the output format (PDF by default; also Word, Markdown, or HTML) and the organization (slide-by-slide by default, or grouped by topic). The system produces a document that explains the deck in detail: for each slide, what the slide says, a thorough explanation of every point, each diagram or chart explained, formulas explained step by step, a worked example where the concept needs one, and how the slide connects to the previous ones. Book figures relevant to a slide are included and explained. Vague slides get a reconstructed explanation, clearly separated from what the slide itself says. Every explanation cites its sources (slide number, book page, or web page). There is no filler — no greetings, restating the obvious, repetition, or padding.

**Why this priority**: This document is the learner's main deliverable.

**Independent Test**: For a researched deck, generate a PDF (slide-by-slide) and a Word file (by topic); verify structure, detail, diagram explanations, clear marking of reconstructed content, citations, and absence of filler and repetition.

**Acceptance Scenarios**:

1. **Given** a researched deck, **When** the learner generates a slide-by-slide PDF, **Then** the document follows slide order, each section shows the slide (as an image) followed by its explanation, and every explanation carries at least one citation.
2. **Given** a slide with a diagram, **When** it is explained, **Then** the explanation walks through the diagram's parts and what it demonstrates.
3. **Given** a vague slide, **When** it is explained, **Then** the document shows "What the slide says" and "Full explanation (reconstructed from sources)" separately, with the interpretation's confidence and the sources used.
4. **Given** a concept repeated across several slides, **When** the document is generated, **Then** it is explained fully once and later slides refer back to that explanation instead of repeating it.
5. **Given** a book figure that explains a slide's concept better than the slide, **When** the document is generated, **Then** the figure is included with its page citation and its own explanation.
6. **Given** a source disagreement recorded during research, **When** the related slide is explained, **Then** the document states both positions with their citations and which is better supported.
7. **Given** the learner selects Word, Markdown, or HTML, **When** generation completes, **Then** the file has the same content and structure as the PDF, with images and citations preserved.

---

### User Story 4 - Ask follow-up questions and check understanding (Priority: P2)

After reading the document, the learner can ask questions about any slide or concept. Answers come only from the deck and the approved sources, with citations. The learner can also ask to be tested: the system asks targeted questions on a slide range, judges answers on concepts rather than keywords, and responds to mistakes with graduated hints that point to the exact slide, page, or web section before revealing the answer. Progress is saved so the learner can resume later.

**Why this priority**: Useful for learning the material, but the document already delivers the core request.

**Independent Test**: Ask one covered and one uncovered question; request a quiz on 5 slides; answer one question wrong; verify citations, refusal for uncovered topics, hint behaviour, and resume after closing.

**Acceptance Scenarios**:

1. **Given** a question covered by the deck or sources, **When** the learner asks it, **Then** the answer cites the slide number and/or source.
2. **Given** a question not covered by the deck or approved sources, **When** the learner asks it, **Then** the system says so and offers to research it, instead of answering from unsupported knowledge.
3. **Given** a wrong answer in a quiz, **When** the learner responds, **Then** the system names the misconception and gives a hint, then a stronger hint, then the exact slide/page/section to review, and reveals the answer only after that or when the learner asks.
4. **Given** a quiz in progress, **When** the learner leaves and returns, **Then** it resumes at the same question.

---

### Edge Cases

- **Keyword-only or fragment slides**: interpreted from context (neighbouring slides, deck title, course context, speaker notes) and explained from sources; always labelled as reconstructed, with confidence.
- **Slides that contradict sources** (errors in the slides): the explanation notes the discrepancy politely, shows what reliable sources say, and cites them; the slide's content is never silently "corrected".
- **Unlabelled or low-quality diagrams**: described as far as they can be read; ambiguous parts are named as ambiguous rather than guessed.
- **Photos of slides** (skewed, glare, partial, handwritten annotations): text is recognized where readable; unreadable regions are reported per slide.
- **Very large decks (150+ slides) or many decks at once**: the estimate reflects the full size; the learner can select a slide range.
- **Decks mixing unrelated topics**: topics are researched separately; the document groups them clearly.
- **Slides that are pure title/section dividers or "Questions?" slides**: kept as structure markers, not explained.
- **Embedded video/audio in PPTX, animations, and slide builds**: animations are flattened to the final state; embedded media is noted but not analysed.
- **Formulas as images or poorly typeset**: recognized and rendered cleanly in the output; unreadable formulas are flagged.
- **Paywalled or unavailable sources**: listed as further reading only; never used as a basis for explanations.
- **Web pages containing instructions aimed at AI agents or misleading content**: treated as untrusted data; such instructions are ignored, and low-quality pages are down-ranked or excluded.
- **No trustworthy source for a topic**: the slide is explained from the slide itself and marked "No outside source found — explanation limited to the slide".
- **The AI provider or search is unavailable, rate-limited, or the API key is missing/invalid**: a specific error is shown and work can resume later without losing progress.
- **Non-English slides**: out of scope for this version (see Assumptions); the learner is told clearly.

## Requirements *(mandatory)*

### Functional Requirements

**Slide intake & understanding**

- **FR-001**: Learners MUST be able to upload slide decks as PowerPoint (.pptx), PDF, or images (PNG/JPG, single or multiple), up to at least 300 slides per upload.
- **FR-002**: Learners MUST be able to optionally provide context: course name, level, lecture topic, and free-text notes.
- **FR-003**: The system MUST extract, per slide and in order: text, speaker notes, tables, formulas, and embedded images; animations are flattened to their final state.
- **FR-004**: The system MUST recognize text on image-only slides and photographed slides, and report unreadable regions per slide.
- **FR-005**: The system MUST interpret every diagram, chart, and picture on a slide, describing what it shows and what it is meant to convey.
- **FR-006**: The system MUST assign each slide a topic, the concepts it covers, and a clarity rating (clear, vague, unreadable); title/divider slides MUST be recognized as structure.
- **FR-007**: For vague slides, the system MUST propose the intended meaning using neighbouring slides, deck title, speaker notes, and learner context, labelled as an interpretation with a confidence level.
- **FR-008**: Slides the system cannot interpret with reasonable confidence MUST be flagged "needs your input", and learner hints MUST be applied to that slide's interpretation.

**Source research**

- **FR-009**: Before research, the system MUST show the list of topics to research and an estimated cost, and MUST wait for confirmation.
- **FR-010**: The system MUST search for relevant books and web content per topic, preferring authoritative sources (official documentation, textbooks, university material, peer-reviewed papers, reputable references).
- **FR-011**: The system MUST only use content that is freely and lawfully accessible (or supplied by the learner) as a basis for explanations; other relevant books MUST be listed as "Further reading" with bibliographic details only.
- **FR-012**: The system MUST present sources per topic ranked by relevance and authority, each with title, author/publisher, type, link or file, and a one-line reason for inclusion.
- **FR-013**: Learners MUST be able to remove sources, add their own book PDFs and URLs, and approve the source list before explanations are generated.
- **FR-014**: Learner-supplied and freely available books MUST be organized into a multi-level summary hierarchy (passage → section → chapter → themes) with page references, so both broad and precise content can be found.
- **FR-015**: The system MUST detect figures and diagrams in books (including drawn/vector figures), capture each with its page and caption, and produce an explanation of what it shows.
- **FR-016**: The system MUST record disagreements between sources, or between a source and a slide, with the evidence on each side.
- **FR-017**: The system MUST treat all web content as untrusted: instructions contained in pages MUST be ignored, and low-quality or manipulative pages MUST be excluded.

**Explanation document**

- **FR-018**: Learners MUST be able to choose the output format — PDF (default), Word (.docx), Markdown, or HTML — and the organization — slide-by-slide (default) or by topic.
- **FR-019**: For each explained slide, the document MUST include: the slide image, what the slide says, a detailed explanation of each point, explanations of every diagram/chart, step-by-step explanation of formulas, a worked example where the concept requires one, and how the slide connects to earlier slides.
- **FR-020**: For vague slides, the document MUST separate "What the slide says" from "Full explanation (reconstructed from sources)", and show the interpretation's confidence.
- **FR-021**: Relevant book figures MUST be included with their page citation and an explanation when they clarify a slide's concept.
- **FR-022**: Every explanation block MUST cite at least one source: slide number, book title and page, or web page title and link.
- **FR-023**: Concepts appearing on several slides MUST be explained fully once; later occurrences MUST refer back rather than repeat.
- **FR-024**: The document MUST exclude filler: greetings, generic introductions, restating the obvious, repetition, and padding. Detail MUST come from substance (mechanisms, reasoning, examples), not length.
- **FR-025**: Recorded disagreements MUST be shown in the related explanation with both positions, their citations, and which is better supported.
- **FR-026**: The document MUST end with a source list (used sources and further reading).

**Follow-up & practice**

- **FR-027**: Learners MUST be able to ask questions about any slide or concept and receive answers grounded only in the deck and approved sources, with citations; uncovered questions MUST be declined with an offer to research them.
- **FR-028**: Learners MUST be able to request a quiz on a slide range; answers MUST be judged on conceptual correctness, and mistakes MUST get a hint ladder (hint → stronger hint → exact slide/page/section) before the answer is revealed, unless the learner asks for it.
- **FR-029**: Quiz and question history MUST persist so the learner can resume later.

**Cross-cutting**

- **FR-030**: Processing MUST be resumable; completed work (slide analysis, research, book processing) MUST be reused on re-run and when the same file or source is added again.
- **FR-031**: The system MUST record and display token usage and cost for each run, broken down by slide analysis, research, book processing, and document generation.
- **FR-032**: The system MUST detect whether local GPU acceleration is available; when it is, text recognition on images MUST run on the learner's machine at no provider cost, otherwise it MUST fall back to the AI provider, with equivalent results; the estimate MUST show which path is used.
- **FR-033**: The system MUST show specific, actionable error messages for unsupported or corrupt files, unreadable slides, unavailable sources, search or provider errors, and missing/invalid API keys.
- **FR-034**: All data (decks, extracted content, sources, generated documents, history) MUST be stored locally; only content necessary for AI processing and search queries is sent to the configured AI provider.

### Key Entities

- **Deck**: an uploaded set of slides — title, file type, learner context, status, cost.
- **Slide**: one slide — number, image, extracted text, speaker notes, tables, formulas, visuals, topic, concepts, clarity rating, interpretation (with confidence), learner hint.
- **Visual**: a diagram, chart, picture, or book figure — origin (slide number or book page), image, kind, caption, extracted text, explanation.
- **Topic**: a subject found in the deck — name, slides it appears on, research status.
- **Source**: a book, web page, paper, or learner file — title, author/publisher, type, link/file, accessibility (usable vs further reading), relevance/authority rank, reason, topics it supports.
- **Book Node**: a node in a book's summary hierarchy — level, text or summary, page range, parent/children, figures.
- **Disagreement**: a conflict between sources or between a source and a slide — claim, positions, citations, assessment.
- **Explanation Document**: a generated output — deck, format, organization, generation date, sections, cost.
- **Quiz Session**: questions asked, answers, hint levels, results, resume point.
- **Run**: a processing job — steps completed, tokens used, cost by stage, errors, resumability state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A 50-slide deck is analysed, researched, and turned into a slide-by-slide PDF in under 20 minutes on the primary laptop.
- **SC-002**: At least 95% of citations point to a slide, page, or web section that actually contains the cited content (verified on a golden review set).
- **SC-003**: For a labelled set of vague slides, the proposed interpretation matches the instructor's intended topic in at least 85% of cases, and every interpretation is labelled with confidence.
- **SC-004**: At least 95% of text on clear image-only slides is recognized correctly; formulas are rendered correctly in at least 90% of cases.
- **SC-005**: At least 90% of diagrams in a labelled test set receive an explanation judged accurate by a reviewer.
- **SC-006**: At least 90% of sources used as a basis for explanations are rated authoritative and relevant by a reviewer, and 0% are paywalled or unlawfully accessed content.
- **SC-007**: No concept is fully explained more than once in a generated document, and reviewers find no filler passages in at least 95% of sections.
- **SC-008**: Learners rate the explanation of vague slides as "clear and complete" in at least 80% of cases.
- **SC-009**: For questions not covered by the deck or approved sources, the system declines to answer from unsupported knowledge in at least 95% of test cases.
- **SC-010**: The cost estimate shown before research and generation is within ±30% of the actual cost.
- **SC-011**: A learner can go from uploading slides to downloading the explanation document in no more than 5 user actions (excluding waiting time).
- **SC-012**: On a machine with local GPU acceleration, text recognition on image slides incurs zero AI-provider cost.

## Assumptions

- Single learner on their own computer; no accounts or sharing.
- The learner provides their own AI provider API key; slide content, search queries, and selected source content are sent to that provider (the learner accepts this).
- The system is multimodal over text and images: slide text, slide images/diagrams, photographed slides, book text, and book figures. Audio and video are out of scope; YouTube is out of scope (learner decision, 2026-09-30).
- "In detail" means complete coverage of every point, diagram, and formula with reasoning and examples — never padding (see FR-024).
- Books are found through the internet (open textbooks, freely available content, bibliographic records) or supplied by the learner. Content that is not freely and lawfully accessible is only cited as further reading.
- The learner has the right to use the slides and books they upload for personal study.
- English-language slides and sources are the supported case in this version.
- Flashcards and spaced-repetition review are out of scope (learner decision, 2026-09-30).
- Primary machine: laptop with no GPU and about 14 GB RAM (all targets must hold here). Secondary machine: i5-13500HX with RTX 4050 (6 GB), where local text recognition lowers cost. Explanations, diagram interpretation, research, and question answering always use the AI provider.
- A normal broadband connection is available for research.
