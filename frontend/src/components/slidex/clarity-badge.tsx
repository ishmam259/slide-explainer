import { StatusPill, type PillState } from "./status-pill";

const MAP: Record<string, { state: PillState; label: string }> = {
  clear: { state: "success", label: "clear" },
  vague: { state: "attention", label: "vague" },
  unreadable: { state: "error", label: "unreadable" },
  divider: { state: "neutral", label: "divider" },
  pending: { state: "running", label: "reading" },
};

export function ClarityBadge({ clarity }: { clarity: string }) {
  const { state, label } = MAP[clarity] ?? MAP.pending;
  return <StatusPill state={state} label={label} />;
}
