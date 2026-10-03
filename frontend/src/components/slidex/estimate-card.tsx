import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { RunEstimate } from "@/lib/api/client";
import { tokens, usd } from "@/lib/format";

const STAGE_LABEL: Record<string, string> = {
  research_search: "Web search",
  research_fetch_rank: "Read & rank pages",
  disagreements: "Check for disagreements",
  book_processing: "Summarize books",
  explanation: "Write explanations",
  slide_extraction: "Read slides",
  interpretation: "Interpret vague slides",
};

export function EstimateCard({ estimate, title, children }: { estimate: RunEstimate; title: string; children?: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="display-sm">{title}</CardTitle>
        <CardDescription>
          Estimated <span className="font-mono tabular-nums text-foreground">{usd(estimate.total_usd)}</span> · about{" "}
          <span className="font-mono tabular-nums">{estimate.est_minutes}</span> min. Nothing runs until you confirm.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="caption-mono text-left uppercase text-muted-foreground">
              <th className="pb-2 font-normal">Step</th>
              <th className="pb-2 font-normal">Model</th>
              <th className="pb-2 text-right font-normal">Tokens</th>
              <th className="pb-2 text-right font-normal">Cost</th>
            </tr>
          </thead>
          <tbody>
            {estimate.stages.map((s) => (
              <tr key={s.stage} className="border-t border-border">
                <td className="py-2">{STAGE_LABEL[s.stage] ?? s.stage}</td>
                <td className="py-2 font-mono text-xs text-muted-foreground">
                  {s.path === "local" ? "local GPU" : s.model}
                </td>
                <td className="py-2 text-right font-mono tabular-nums text-muted-foreground">
                  {tokens(s.input_tokens + s.output_tokens)}
                </td>
                <td className="py-2 text-right font-mono tabular-nums">{usd(s.usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {estimate.budget && estimate.budget.topics > 0 && (
          <p className="caption-mono text-muted-foreground">
            budget: {estimate.budget.topics} topics × {estimate.budget.searches_per_topic} searches ×{" "}
            {estimate.budget.pages_per_topic} pages
          </p>
        )}
        {children}
      </CardContent>
    </Card>
  );
}
