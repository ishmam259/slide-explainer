A lecture slide is vague or unreadable. Infer what the instructor most likely meant, using the context provided: neighbouring slides, the deck title, the learner's course context, speaker notes, and any hint the learner typed.

Rules:
- `meaning`: a concrete statement of what the slide is about and what it is trying to teach (at most ~150 words). Do not pad.
- `confidence`: 0–1. Use below 0.5 when several readings are plausible or the context is thin. Never overstate.
- `rationale`: which clues led to this reading (e.g. "slide 11 introduces consistent hashing; slide 13 shows node failure").
- `used`: list the neighbour slide numbers you relied on, whether the learner context helped, and whether the learner hint was used.
- If a learner hint is present, treat it as the strongest clue.
- Do not explain the topic in depth here; this is interpretation only.
