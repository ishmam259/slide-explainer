Group the slides of a lecture deck into research topics.

Rules:
- Return between 1 and 15 topics. Merge near-duplicates and sub-points into their parent topic.
- Each topic name is a precise, searchable subject (e.g. "Consistent hashing", "CAP theorem trade-offs"), not a slide title like "Overview".
- `slide_numbers`: every slide that covers the topic. Ignore divider slides.
- Use the interpreted meaning for vague slides.
