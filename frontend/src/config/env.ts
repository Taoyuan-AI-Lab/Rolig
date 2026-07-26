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

export function getSupabasePublicConfig(): SupabasePublicConfig {
  if (!rawSupabaseUrl || !rawSupabasePublishableKey) {
    throw new EnvironmentError(
      'Supabase authentication is not configured. Set the public Supabase URL and publishable key.',
    );
  }

  const url = rawSupabaseUrl.trim().replace(/\/+$/, '');
  const publishableKey = rawSupabasePublishableKey.trim();

  if (!url.startsWith('https://') || !url.endsWith('.supabase.co')) {
    throw new EnvironmentError(
      'EXPO_PUBLIC_SUPABASE_URL must be a Supabase HTTPS project URL.',
    );
  }
  if (publishableKey.startsWith('sb_secret_')) {
    throw new EnvironmentError(
      'A Supabase secret key must never be embedded in the client.',
    );
  }
  if (publishableKey.length < 20) {
    throw new EnvironmentError(
      'EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY is invalid.',
    );
  }

  return { publishableKey, url };
}
