Find factual disagreements about one topic between the provided sources, and between the sources and the slide text.

{{UNTRUSTED_RULE}}

Rules:
- Only report substantive conflicts (different definitions, numbers, conditions, or conclusions). Ignore differences in wording, emphasis, or level of detail.
- Each disagreement has a `claim`, at least two `positions`, each citing the evidence ids that support it (ids are given in the input, e.g. `S12` for slide 12, `W3` for a web section, `B7` for a book passage).
- If a slide is one side, set `involves_slide` to its number.
- `assessment`: which position is better supported and why, citing the stronger evidence. If unclear, say so.
- Return an empty list when there are no real disagreements.
