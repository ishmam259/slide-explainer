"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type DeckDetail, unwrap } from "./api/client";
import { describeError } from "./api/errors";
import { useDeckEvents } from "./sse";

const BUSY = new Set(["uploaded", "extracting", "researching", "processing_sources", "generating"]);

/** Deck detail that refreshes on every live event (throttled), plus a manual reload. */
export function useDeck(deckId: string) {
  const [deck, setDeck] = useState<DeckDetail | null>(null);
  const [error, setError] = useState<{ title: string; detail: string } | null>(null);
  const [tick, setTick] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchDeck = useCallback(
    async () => unwrap(await api.GET("/decks/{deck_id}", { params: { path: { deck_id: deckId } } })),
    [deckId],
  );

  const reload = useCallback(async () => {
    try {
      const d = await fetchDeck();
      setDeck(d);
      setError(null);
    } catch (e) {
      setError(describeError(e));
    }
  }, [fetchDeck]);

  useEffect(() => {
    let alive = true;
    fetchDeck()
      .then((d) => alive && (setDeck(d), setError(null)))
      .catch((e: unknown) => alive && setError(describeError(e)));
    return () => {
      alive = false;
    };
  }, [fetchDeck]);

  const onEvent = useCallback(
    () => {
      if (timer.current) return;
      timer.current = setTimeout(() => {
        timer.current = null;
        void reload();
        setTick((t) => t + 1);
      }, 400);
    },
    [reload],
  );
  useDeckEvents(deckId, onEvent);

  // Fallback: while work is in progress, poll so the UI stays correct even if events stall.
  const busy = deck ? BUSY.has(deck.status) || deck.active_run?.status === "running" : false;
  useEffect(() => {
    if (!busy) return;
    const id = setInterval(() => {
      void reload();
      setTick((t) => t + 1);
    }, 2000);
    return () => clearInterval(id);
  }, [busy, reload]);

  return { deck, error, reload, tick };
}
