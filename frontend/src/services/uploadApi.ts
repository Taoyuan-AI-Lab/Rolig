import { getApiBaseUrl } from '../config/env';
import type {
  UploadAttribution,
  UploadMedia,
  UploadProcessingStatus,
  UploadResult,
  UploadSession,
} from '../types/upload';

const API_TIMEOUT_MS = 20_000;
const MEDIA_UPLOAD_TIMEOUT_MS = 120_000;

export class UploadApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'UploadApiError';
    this.status = status;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function parseHeaders(value: unknown): Record<string, string> {
  if (value == null) return {};
  if (!isRecord(value)) throw new UploadApiError('The upload service returned invalid headers.');

  const headers: Record<string, string> = {};
  for (const [name, headerValue] of Object.entries(value)) {
    if (typeof headerValue !== 'string') {
      throw new UploadApiError('The upload service returned an invalid header.');
    }
    headers[name] = headerValue;
  }
  return headers;
}

function parseUploadSession(value: unknown): UploadSession {
  if (!isRecord(value)) {
    throw new UploadApiError('The upload service returned an invalid session.');
  }

  const { expiresAt, headers, uploadId, uploadUrl } = value;
  if (
    typeof uploadId !== 'string' ||
    uploadId.length === 0 ||
    typeof uploadUrl !== 'string' ||
    !uploadUrl.startsWith('https://') ||
    typeof expiresAt !== 'string' ||
    Number.isNaN(Date.parse(expiresAt))
  ) {
    throw new UploadApiError('The upload service returned an invalid session.');
  }

  return {
    expiresAt,
    headers: parseHeaders(headers),
    uploadId,
    uploadUrl,
  };
}

function isProcessingStatus(value: unknown): value is UploadProcessingStatus {
  return value === 'processing' || value === 'ready' || value === 'rejected';
}

function parseUploadResult(value: unknown): UploadResult {
  if (!isRecord(value)) {
    throw new UploadApiError('The upload service returned an invalid result.');
  }

  const { memeId, message, status, uploadId } = value;
  if (
    typeof uploadId !== 'string' ||
    !isProcessingStatus(status) ||
    (memeId !== null && typeof memeId !== 'string') ||
    (message !== null && typeof message !== 'string')
  ) {
    throw new UploadApiError('The upload service returned an invalid result.');
  }

  return { memeId, message, status, uploadId };
}

async function readErrorMessage(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json();
    if (!isRecord(body)) return null;
    if (typeof body.detail === 'string') return body.detail;
    if (typeof body.message === 'string') return body.message;
  } catch {
    // Error bodies are optional and must never obscure the HTTP status.
  }
  return null;
}

async function apiRequest(
  path: string,
  init: RequestInit,
  signal?: AbortSignal,
): Promise<unknown> {
  const controller = new AbortController();
  const abortRequest = () => controller.abort();
  signal?.addEventListener('abort', abortRequest, { once: true });
  const timeout = setTimeout(abortRequest, API_TIMEOUT_MS);

  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...init.headers,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await readErrorMessage(response);
      throw new UploadApiError(detail ?? 'The upload request failed.', response.status);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof UploadApiError) throw error;
    if (controller.signal.aborted) {
      if (signal?.aborted) throw new UploadApiError('The upload was cancelled.');
      throw new UploadApiError('The upload service took too long to respond.');
    }
    throw new UploadApiError('Unable to reach the upload service.');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abortRequest);
  }
}

export async function createUploadSession(
  media: UploadMedia,
  signal?: AbortSignal,
): Promise<UploadSession> {
  const value = await apiRequest(
    '/api/v1/uploads/presign',
    {
      body: JSON.stringify({
        contentType: media.mimeType,
        fileName: media.fileName,
        mediaType: media.mediaType,
        sizeBytes: media.fileSize,
      }),
      method: 'POST',
    },
    signal,
  );
  return parseUploadSession(value);
}

function loadMediaBody(media: UploadMedia): Promise<Blob> {
  if (media.file) return Promise.resolve(media.file);

  return fetch(media.uri).then((response) => {
    if (!response.ok) throw new UploadApiError('The selected media could not be read.');
    return response.blob();
  });
}

export async function uploadMediaToSession(
  media: UploadMedia,
  session: UploadSession,
  onProgress: (progress: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  const body = await loadMediaBody(media);

  await new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    const abortRequest = () => request.abort();

    request.open('PUT', session.uploadUrl);
    request.timeout = MEDIA_UPLOAD_TIMEOUT_MS;
    for (const [name, value] of Object.entries(session.headers)) {
      request.setRequestHeader(name, value);
    }
    if (!Object.keys(session.headers).some((name) => name.toLowerCase() === 'content-type')) {
      request.setRequestHeader('Content-Type', media.mimeType);
    }

    request.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress(Math.min(1, event.loaded / event.total));
      }
    };
    request.onload = () => {
      signal?.removeEventListener('abort', abortRequest);
      if (request.status >= 200 && request.status < 300) {
        onProgress(1);
        resolve();
      } else {
        reject(new UploadApiError('R2 rejected the media upload.', request.status));
      }
    };
    request.onerror = () => {
      signal?.removeEventListener('abort', abortRequest);
      reject(new UploadApiError('The media upload could not be completed.'));
    };
    request.ontimeout = () => {
      signal?.removeEventListener('abort', abortRequest);
      reject(new UploadApiError('The media upload took too long.'));
    };
    request.onabort = () => {
      signal?.removeEventListener('abort', abortRequest);
      reject(new UploadApiError('The upload was cancelled.'));
    };

    signal?.addEventListener('abort', abortRequest, { once: true });
    request.send(body);
  });
}

export async function completeUploadSession(
  uploadId: string,
  attribution: UploadAttribution,
  signal?: AbortSignal,
): Promise<UploadResult> {
  const value = await apiRequest(
    `/api/v1/uploads/${encodeURIComponent(uploadId)}/complete`,
    {
      body: JSON.stringify({ attribution }),
      method: 'POST',
    },
    signal,
  );
  return parseUploadResult(value);
}

export async function fetchUploadStatus(
  uploadId: string,
  signal?: AbortSignal,
): Promise<UploadResult> {
  const value = await apiRequest(
    `/api/v1/uploads/${encodeURIComponent(uploadId)}`,
    { method: 'GET' },
    signal,
  );
  return parseUploadResult(value);
}

export function getUploadErrorMessage(error: unknown): string {
  if (error instanceof UploadApiError) {
    if (error.status === 401 || error.status === 403) {
      return 'You must be signed in and allowed to upload memes.';
    }
    if (error.status === 404 || error.status === 501) {
      return 'The secure upload service is not available yet.';
    }
    if (error.status === 413) {
      return 'This file is larger than the server allows.';
    }
    if (error.status === 415 || error.status === 422) {
      return error.message;
    }
    if (error.status && error.status >= 500) {
      return 'Rolig could not process this upload. Please try again.';
    }
    return error.message;
  }
  return 'The upload could not be completed.';
}
