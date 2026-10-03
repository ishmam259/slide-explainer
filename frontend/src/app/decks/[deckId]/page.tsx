"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { ClarityBadge } from "@/components/slidex/clarity-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type Slide, unwrap } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import { pct } from "@/lib/format";
import { useDeckEvents } from "@/lib/sse";
import { cn } from "@/lib/utils";

type Filter = "all" | "needs_input" | "vague";

export default function SlidesPage({ params }: PageProps<"/decks/[deckId]">) {
  const { deckId } = use(params);
  const [slides, setSlides] = useState<Slide[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  const fetchSlides = useCallback(
    async () => (await api.GET("/decks/{deck_id}/slides", { params: { path: { deck_id: deckId } } })).data,
    [deckId],
  );
  const load = useCallback(async () => {
    const data = await fetchSlides();
    if (data) setSlides(data);
  }, [fetchSlides]);
  useEffect(() => {
    let alive = true;
    fetchSlides().then((data) => alive && data && setSlides(data));
    return () => {
      alive = false;
    };
  }, [fetchSlides]);
  useDeckEvents(deckId, (e) => {
    if (e.event === "slide.updated" || e.event.startsWith("run.")) void load();
  });

  const shown = useMemo(() => {
    if (!slides) return [];
    if (filter === "needs_input") return slides.filter((s) => s.needs_input);
    if (filter === "vague") return slides.filter((s) => s.clarity === "vague" || s.clarity === "unreadable");
    return slides;
  }, [slides, filter]);
  const current = slides?.find((s) => s.number === selected) ?? null;
  const needs = slides?.filter((s) => s.needs_input).length ?? 0;

  if (!slides) return <p className="text-muted-foreground">Loading slides…</p>;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_420px]">
      <section>
        <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filter slides">
          {(
            [
              ["all", `All (${slides.length})`],
              ["vague", "Vague or unreadable"],
              ["needs_input", `Needs your input (${needs})`],
            ] as const
          ).map(([key, label]) => (
            <Button key={key} size="sm" variant={filter === key ? "default" : "outline"} aria-pressed={filter === key}
              onClick={() => setFilter(key)}>
              {label}
            </Button>
          ))}
        </div>
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {shown.map((s) => (
            <li key={s.number}>
              <button
                type="button"
                onClick={() => setSelected(s.number)}
                aria-pressed={selected === s.number}
                className={cn(
                  "w-full overflow-hidden rounded-lg border bg-card text-left transition-shadow hover:shadow-level-2",
                  selected === s.number ? "border-foreground" : "border-border",
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={s.image_url} alt={`Slide ${s.number}`} className="aspect-video w-full border-b border-border object-contain bg-white" />
                <div className="space-y-1.5 p-2.5">
                  <div className="flex items-center gap-2">
                    <span className="caption-mono text-muted-foreground">{s.number}</span>
                    <ClarityBadge clarity={s.clarity} />
                    {s.needs_input && <span className="caption-mono text-warning">needs input</span>}
                  </div>
                  <p className="line-clamp-2 text-sm">{s.topic ?? s.title ?? "—"}</p>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <aside className="lg:sticky lg:top-20 lg:self-start">
        {current ? (
          <SlideDetail key={current.number} deckId={deckId} slide={current} onSaved={load} />
        ) : (
          <p className="rounded-lg border border-dashed border-border p-6 text-center text-muted-foreground">
            Select a slide to see what the agent read and how it interpreted it.
          </p>
        )}
      </aside>
    </div>
  );
}

function SlideDetail({ deckId, slide, onSaved }: { deckId: string; slide: Slide; onSaved: () => void }) {
  const [hint, setHint] = useState(slide.learner_hint ?? "");
  const [saving, setSaving] = useState(false);

  async function saveHint(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      unwrap(
        await api.PUT("/decks/{deck_id}/slides/{number}/hint", {
          params: { path: { deck_id: deckId, number: slide.number } },
          body: { hint },
        }),
      );
      toast.success("Hint applied", { description: "The slide was re-interpreted." });
      onSaved();
    } catch (err) {
      const d = describeError(err);
      toast.error(d.title, { description: d.detail });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2">
        <h2 className="display-sm">Slide {slide.number}</h2>
        <ClarityBadge clarity={slide.clarity} />
        <span className="caption-mono ml-auto text-muted-foreground">{slide.ocr_path.replace("_", " ")}</span>
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={slide.image_url} alt={`Slide ${slide.number}`} className="w-full rounded-md border border-border bg-white" />
      {slide.text && (
        <section>
          <h3 className="mb-1 text-sm font-medium">What the slide says</h3>
          <p className="whitespace-pre-line text-sm text-muted-foreground">{slide.text}</p>
        </section>
      )}
      {slide.interpretation && (
        <section className="rounded-md bg-running-soft p-3">
          <h3 className="mb-1 text-sm font-medium">
            Interpretation · <span className="caption-mono">confidence {pct(slide.interpretation.confidence)}</span>
          </h3>
          <p className="text-sm">{slide.interpretation.meaning}</p>
          <p className="caption-mono mt-2 text-muted-foreground">{slide.interpretation.rationale}</p>
        </section>
      )}
      {(slide.visuals ?? []).map((v) => (
        <section key={v.id}>
          <h3 className="mb-1 text-sm font-medium">
            Visual · <span className="caption-mono">{v.kind}</span>
          </h3>
          <p className="text-sm">{v.description}</p>
          {v.explanation && <p className="mt-1 text-sm text-muted-foreground">{v.explanation}</p>}
        </section>
      ))}
      {slide.notes && (
        <section>
          <h3 className="mb-1 text-sm font-medium">Speaker notes</h3>
          <p className="whitespace-pre-line text-sm text-muted-foreground">{slide.notes}</p>
        </section>
      )}
      {(slide.clarity === "vague" || slide.clarity === "unreadable") && (
        <form onSubmit={saveHint} className="space-y-2 border-t border-border pt-4">
          <label htmlFor="hint" className="text-sm font-medium">
            {slide.needs_input ? "The agent isn't sure. What is this slide about?" : "Add a hint (optional)"}
          </label>
          <div className="flex gap-2">
            <Input id="hint" value={hint} maxLength={500} onChange={(e) => setHint(e.target.value)}
              placeholder="e.g. the quorum condition for strong consistency" />
            <Button type="submit" disabled={!hint.trim() || saving}>
              {saving ? "Applying…" : "Apply"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
