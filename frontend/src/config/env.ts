const rawApiUrl = process.env.EXPO_PUBLIC_API_URL;
const rawSupabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL;
const rawSupabasePublishableKey =
  process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export class EnvironmentError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'EnvironmentError';
  }
}

export function getApiBaseUrl(): string {
  if (!rawApiUrl) {
    throw new EnvironmentError(
      'EXPO_PUBLIC_API_URL is missing. Copy .env.example to .env and set the backend URL.',
    );
  }

  const normalizedUrl = rawApiUrl.trim().replace(/\/+$/, '');

  if (!/^https?:\/\//i.test(normalizedUrl)) {
    throw new EnvironmentError('EXPO_PUBLIC_API_URL must be an HTTP(S) URL.');
  }

  if (!__DEV__ && !normalizedUrl.startsWith('https://')) {
    throw new EnvironmentError(
      'EXPO_PUBLIC_API_URL must use HTTPS in production.',
    );
  }

  return normalizedUrl;
}

export interface SupabasePublicConfig {
  publishableKey: string;
  url: string;
}

const SUPABASE_PUBLISHABLE_KEY_PATTERN =
  /^sb_publishable_[A-Za-z0-9_-]{20,}$/;

export function validateSupabasePublicConfig(
  rawUrl: string | undefined,
  rawPublishableKey: string | undefined,
): SupabasePublicConfig {
  if (!rawUrl || !rawPublishableKey) {
    throw new EnvironmentError(
      'Supabase authentication is not configured. Set the public Supabase URL and publishable key.',
    );
  }

  const url = rawUrl.trim().replace(/\/+$/, '');
  const publishableKey = rawPublishableKey.trim();

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(url);
  } catch {
    throw new EnvironmentError(
      'EXPO_PUBLIC_SUPABASE_URL must be a Supabase HTTPS project URL.',
    );
  }

  if (
    parsedUrl.protocol !== 'https:' ||
    !parsedUrl.hostname.endsWith('.supabase.co') ||
    parsedUrl.username !== '' ||
    parsedUrl.password !== '' ||
    (parsedUrl.pathname !== '' && parsedUrl.pathname !== '/') ||
    parsedUrl.search !== '' ||
    parsedUrl.hash !== ''
  ) {
    throw new EnvironmentError(
      'EXPO_PUBLIC_SUPABASE_URL must be a Supabase HTTPS project URL.',
    );
  }

  // Only the modern public client-key format is accepted. Rejecting every
  // legacy JWT format prevents a service_role token from being accidentally
  // bundled into the public Expo application.
  if (!SUPABASE_PUBLISHABLE_KEY_PATTERN.test(publishableKey)) {
    throw new EnvironmentError(
      'EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY must be an sb_publishable_ key.',
    );
  }

  return { publishableKey, url };
}

export function getSupabasePublicConfig(): SupabasePublicConfig {
  return validateSupabasePublicConfig(
    rawSupabaseUrl,
    rawSupabasePublishableKey,
  );
}
