import { useCallback, useEffect, useRef, useState } from 'react';

import {
  fetchFeedPage,
  getFeedErrorMessage,
  type FeedPage,
} from '../services/feedApi';
import type { Meme } from '../types/meme';

interface MemeFeedState {
  error: string | null;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  isInitialLoading: boolean;
  loadNextPage: () => Promise<void>;
  memes: Meme[];
  paginationError: string | null;
  refresh: () => Promise<void>;
}

function mergeUniqueMemes(current: Meme[], incoming: Meme[]): Meme[] {
  const knownIds = new Set(current.map((meme) => meme.id));
  return [...current, ...incoming.filter((meme) => !knownIds.has(meme.id))];
}

export function useMemeFeed(): MemeFeedState {
  const [memes, setMemes] = useState<Meme[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isFetchingNextPage, setIsFetchingNextPage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paginationError, setPaginationError] = useState<string | null>(null);

  const memesRef = useRef<Meme[]>([]);
  const nextCursorRef = useRef<string | null>(null);
  const initialRequestRef = useRef<AbortController | null>(null);
  const nextPageRequestRef = useRef<AbortController | null>(null);

  const applyInitialPage = useCallback((page: FeedPage) => {
    memesRef.current = page.items;
    nextCursorRef.current = page.nextCursor;
    setMemes(page.items);
  }, []);

  const refresh = useCallback(async () => {
    initialRequestRef.current?.abort();
    nextPageRequestRef.current?.abort();

    const controller = new AbortController();
    initialRequestRef.current = controller;
    setIsInitialLoading(memesRef.current.length === 0);
    setIsFetchingNextPage(false);
    setError(null);
    setPaginationError(null);

    try {
      const page = await fetchFeedPage({ signal: controller.signal });
      if (initialRequestRef.current !== controller) return;
      applyInitialPage(page);
    } catch (requestError) {
      if (initialRequestRef.current !== controller || controller.signal.aborted) return;
      setError(getFeedErrorMessage(requestError));
    } finally {
      if (initialRequestRef.current === controller) {
        initialRequestRef.current = null;
        setIsInitialLoading(false);
      }
    }
  }, [applyInitialPage]);

  const loadNextPage = useCallback(async () => {
    const cursor = nextCursorRef.current;
    if (cursor === null || nextPageRequestRef.current) return;

    const controller = new AbortController();
    nextPageRequestRef.current = controller;
    setIsFetchingNextPage(true);
    setPaginationError(null);

    try {
      const page = await fetchFeedPage({ cursor, signal: controller.signal });
      if (nextPageRequestRef.current !== controller) return;

      const merged = mergeUniqueMemes(memesRef.current, page.items);
      const madeProgress = merged.length > memesRef.current.length;
      memesRef.current = merged;
      nextCursorRef.current =
        madeProgress && page.nextCursor !== cursor ? page.nextCursor : null;
      setMemes(merged);
    } catch (requestError) {
      if (nextPageRequestRef.current !== controller || controller.signal.aborted) return;
      setPaginationError(getFeedErrorMessage(requestError));
    } finally {
      if (nextPageRequestRef.current === controller) {
        nextPageRequestRef.current = null;
        setIsFetchingNextPage(false);
      }
    }
  }, []);

  useEffect(() => {
    void refresh();

    return () => {
      initialRequestRef.current?.abort();
      nextPageRequestRef.current?.abort();
    };
  }, [refresh]);

  return {
    error,
    hasNextPage: nextCursorRef.current !== null,
    isFetchingNextPage,
    isInitialLoading,
    loadNextPage,
    memes,
    paginationError,
    refresh,
  };
}
