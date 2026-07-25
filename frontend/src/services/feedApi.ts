import { getApiBaseUrl } from '../config/env';
import type { Meme } from '../types/meme';

const FEED_PAGE_SIZE = 20;
const REQUEST_TIMEOUT_MS = 15_000;

export interface FeedPage {
  items: Meme[];
  nextCursor: string | null;
}

export interface FetchFeedPageOptions {
  cursor?: string | null;
  limit?: number;
  signal?: AbortSignal;
}

export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function parseMeme(value: unknown): Meme {
  if (!isRecord(value)) throw new ApiError('The feed returned an invalid meme.');

  const { creatorId, id, likeCount, musicTitle, score, summary, tags, type, url, viewCount } =
    value;
  const validTags = Array.isArray(tags) && tags.every((tag) => typeof tag === 'string');

  if (
    typeof id !== 'string' ||
    typeof creatorId !== 'string' ||
    typeof url !== 'string' ||
    (type !== 'video' && type !== 'image') ||
    !validTags ||
    typeof score !== 'number' ||
    !Number.isFinite(score) ||
    score < 0 ||
    score > 1 ||
    typeof summary !== 'string'
  ) {
    throw new ApiError('The feed returned an invalid meme.');
  }

  return {
    creatorId,
    id,
    likeCount: typeof likeCount === 'number' && likeCount >= 0 ? likeCount : 0,
    musicTitle: typeof musicTitle === 'string' ? musicTitle : undefined,
    score,
    summary,
    tags,
    type,
    url,
    viewCount: typeof viewCount === 'number' && viewCount >= 0 ? viewCount : 0,
  };
}

function parseFeedPage(value: unknown): FeedPage {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    throw new ApiError('The feed returned an invalid response.');
  }

  const nextCursor = value.nextCursor;

  if (nextCursor !== null && typeof nextCursor !== 'string') {
    throw new ApiError('The feed returned an invalid cursor.');
  }

  return {
    items: value.items.map(parseMeme),
    nextCursor,
  };
}

export async function fetchFeedPage({
  cursor = null,
  limit = FEED_PAGE_SIZE,
  signal,
}: FetchFeedPageOptions = {}): Promise<FeedPage> {
  const requestController = new AbortController();
  const abortRequest = () => requestController.abort();
  signal?.addEventListener('abort', abortRequest, { once: true });
  const timeout = setTimeout(abortRequest, REQUEST_TIMEOUT_MS);

  try {
    const searchParams = new URLSearchParams({ limit: String(limit) });
    if (cursor) searchParams.set('cursor', cursor);

    const response = await fetch(
      `${getApiBaseUrl()}/api/v1/feed?${searchParams.toString()}`,
      {
        headers: { Accept: 'application/json' },
        signal: requestController.signal,
      },
    );

    if (!response.ok) {
      throw new ApiError('The feed request failed.', response.status);
    }

    return parseFeedPage(await response.json());
  } catch (error) {
    if (requestController.signal.aborted) {
      if (signal?.aborted) throw new ApiError('The feed request was cancelled.');
      throw new ApiError('The feed request timed out.');
    }

    if (error instanceof ApiError) throw error;
    throw new ApiError('Unable to reach the Rolig service.');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abortRequest);
  }
}

export function getFeedErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      return 'The feed is not available for this account.';
    }
    if (error.status && error.status >= 500) {
      return 'Rolig is having trouble right now. Please try again.';
    }
    if (error.message.includes('timed out')) {
      return 'The feed took too long to respond. Check your connection and retry.';
    }
  }

  return 'Could not load memes. Check your connection and try again.';
}
