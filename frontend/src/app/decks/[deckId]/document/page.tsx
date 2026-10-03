"use client";

import { Download } from "lucide-react";
import { use, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { EstimateCard } from "@/components/slidex/estimate-card";
import { StatusPill } from "@/components/slidex/status-pill";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { api, type ExplanationDocument, type RunEstimate, unwrap } from "@/lib/api/client";
import { describeError } from "@/lib/api/errors";
import { pct, usd } from "@/lib/format";
import { useDeck } from "@/lib/use-deck";

const FORMATS = [
  { id: "pdf", label: "PDF" },
  { id: "docx", label: "Word (.docx)" },
  { id: "md", label: "Markdown (.zip)" },
  { id: "html", label: "HTML" },
] as const;
type Format = (typeof FORMATS)[number]["id"];

export default function DocumentPage({ params }: PageProps<"/decks/[deckId]/document">) {
  const { deckId } = use(params);
  const { deck, reload, tick } = useDeck(deckId);
  const [organization, setOrganization] = useState<"by_slide" | "by_topic">("by_slide");
  const [formats, setFormats] = useState<Format[]>(["pdf"]);
  const [range, setRange] = useState({ from: "", to: "" });
  const [estimate, setEstimate] = useState<RunEstimate | null>(null);
  const [docs, setDocs] = useState<ExplanationDocument[]>([]);
  const [busy, setBusy] = useState(false);

  const fetchDocs = useCallback(
    async () => (await api.GET("/decks/{deck_id}/documents", { params: { path: { deck_id: deckId } } })).data,
    [deckId],
  );
  const loadDocs = useCallback(async () => {
    const data = await fetchDocs();
    if (data) setDocs(data);
  }, [fetchDocs]);

  useEffect(() => {
    let alive = true;
    fetchDocs().then((data) => alive && data && setDocs(data));
    if (deck?.status === "ready") {
      api
        .GET("/decks/{deck_id}/estimate", { params: { path: { deck_id: deckId }, query: { stage: "generate" } } })
        .then((r) => alive && r.data && setEstimate(r.data));
    }
    return () => {
      alive = false;
    };
  }, [deck?.status, deckId, fetchDocs, tick]);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    const from = Number(range.from);
    const to = Number(range.to);
    try {
      unwrap(
        await api.POST("/decks/{deck_id}/documents", {
          params: { path: { deck_id: deckId } },
          body: {
            organization,
            formats,
            slide_range: range.from && range.to ? [from, to] : null,
          },
        }),
      );
      await Promise.all([reload(), loadDocs()]);
    } catch (err) {
      const d = describeError(err);
      toast.error(d.title, { description: d.detail });
    } finally {
      setBusy(false);
    }
  }

  if (!deck) return null;
  const canGenerate = deck.status === "ready";

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <section className="space-y-6">
        {!canGenerate && deck.status !== "generating" && (
          <Alert>
            <AlertTitle>Approve sources first</AlertTitle>
            <AlertDescription>The document is written from your slides plus the sources you approve.</AlertDescription>
          </Alert>
        )}
        {canGenerate && estimate && (
          <form onSubmit={generate}>
            <EstimateCard estimate={estimate} title="Write the explanation">
              <fieldset className="space-y-2">
                <legend className="mb-1 text-sm font-medium">Organize</legend>
                {(
                  [
                    ["by_slide", "Slide by slide", "Follows your deck in order."],
                    ["by_topic", "By topic", "Groups related slides together."],
                  ] as const
                ).map(([value, label, hint]) => (
                  <label key={value} className="flex items-start gap-2 text-sm">
                    <input type="radio" name="organization" value={value} checked={organization === value}
                      onChange={() => setOrganization(value)} className="mt-1" />
                    <span>
                      <span className="font-medium">{label}</span>{" "}
                      <span className="text-muted-foreground">— {hint}</span>
                    </span>
                  </label>
                ))}
              </fieldset>
              <fieldset className="space-y-2">
                <legend className="mb-1 text-sm font-medium">Formats</legend>
                <div className="flex flex-wrap gap-4">
                  {FORMATS.map((f) => (
                    <label key={f.id} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={formats.includes(f.id)}
                        onCheckedChange={(v: boolean) =>
                          setFormats((prev) => (v ? [...prev, f.id] : prev.filter((x) => x !== f.id)))
                        }
                      />
                      {f.label}
                    </label>
                  ))}
                </div>
              </fieldset>
              <fieldset className="flex items-center gap-2 text-sm">
                <legend className="mb-1 text-sm font-medium">Slides (optional)</legend>
                <input aria-label="From slide" type="number" min={1} max={deck.slide_count} value={range.from}
                  onChange={(e) => setRange({ ...range, from: e.target.value })}
                  className="h-9 w-20 rounded-md border border-input bg-card px-2" />
                to
                <input aria-label="To slide" type="number" min={1} max={deck.slide_count} value={range.to}
                  onChange={(e) => setRange({ ...range, to: e.target.value })}
                  className="h-9 w-20 rounded-md border border-input bg-card px-2" />
              </fieldset>
              <Button type="submit" disabled={!formats.length || busy}>
                {busy ? "Starting…" : "Write the document"}
              </Button>
            </EstimateCard>
          </form>
        )}
      </section>

      <aside>
        <Card size="sm">
          <CardHeader>
            <CardTitle>Documents</CardTitle>
          </CardHeader>
          <CardContent>
            {docs.length === 0 ? (
              <p className="text-sm text-muted-foreground">None yet.</p>
            ) : (
              <ul className="space-y-4">
                {docs.map((d) => (
                  <li key={d.id} className="space-y-2 border-b border-border pb-4 last:border-0">
                    <div className="flex items-center gap-2">
                      <StatusPill
                        state={d.status === "ready" ? "success" : d.status === "failed" ? "error" : "running"}
                        label={d.status}
                      />
                      <span className="caption-mono text-muted-foreground">
                        {d.organization === "by_slide" ? "by slide" : "by topic"} · {usd(d.cost_usd ?? 0)}
                      </span>
                    </div>
                    {(d.status === "generating" || d.status === "rendering" || d.status === "queued") && (
                      <Progress value={Math.round((d.progress ?? 0) * 100)} aria-label="Document progress" />
                    )}
                    {d.stats && d.status === "ready" && (
                      <p className="caption-mono text-muted-foreground tabular-nums">
                        {d.stats.sections} sections · {d.stats.reconstructed_slides} reconstructed ·{" "}
                        {d.stats.disagreements_shown} disagreements · {d.stats.dropped_blocks} uncited blocks dropped
                      </p>
                    )}
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(d.downloads ?? {}).map(([fmt, url]) => (
                        <a key={fmt} href={url} download
                          className="inline-flex h-8 items-center gap-1 rounded-md border border-border px-2.5 text-sm hover:bg-secondary">
                          <Download className="size-3.5" aria-hidden /> {fmt.toUpperCase()}
                        </a>
                      ))}
                    </div>
                    {d.error && <p className="text-sm text-warning">{d.error.detail ?? d.error.title}</p>}
                    <p className="caption-mono text-muted-foreground">{pct(d.progress ?? 0)} · {new Date(d.created_at).toLocaleString()}</p>
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
