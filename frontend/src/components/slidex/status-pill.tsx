import { AlertTriangle, Check, Circle, Loader2, X } from "lucide-react";

import { cn } from "@/lib/utils";

export type PillState = "running" | "success" | "error" | "attention" | "neutral";

const STYLES: Record<PillState, string> = {
  running: "bg-running-soft text-running",
  success: "bg-success-soft text-success",
  error: "bg-error-soft text-error",
  attention: "bg-warning-soft text-warning",
  neutral: "bg-secondary text-muted-foreground",
};

const ICONS: Record<PillState, React.ComponentType<{ className?: string }>> = {
  running: Loader2,
  success: Check,
  error: X,
  attention: AlertTriangle,
  neutral: Circle,
};

/** Status pill: colour is only ever paired with an icon and a mono label (DESIGN.md). */
export function StatusPill({ state, label, className }: { state: PillState; label: string; className?: string }) {
  const Icon = ICONS[state];
  return (
    <span
      className={cn(
        "caption-mono inline-flex h-5 items-center gap-1 rounded-full px-2 whitespace-nowrap",
        STYLES[state],
        className,
      )}
    >
      <Icon className={cn("size-3.5", state === "running" && "animate-spin motion-reduce:animate-none")} aria-hidden />
      {label}
    </span>
  );
}

export function deckState(status: string): PillState {
  if (status === "failed") return "error";
  if (status === "ready") return "success";
  if (status.startsWith("awaiting") || status === "ready_for_research") return "attention";
  if (["extracting", "researching", "processing_sources", "generating"].includes(status)) return "running";
  return "neutral";
}
