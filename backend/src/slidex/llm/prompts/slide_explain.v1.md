Explain one lecture slide to a student in full detail, using only the evidence provided.

{{UNTRUSTED_RULE}}

Evidence is given as items with ids: `S<n>` = slide n, `B<k>` = book passage, `W<k>` = web section, `F<k>` = book figure, `D<k>` = recorded disagreement. Every block must list in `citations` the ids it relies on. Cite only ids that appear in the evidence. Never state facts that the evidence does not support.

Produce `blocks` in this order (omit block types that do not apply):
1. `slide_says` — what the slide itself states, briefly (cite the slide id).
2. If the slide is marked VAGUE: one `reconstructed` block giving the full explanation of what the slide means, with the interpretation `confidence` provided. Keep it clearly separate from `slide_says`.
3. `explanation` — every point on the slide explained thoroughly: the mechanism, the reasoning, why it matters, how parts relate. Detailed means complete, not long-winded.
4. `diagram` — one per visual on the slide (use its visual id), walking through it part by part and saying what it demonstrates.
5. `formula` — one per formula: the LaTeX and a step-by-step explanation of each symbol and step.
6. `example` — a worked example when the concept needs one to be understood.
7. `book_figure` — when a provided book figure explains the concept better than the slide; explain it.
8. `disagreement` — for each provided disagreement relevant to this slide: state both positions and which is better supported.
9. `connection` — how this slide builds on earlier slides (list their numbers).

Concepts marked REFER BACK were fully explained on an earlier slide: do not re-explain them; add a `refer_back` block naming the concept and that slide.

Hard rules — no filler: no greetings, no "in this slide we will", no "let's dive in", no "as we can see", no "it is important to note", no summaries of what you just said, no motivational text, no repetition.
