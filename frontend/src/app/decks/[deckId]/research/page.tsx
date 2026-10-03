"use client";

import { ExternalLink, Plus } from "lucide-react";
import { use, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Citations } from "@/components/slidex/citation-chip";
import { EstimateCard } from "@/components/slidex/estimate-card";
import { StatusPill } from "@/components/slidex/status-pill";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  api,
  ApiError,
  type DeckSource,
  type Disagreement,
  type RunEstimate,
  type SourceList,
  unwrap,
} from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import { pct } from "@/lib/format";
import { useDeck } from "@/lib/use-deck";

function fail(err: unknown) {
  const d = describeError(err);
  toast.error(d.title, { description: d.detail });
}

export default function ResearchPage({ params }: PageProps<"/decks/[deckId]/research">) {
  const { deckId } = use(params);
  const { deck, reload, tick } = useDeck(deckId);
  const [estimate, setEstimate] = useState<RunEstimate | null>(null);
  const [sources, setSources] = useState<SourceList | null>(null);
  const [disagreements, setDisagreements] = useState<Disagreement[]>([]);
  const [busy, setBusy] = useState(false);

  const status = deck?.status;
  const fetchSources = useCallback(async () => {
    const p = { params: { path: { deck_id: deckId } } };
    const [s, d] = await Promise.all([
      api.GET("/decks/{deck_id}/sources", p),
      api.GET("/decks/{deck_id}/disagreements", p),
    ]);
    return { s: s.data, d: d.data };
  }, [deckId]);
  const loadSources = useCallback(async () => {
    const { s, d } = await fetchSources();
    if (s) setSources(s);
    if (d) setDisagreements(d);
  }, [fetchSources]);

  useEffect(() => {
    let alive = true;
    if (status === "awaiting_research_confirm") {
      api
        .GET("/decks/{deck_id}/estimate", { params: { path: { deck_id: deckId }, query: { stage: "research" } } })
        .then((r) => alive && r.data && setEstimate(r.data));
    }
    fetchSources().then(({ s, d }) => {
      if (!alive) return;
      if (s) setSources(s);
      if (d) setDisagreements(d);
    });
    return () => {
      alive = false;
    };
  }, [status, deckId, fetchSources, tick]);

  async function confirm() {
    setBusy(true);
    try {
      unwrap(await api.POST("/decks/{deck_id}/research", { params: { path: { deck_id: deckId } }, body: { confirm: true } }));
      await reload();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    setBusy(true);
    try {
      unwrap(await api.POST("/decks/{deck_id}/sources/approve", { params: { path: { deck_id: deckId } } }));
      await reload();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(ds: DeckSource, approved: boolean) {
    try {
      unwrap(
        await api.PATCH("/decks/{deck_id}/sources/{source_id}", {
          params: { path: { deck_id: deckId, source_id: ds.source.id } },
          body: { approved },
        }),
      );
      await loadSources();
    } catch (e) {
      fail(e);
    }
  }

  if (!deck) return null;
  const early = ["uploaded", "extracting", "ready_for_research"].includes(deck.status);

  return (
    <div className="space-y-6">
      {early && (
        <Alert>
          <AlertTitle>Still reading your slides</AlertTitle>
          <AlertDescription>Research starts once every slide is understood.</AlertDescription>
        </Alert>
      )}

      {deck.status === "awaiting_research_confirm" && estimate && (
        <EstimateCard estimate={estimate} title="Research books and web sources">
          <div className="flex gap-2">
            <Button onClick={confirm} disabled={busy}>
              {busy ? "Starting…" : "Confirm and research"}
            </Button>
          </div>
        </EstimateCard>
      )}

      {deck.status === "awaiting_source_approval" && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border-l-2 border-warning bg-warning-soft p-4">
          <StatusPill state="attention" label="needs approval" />
          <p className="text-sm">
            Review the sources below. Only approved, freely available sources are used to explain your slides.
          </p>
          <div className="ml-auto flex gap-2">
            <AddSource deckId={deckId} onAdded={loadSources} />
            <Button onClick={approve} disabled={busy}>
              {busy ? "Approving…" : "Approve sources"}
            </Button>
          </div>
        </div>
      )}

      {sources?.by_topic.map((group) => (
        <Card key={group.topic.id} size="sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {group.topic.name}
              {group.topic.research_status === "no_reliable_source" && (
                <StatusPill state="attention" label="no reliable source" />
              )}
            </CardTitle>
            {group.topic.slide_numbers.length > 0 && (
              <CardDescription className="caption-mono">slides {group.topic.slide_numbers.join(", ")}</CardDescription>
            )}
          </CardHeader>
          <CardContent>
            {group.sources.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {group.topic.research_status === "no_reliable_source"
                  ? "No trustworthy source found. The explanation will stay close to the slide."
                  : group.topic.research_status === "searching"
                    ? "Searching…"
                    : "Not researched yet."}
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {group.sources.map((ds) => (
                  <li key={ds.source.id} className="flex items-start gap-3 py-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="caption-mono rounded-full bg-secondary px-2 text-muted-foreground">
                          {ds.source.kind.replace("_", " ")}
                        </span>
                        {ds.source.url ? (
                          <a href={ds.source.url} target="_blank" rel="noreferrer noopener"
                            className="inline-flex items-center gap-1 font-medium hover:underline">
                            {ds.source.title} <ExternalLink className="size-3" aria-hidden />
                          </a>
                        ) : (
                          <span className="font-medium">{ds.source.title}</span>
                        )}
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">{ds.reason}</p>
                      <p className="caption-mono mt-1 text-muted-foreground tabular-nums">
                        relevance {pct(ds.relevance)} · authority {pct(ds.authority)}
                        {ds.source.page_count ? ` · ${ds.source.page_count} pages` : ""}
                      </p>
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                      <Switch checked={ds.approved} onCheckedChange={(v: boolean) => toggle(ds, v)}
                        aria-label={`Use ${ds.source.title}`} disabled={deck.status !== "awaiting_source_approval"} />
                      Use
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      ))}

      {disagreements.length > 0 && (
        <Card size="sm">
          <CardHeader>
            <CardTitle>Where sources disagree</CardTitle>
            <CardDescription>Shown in the document next to the related slide.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {disagreements.map((d) => (
              <div key={d.id} className="rounded-md border-l-2 border-warning bg-warning-soft p-3">
                <p className="font-medium">{d.claim}</p>
                {d.positions.map((p, i) => (
                  <div key={i} className="mt-2 text-sm">
                    {p.statement}
                    <Citations refs={p.evidence} />
                  </div>
                ))}
                <p className="mt-2 text-sm text-muted-foreground">{d.assessment}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {sources && sources.further_reading.length > 0 && (
        <Card size="sm">
          <CardHeader>
            <CardTitle>Further reading</CardTitle>
            <CardDescription>Relevant but not freely available — listed for reference, never used as evidence.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {sources.further_reading.map((s) => (
                <li key={s.id}>
                  {s.authors?.length ? `${s.authors.join(", ")}, ` : ""}
                  {s.title}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function AddSource({ deckId, onAdded }: { deckId: string; onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function add(body: FormData) {
    setBusy(true);
    try {
      const res = await fetch(`/api/decks/${deckId}/sources`, { method: "POST", body });
      if (!res.ok) {
        const p = await res.json().catch(() => ({}));
        throw new ApiError({ title: p.title ?? res.statusText, status: res.status, code: p.code ?? "internal_error", detail: p.detail });
      }
      toast.success("Source added");
      setUrl("");
      setOpen(false);
      onAdded();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Plus className="size-4" aria-hidden /> Add a source
      </Button>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" className="w-56" aria-label="Source URL" />
      <Button variant="outline" disabled={!url || busy} onClick={() => {
        const f = new FormData();
        f.append("url", url);
        void add(f);
      }}>Add URL</Button>
      <label className="cursor-pointer text-sm underline">
        or upload a book PDF
        <input type="file" accept=".pdf" className="sr-only" onChange={(e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          const f = new FormData();
          f.append("file", file);
          void add(f);
        }} />
      </label>
    </div>
  );
}
