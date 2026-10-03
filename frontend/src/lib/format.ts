export function usd(value: number): string {
  if (value === 0) return "$0.00";
  if (value < 0.01) return "<$0.01";
  return `$${value.toFixed(2)}`;
}

export function tokens(n: number): string {
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : `${n}`;
}

export function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export const DECK_STATUS_LABEL: Record<string, string> = {
  uploaded: "Uploaded",
  extracting: "Reading slides",
  awaiting_input: "Needs your input",
  ready_for_research: "Ready for research",
  awaiting_research_confirm: "Confirm research",
  researching: "Researching",
  awaiting_source_approval: "Approve sources",
  processing_sources: "Processing sources",
  ready: "Ready",
  generating: "Writing document",
  failed: "Failed",
};
