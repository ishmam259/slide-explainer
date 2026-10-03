"use client";

import Link from "next/link";
import { Moon, Presentation, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, type Health } from "@/lib/api/client";

import { StatusPill } from "./status-pill";

export function AppHeader() {
  const { resolvedTheme, setTheme } = useTheme();
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    api
      .GET("/health")
      .then((r) => (r.data ? setHealth(r.data) : setOffline(true)))
      .catch(() => setOffline(true));
  }, []);

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur-none">
      <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
        <Presentation className="size-4" aria-hidden />
        Slide Explainer
      </Link>
      <div className="ml-auto flex items-center gap-2">
        {offline && <StatusPill state="error" label="backend offline" />}
        {health && !health.api_key_configured && <StatusPill state="attention" label="add OPENAI_API_KEY" />}
        {health && health.api_key_configured && (
          <span className="caption-mono hidden text-muted-foreground sm:inline">
            {health.models.strong} · ocr {health.ocr_path === "local_gpu" ? "local GPU" : "provider"}
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle theme"
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
          <Sun className="size-4 dark:hidden" aria-hidden />
          <Moon className="hidden size-4 dark:block" aria-hidden />
        </Button>
      </div>
    </header>
  );
}
