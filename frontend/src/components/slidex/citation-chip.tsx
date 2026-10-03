import { BookOpen, Globe, Presentation } from "lucide-react";

import type { EvidenceRef } from "@/lib/api/client";

const ICON = { slide: Presentation, book: BookOpen, web: Globe } as const;

export function CitationChip({ refItem }: { refItem: EvidenceRef }) {
  const Icon = ICON[refItem.kind];
  const body = (
    <>
      <Icon className="size-3 shrink-0" aria-hidden />
      <span className="truncate">{refItem.label}</span>
    </>
  );
  const cls =
    "caption-mono inline-flex max-w-full items-center gap-1 rounded-full border border-border bg-card px-2 py-0.5 text-muted-foreground";
  return refItem.url ? (
    <a href={refItem.url} target="_blank" rel="noreferrer noopener" className={`${cls} hover:text-foreground`}>
      {body}
    </a>
  ) : (
    <span className={cls}>{body}</span>
  );
}

export function Citations({ refs }: { refs: EvidenceRef[] }) {
  if (!refs.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {refs.map((r, i) => (
        <CitationChip key={`${r.label}-${i}`} refItem={r} />
      ))}
    </div>
  );
}
