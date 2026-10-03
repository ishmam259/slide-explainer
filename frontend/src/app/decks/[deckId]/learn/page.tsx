"use client";

import { ArrowUp } from "lucide-react";
import { use, useState } from "react";
import { toast } from "sonner";

import { CitationChip, Citations } from "@/components/slidex/citation-chip";
import { StatusPill } from "@/components/slidex/status-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api, type QaTurn, type QuizFeedback, type QuizState, unwrap } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";

function fail(err: unknown) {
  const d = describeError(err);
  toast.error(d.title, { description: d.detail });
}

export default function LearnPage({ params }: PageProps<"/decks/[deckId]/learn">) {
  const { deckId } = use(params);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <QaPanel deckId={deckId} />
      <QuizPanel deckId={deckId} />
    </div>
  );
}

function QaPanel({ deckId }: { deckId: string }) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<{ q: string; a: string; turn?: QaTurn }[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function ask(e?: React.FormEvent) {
    e?.preventDefault();
    const q = question.trim();
    if (!q) return;
    setBusy(true);
    setQuestion("");
    setTurns((t) => [...t, { q, a: "" }]);
    try {
      const res = await fetch(`/api/decks/${deckId}/qa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, thread_id: threadId }),
      });
      if (!res.ok || !res.body) throw new Error("The question could not be answered.");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const frames = buf.split(/\r?\n\r?\n/);
        buf = frames.pop() ?? "";
        for (const frame of frames) {
          const event = /^event: (.*)$/m.exec(frame)?.[1];
          const data = frame.split(/\r?\n/).filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("\n");
          if (event === "answer.delta") {
            setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a: x.a + data } : x)));
          } else if (event === "answer.done" || event === "answer.declined") {
            const turn = JSON.parse(data) as QaTurn;
            setThreadId(turn.thread_id);
            setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a: turn.text, turn } : x)));
          }
        }
      }
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="display-sm">Ask about your slides</CardTitle>
        <CardDescription>Answers come only from your slides and approved sources, with citations.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-5" aria-live="polite">
          {turns.map((t, i) => (
            <div key={i} className="space-y-2">
              <p className="ml-auto max-w-[85%] rounded-lg bg-secondary px-3 py-2 text-[16px] leading-6">{t.q}</p>
              <div className="text-[16px] leading-6">
                {t.turn?.declined && <StatusPill state="attention" label="not covered" className="mb-1" />}
                <p className="whitespace-pre-line">{t.a || "…"}</p>
                {t.turn && <Citations refs={t.turn.citations} />}
              </div>
            </div>
          ))}
        </div>
        <form onSubmit={ask} className="rounded-lg border border-border bg-card p-2 focus-within:shadow-level-2">
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void ask();
              }
            }}
            rows={2}
            maxLength={2000}
            placeholder="Ask about any slide or concept…"
            aria-label="Your question"
            className="resize-none border-0 shadow-none focus-visible:ring-0"
          />
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={busy || !question.trim()}>
              <ArrowUp className="size-4" aria-hidden /> Ask
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function QuizPanel({ deckId }: { deckId: string }) {
  const [range, setRange] = useState({ from: "1", to: "5" });
  const [quiz, setQuiz] = useState<QuizState | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<QuizFeedback | null>(null);
  const [busy, setBusy] = useState(false);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const q = unwrap(
        await api.POST("/decks/{deck_id}/quizzes", {
          params: { path: { deck_id: deckId } },
          body: { slide_from: Number(range.from), slide_to: Number(range.to), count: 5 },
        }),
      );
      setQuiz(q);
      setFeedback(null);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!quiz) return;
    setBusy(true);
    try {
      const fb = unwrap(
        await api.POST("/quizzes/{quiz_id}/answer", { params: { path: { quiz_id: quiz.id } }, body: { answer } }),
      );
      setFeedback(fb);
      setQuiz(fb.state);
      if (fb.verdict === "correct" || fb.verdict === "revealed") setAnswer("");
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  async function reveal() {
    if (!quiz) return;
    try {
      const fb = unwrap(await api.POST("/quizzes/{quiz_id}/reveal", { params: { path: { quiz_id: quiz.id } } }));
      setFeedback(fb);
      setQuiz(fb.state);
      setAnswer("");
    } catch (err) {
      fail(err);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="display-sm">Check your understanding</CardTitle>
        <CardDescription>Wrong answers get hints and a pointer to the exact slide or page before the answer.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={start} className="flex flex-wrap items-center gap-2 text-sm">
          Slides
          <input aria-label="From slide" type="number" min={1} value={range.from}
            onChange={(e) => setRange({ ...range, from: e.target.value })}
            className="h-9 w-16 rounded-md border border-input bg-card px-2" />
          to
          <input aria-label="To slide" type="number" min={1} value={range.to}
            onChange={(e) => setRange({ ...range, to: e.target.value })}
            className="h-9 w-16 rounded-md border border-input bg-card px-2" />
          <Button type="submit" variant={quiz ? "outline" : "default"} disabled={busy}>
            {quiz ? "New quiz" : "Start quiz"}
          </Button>
        </form>

        {quiz && (
          <div className="space-y-3">
            <div className="caption-mono flex justify-between text-muted-foreground tabular-nums">
              <span>
                question {Math.min(quiz.index + 1, quiz.total)} / {quiz.total}
              </span>
              <span>
                score {quiz.score.correct}/{quiz.score.answered} · hint level {quiz.hint_level}/3
              </span>
            </div>
            {quiz.status === "completed" ? (
              <StatusPill state="success" label="quiz complete" />
            ) : (
              <form onSubmit={submit} className="space-y-2">
                <p className="text-[16px] font-medium leading-6">{quiz.question}</p>
                <Textarea value={answer} onChange={(e) => setAnswer(e.target.value)} rows={3} maxLength={4000}
                  aria-label="Your answer" />
                <div className="flex gap-2">
                  <Button type="submit" disabled={busy || !answer.trim()}>Check</Button>
                  <Button type="button" variant="outline" onClick={reveal}>Show answer</Button>
                </div>
              </form>
            )}
            {feedback && (
              <div className="space-y-2 rounded-md border border-border p-3 text-sm">
                <StatusPill
                  state={feedback.verdict === "correct" ? "success" : feedback.verdict === "revealed" ? "neutral" : "attention"}
                  label={feedback.verdict}
                />
                {feedback.misconception && <p>{feedback.misconception}</p>}
                {feedback.hint && <p className="text-muted-foreground">{feedback.hint}</p>}
                {feedback.pointer && (
                  <p className="flex items-center gap-2">
                    Review: <CitationChip refItem={feedback.pointer} />
                  </p>
                )}
                {feedback.revealed_answer && <p><span className="font-medium">Answer:</span> {feedback.revealed_answer}</p>}
                {feedback.explanation && <p className="text-muted-foreground">{feedback.explanation}</p>}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
