"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const TABS = [
  { href: "", label: "Slides" },
  { href: "/research", label: "Sources" },
  { href: "/document", label: "Document" },
  { href: "/learn", label: "Ask & quiz" },
];

export function DeckNav({ deckId }: { deckId: string }) {
  const path = usePathname();
  return (
    <nav aria-label="Deck sections" className="flex gap-1 border-b border-border">
      {TABS.map((t) => {
        const href = `/decks/${deckId}${t.href}`;
        const active = path === href;
        return (
          <Link
            key={t.label}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
              active
                ? "border-foreground font-medium text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
