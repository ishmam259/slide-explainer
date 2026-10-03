"use client";

import { useEffect, useRef } from "react";

export interface DeckEvent {
  event: string;
  deck_id: string;
  at: string;
  run?: Record<string, unknown> | null;
  slide_number?: number | null;
  source_id?: string | null;
  document_id?: string | null;
  message?: string | null;
}

const EVENTS = [
  "run.started",
  "run.stage",
  "run.progress",
  "run.paused",
  "run.completed",
  "run.failed",
  "slide.updated",
  "topic.updated",
  "source.updated",
  "document.updated",
  "deck.status",
];

/** Subscribe to live progress for a deck. EventSource reconnects automatically. */
export function useDeckEvents(deckId: string | undefined, onEvent: (e: DeckEvent) => void): void {
  const handler = useRef(onEvent);
  useEffect(() => {
    handler.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!deckId) return;
    const source = new EventSource(`/api/decks/${deckId}/events`);
    const listener = (msg: MessageEvent<string>) => {
      try {
        handler.current(JSON.parse(msg.data) as DeckEvent);
      } catch {
        /* ignore malformed keep-alive frames */
      }
    };
    for (const name of EVENTS) source.addEventListener(name, listener);
    return () => source.close();
  }, [deckId]);
}
