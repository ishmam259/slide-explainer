"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { FileUp, GripVertical, X } from "lucide-react";
import { z } from "zod";

import { deckState, StatusPill } from "@/components/slidex/status-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, type DeckSummary } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import { DECK_STATUS_LABEL } from "@/lib/format";

const ACCEPT = ".pptx,.pdf,.png,.jpg,.jpeg,.webp";
const contextSchema = z.object({
  course: z.string().max(200).optional(),
  level: z.enum(["intro", "intermediate", "advanced", "graduate"]).optional(),
  topic: z.string().max(200).optional(),
  notes: z.string().max(2000).optional(),
});

export default function Home() {
  const router = useRouter();
  const [decks, setDecks] = useState<DeckSummary[] | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [ctx, setCtx] = useState({ course: "", level: "", topic: "", notes: "" });
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.GET("/decks").then((r) => setDecks(r.data ?? [])).catch(() => setDecks([]));
  }, []);

  function addFiles(list: FileList | null) {
    if (!list) return;
    setFiles((prev) => [...prev, ...Array.from(list)]);
  }

  function move(i: number, dir: -1 | 1) {
    setFiles((prev) => {
      const next = [...prev];
      const j = i + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = contextSchema.safeParse(
      Object.fromEntries(Object.entries(ctx).filter(([, v]) => v.trim() !== "")),
    );
    if (!parsed.success) {
      toast.error("Check the course details", { description: parsed.error.issues[0]?.message });
      return;
    }
    setBusy(true);
    try {
      const body = new FormData();
      for (const f of files) body.append("files", f);
      body.append("context", JSON.stringify(parsed.data));
      const res = await fetch("/api/decks", { method: "POST", body });
      if (!res.ok) throw await problem(res);
      const deck = (await res.json()) as DeckSummary;
      router.push(`/decks/${deck.id}`);
    } catch (err) {
      const d = describeError(err);
      toast.error(d.title, { description: d.detail });
      setBusy(false);
    }
  }

  const images = files.length > 0 && files.every((f) => /\.(png|jpe?g|webp)$/i.test(f.name));

  return (
    <div className="mx-auto grid max-w-5xl gap-8 px-4 py-10 lg:grid-cols-[1fr_340px]">
      <section>
        <h1 className="display-md">Explain my slides</h1>
        <p className="mt-1 text-muted-foreground">
          Upload a lecture deck. The agent reads every slide — even vague ones — researches books and
          trusted web sources, and writes a detailed, cited explanation.
        </p>
        <form onSubmit={submit} className="mt-6 space-y-5">
          <div
            role="button"
            tabIndex={0}
            onClick={() => input.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              addFiles(e.dataTransfer.files);
            }}
            className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-border bg-card px-6 py-10 text-center hover:border-muted-foreground"
          >
            <FileUp className="size-5 text-muted-foreground" aria-hidden />
            <span className="font-medium">Drop a PPTX or PDF, or slide images</span>
            <span className="caption-mono text-muted-foreground">.pptx .pdf .png .jpg .webp · up to 300 slides</span>
            <input
              ref={input}
              type="file"
              accept={ACCEPT}
              multiple
              className="sr-only"
              onChange={(e) => addFiles(e.target.files)}
            />
          </div>

          {files.length > 0 && (
            <ul className="divide-y divide-border rounded-lg border border-border bg-card">
              {files.map((f, i) => (
                <li key={`${f.name}-${i}`} className="flex items-center gap-2 px-3 py-2 text-sm">
                  {images && <GripVertical className="size-4 text-muted-foreground" aria-hidden />}
                  <span className="caption-mono w-6 text-muted-foreground">{i + 1}</span>
                  <span className="truncate">{f.name}</span>
                  <span className="ml-auto flex gap-1">
                    {images && (
                      <>
                        <Button type="button" variant="ghost" size="sm" onClick={() => move(i, -1)} aria-label="Move up">
                          ↑
                        </Button>
                        <Button type="button" variant="ghost" size="sm" onClick={() => move(i, 1)} aria-label="Move down">
                          ↓
                        </Button>
                      </>
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove ${f.name}`}
                      onClick={() => setFiles((p) => p.filter((_, j) => j !== i))}
                    >
                      <X className="size-4" aria-hidden />
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          )}

          <fieldset className="grid gap-4 sm:grid-cols-2">
            <legend className="mb-2 text-sm font-medium">
              Course context <span className="text-muted-foreground">(optional — helps with vague slides)</span>
            </legend>
            <div className="space-y-1.5">
              <Label htmlFor="course">Course</Label>
              <Input id="course" value={ctx.course} maxLength={200} placeholder="Distributed Systems"
                onChange={(e) => setCtx({ ...ctx, course: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="level">Level</Label>
              <select
                id="level"
                value={ctx.level}
                onChange={(e) => setCtx({ ...ctx, level: e.target.value })}
                className="h-9 w-full rounded-md border border-input bg-card px-3 text-sm"
              >
                <option value="">Not specified</option>
                <option value="intro">Intro</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
                <option value="graduate">Graduate</option>
              </select>
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="topic">Lecture topic</Label>
              <Input id="topic" value={ctx.topic} maxLength={200} placeholder="Replication and consistency"
                onChange={(e) => setCtx({ ...ctx, topic: e.target.value })} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea id="notes" value={ctx.notes} maxLength={2000} rows={3}
                placeholder="Anything the slides leave out, e.g. what the lecturer emphasised"
                onChange={(e) => setCtx({ ...ctx, notes: e.target.value })} />
            </div>
          </fieldset>

          <Button type="submit" disabled={!files.length || busy}>
            {busy ? "Uploading…" : "Upload and read slides"}
          </Button>
        </form>
      </section>

      <aside>
        <Card size="sm">
          <CardHeader>
            <CardTitle>Your decks</CardTitle>
            <CardDescription>Stored locally on this computer.</CardDescription>
          </CardHeader>
          <CardContent>
            {decks === null ? (
              <p className="text-muted-foreground">Loading…</p>
            ) : decks.length === 0 ? (
              <p className="text-muted-foreground">No decks yet.</p>
            ) : (
              <ul className="space-y-2">
                {decks.map((d) => (
                  <li key={d.id}>
                    <Link href={`/decks/${d.id}`} className="block rounded-md px-2 py-1.5 hover:bg-secondary">
                      <span className="block truncate font-medium">{d.title}</span>
                      <span className="mt-1 flex items-center gap-2">
                        <StatusPill state={deckState(d.status)} label={DECK_STATUS_LABEL[d.status] ?? d.status} />
                        <span className="caption-mono text-muted-foreground">{d.slide_count} slides</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}

async function problem(res: Response) {
  const { ApiError } = await import("@/lib/api/client");
  const body = await res.json().catch(() => ({}));
  return new ApiError({
    title: body.title ?? res.statusText,
    status: res.status,
    code: body.code ?? "internal_error",
    detail: body.detail ?? null,
  });
}
