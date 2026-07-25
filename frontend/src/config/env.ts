const rawApiUrl = process.env.EXPO_PUBLIC_API_URL;

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
    throw new EnvironmentError('EXPO_PUBLIC_API_URL must use HTTPS in production.');
  }

  return normalizedUrl;
}
