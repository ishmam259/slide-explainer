# Slide Explainer — presentation video script

**Presenter:** A K M Ishmam Tahmid (220041259) · **Target length:** 7 minutes ·
**Format:** screen recording with your face in a corner (OBS "Display Capture" + "Video Capture
Device", or Windows Game Bar / Clipchamp with webcam overlay).

Timings are a guide. Words in *italics* are what you do on screen; the rest is what you say.
Say it in your own words. Don't read it word for word.

---

## Before you record (15 minutes, once)

1. **Use the deck the live run already processed** so you don't wait on camera. In PowerShell,
   from `C:\Users\16IRL8\Downloads\gg`, close any old server windows first, then run:

   ```powershell
   .\start.ps1 -Live -DataDir ../data-live-sample
   ```

   The app opens with the **Distributed Databases** deck already researched and explained by the
   real model. Asking questions and taking the quiz live costs well under $0.01.
2. Open these in tabs, ready to switch to:
   - `http://localhost:3000` (the app)
   - `samples\vague-lecture.pdf` in a PDF viewer (the bad deck)
   - `samples\output\vague-lecture-explained.pdf` (the generated document)
   - the GitHub repo page
3. Set the browser zoom to 110–125% so text is readable in the video. Turn off notifications.
4. Rehearse once: the Q&A answer takes about 10–20 seconds, so keep talking while it streams.

---

## 0:00 – 0:40 · Introduction and the problem

*Face full screen, or the app's home page behind you.*

"Hi, I'm A K M Ishmam Tahmid, student ID 220041259, and this is **Slide Explainer**.

Every student knows this problem: you go back to a lecture deck to study and the slides are just
keywords. 'Quorums.' 'R plus W greater than N.' A diagram with no labels. A slide that says
'see lecture.' The lecture explained it, but you're alone with the slides now. Pasting them into
a chatbot gives a confident answer with no sources, and you can't tell if it's right."

*Switch to `samples\vague-lecture.pdf` and scroll quickly through slides 4, 5, 6, 7 and 15.*

"Here's a deliberately bad 25-slide deck I made to test this. Slide 4 is an unlabelled diagram,
slide 7 just says 'See lecture', and slide 15 is actually **wrong**: it says CAP lets a system be
consistent, available and partition-tolerant all at the same time."

## 0:40 – 1:20 · The solution

*Back to the app home page.*

"Slide Explainer is an AI agent that turns a deck like that into a full study document. You
upload PowerPoint, PDF, or even phone photos of the projector. The agent reads every slide, works
out what the vague ones mean, researches **free, legal** sources like MIT OpenCourseWare,
LibreTexts and Wikipedia, and writes a detailed explanation where **every paragraph cites its
evidence**. It also answers your questions and quizzes you, using only those sources.

Three things make it different from a chatbot: it's **grounded**, every claim is cited or
rejected; it's **honest**, it says when a slide is wrong and declines questions its sources don't
cover; and **you stay in control**, it shows the cost before anything is spent and only uses
sources you approve."

## 1:20 – 2:40 · How it works

*Show the "How it works" diagram in the GitHub README (scroll to it).*

"Under the hood it's an agent pipeline built with **LangGraph**:

1. **Extract**: text, tables and diagrams from each slide, using OCR or a vision model.
2. **Interpret**: for vague slides, a reasoning model reconstructs the meaning from neighbouring
   slides and the course context, and gives a **confidence score**.
3. **Topics**, then the agent **pauses**: it shows me a cost estimate and waits for my approval.
4. **Research**: web search restricted to open educational sites, respecting robots.txt with rate
   limits. Every fetched page is treated as **untrusted**: it goes through a safety check that
   blocks spam, paywalls, and **prompt-injection** attempts before any model reads it.
5. It **pauses again** so I can approve the sources. Long books get indexed with **RAPTOR**, a
   tree of summaries built with embeddings and Gaussian-mixture clustering, so retrieval works at
   paragraph, chapter and theme level.
6. **Explain and cite**: each slide is explained from the retrieved evidence. A validator rejects
   any block that cites something that doesn't exist, and rejects filler phrases.
7. **Render** to PDF, Word, Markdown or HTML.

The backend is **FastAPI** in Python, the frontend is **Next.js** with TypeScript, and the models
are OpenAI's **GPT-5.4-nano**, the cheapest one, which keeps a whole 25-slide deck to about
**forty cents**. State is checkpointed in SQLite, so if it crashes it resumes without paying twice."

## 2:40 – 5:40 · Live demo

*App: open the Distributed Databases deck.*

**Slides tab (2:40)**
"Here's the vague deck after processing. Each slide has a clarity rating: most came out
**vague**, with icons and labels, not just colour."
*Click slide 5 ("R + W > N").*
"For this slide the agent explains what it means, with a confidence score. If it gets one wrong,
I can type a hint and it re-interprets just that slide."

**Sources tab (3:20)**
"This is what research found: MIT OpenCourseWare lecture notes, two MIT textbooks, LibreTexts
and Wikipedia, each with a relevance score and the reason it was picked. I can switch any of them
off. The agent even found an 826-page MIT book, which I chose not to approve, to keep the cost
down. Paywalled books only ever show up as 'further reading'."

**Document tab (3:50)**
"Before writing, it shows the estimate: model, tokens and dollars per step."
*Open `samples\output\vague-lecture-explained.pdf`.*
"This is the result: a 64-page document. Slide 2 just said 'Why replicate?', and here's a full
explanation."
*Point at the citation line under a paragraph.*
"Every block ends with its sources, linked to the exact section."
*Scroll to Slide 15.*
"And here's slide 15, the wrong one. The agent writes a **Correction**: it quotes the slide's
claim, says it's not correct, and cites the source explaining that CAP is about trade-offs.
A plain summariser would have repeated the mistake."

**Ask & quiz tab (4:50)**
*Type: "Why does R + W > N guarantee that a read sees the latest write?"*
"I can ask questions about the deck…"
*While it streams:* "…and the answer streams in with citations to the slides and sources."
*Then type something off-topic, for example: "How do I make pasta carbonara?"*
"If my sources don't cover a question, it **declines** instead of making something up."
*Start a quiz on slides 4–6, give one wrong answer.*
"The quiz grades the idea, not keywords. A wrong answer gets a hint, then a stronger hint,
then a pointer to the exact slide. It only shows the answer at the end, or if I ask for it."

## 5:40 – 6:30 · Testing it and engineering quality

*Show the terminal running `uv run pytest` (or a screenshot of "213 passed").*

"For the judges: clone the repo and run **one command**, `start.ps1`. Demo mode needs **no API
key and costs nothing**: it uses an offline model and a bundled offline web, so you can click
through the whole workflow. Real generated documents are in the `samples/output` folder.

On quality: there are **213 automated tests** that never call a paid API, plus strict type
checking. My first real run also caught three bugs the offline tests couldn't: a schema format
OpenAI rejects, keyword slides being skipped as section dividers, and the wrong CAP claim being
repeated instead of corrected. All three are fixed and now covered by tests. Everything is
documented in the repo."

## 6:30 – 7:00 · Close

*Face full screen.*

"So Slide Explainer takes the worst lecture slides and turns them into a cited, honest study
guide, with questions and quizzes on top, for well under a dollar a deck. It's grounded, it
corrects mistakes, and the learner stays in control. Thanks for watching."

---

## Submission checklist (deadline 20 Oct 2026)

- [ ] Folder name: **`SlideExplainer-AKMIshmamTahmid_220041259`**
- [ ] Inside it: the video (`.mp4`), `README.md` (copy from the repo), and either the repo link or a
      zip of the repo. **Make the GitHub repo public, or add the judges as collaborators**, since it
      is currently private.
- [ ] README has your name, ID, title, one-paragraph description, and tools used (done)
- [ ] Watch the video once: audio clear, text readable, face visible the whole time
- [ ] Before zipping: **don't include `backend\.env`**. It holds your API key. If you zip, make it
      from a fresh `git clone`, not from this folder.
