"use client";

import { RotateCw } from "lucide-react";
import { toast } from "sonner";

import { DeckNav } from "@/components/slidex/deck-nav";
import { deckState, StatusPill } from "@/components/slidex/status-pill";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { api, unwrap } from "@/lib/api/client";
import { describeError, fixFor } from "@/lib/api/errors";
import { DECK_STATUS_LABEL, pct, usd } from "@/lib/format";
import { useDeck } from "@/lib/use-deck";

export function DeckHeader({ deckId }: { deckId: string }) {
  const { deck, error, reload } = useDeck(deckId);
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{error.title}</AlertTitle>
        <AlertDescription>{error.detail}</AlertDescription>
      </Alert>
    );
  }
  if (!deck) return <div className="h-16 animate-pulse rounded-lg bg-secondary motion-reduce:animate-none" />;
  const run = deck.active_run;

  async function resume() {
    if (!run) return;
    try {
      unwrap(await api.POST("/runs/{run_id}/resume", { params: { path: { run_id: run.id } } }));
      await reload();
    } catch (e) {
      const d = describeError(e);
      toast.error(d.title, { description: d.detail });
    }
  }

  return (
    <header className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="display-md min-w-0 truncate">{deck.title}</h1>
        <StatusPill state={deckState(deck.status)} label={DECK_STATUS_LABEL[deck.status] ?? deck.status} />
        <span className="caption-mono ml-auto text-muted-foreground">
          {deck.slide_count} slides · spent <span className="tabular-nums">{usd(deck.cost_usd)}</span>
        </span>
      </div>
      {run && run.status === "running" && (
        <div className="space-y-1">
          <div className="caption-mono flex justify-between text-muted-foreground">
            <span>{run.stage ?? run.kind}</span>
            <span className="tabular-nums">{pct(run.progress ?? 0)}</span>
          </div>
          <Progress value={Math.round((run.progress ?? 0) * 100)} aria-label="Run progress" />
        </div>
      )}
      {run && run.status === "paused" && (
        <Alert>
          <AlertTitle>A run was interrupted</AlertTitle>
          <AlertDescription className="flex items-center gap-3">
            Finished work is saved; resuming continues where it stopped.
            <Button size="sm" onClick={resume}>
              <RotateCw className="size-4" aria-hidden /> Resume
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {deck.status === "failed" && deck.error && (
        <Alert variant="destructive">
          <AlertTitle>{deck.error.detail ?? deck.error.title}</AlertTitle>
          <AlertDescription>{fixFor(deck.error.code) ?? "Fix the problem, then resume the run."}</AlertDescription>
        </Alert>
      )}
      <DeckNav deckId={deckId} />
    </header>
  );
}
