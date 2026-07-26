import type { Session, User } from '@supabase/supabase-js';
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { getSupabaseClient } from '../services/supabase';

export class AuthenticationRequiredError extends Error {
  constructor(message = 'Sign in to continue.') {
    super(message);
    this.name = 'AuthenticationRequiredError';
  }
}

interface SignUpResult {
  confirmationRequired: boolean;
}

interface AuthContextValue {
  configurationError: string | null;
  getAccessToken: () => Promise<string>;
  isLoading: boolean;
  session: Session | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  signUp: (email: string, password: string) => Promise<SignUpResult>;
  user: User | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [configurationError, setConfigurationError] = useState<string | null>(
    null,
  );

  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | undefined;

    try {
      const supabase = getSupabaseClient();
      void supabase.auth.getSession().then(({ data, error }) => {
        if (!active) return;
        if (error) {
          setConfigurationError('The saved session could not be restored.');
          setSession(null);
        } else {
          setSession(data.session);
        }
        setIsLoading(false);
      });

      const listener = supabase.auth.onAuthStateChange(
        (_event, nextSession) => {
          if (active) setSession(nextSession);
        },
      );
      unsubscribe = () => listener.data.subscription.unsubscribe();
    } catch (error) {
      setConfigurationError(
        error instanceof Error
          ? error.message
          : 'Supabase authentication is unavailable.',
      );
      setIsLoading(false);
    }

    return () => {
      active = false;
      unsubscribe?.();
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      configurationError,
      async getAccessToken() {
        if (configurationError)
          throw new AuthenticationRequiredError(configurationError);
        const supabase = getSupabaseClient();
        const { data, error } = await supabase.auth.getSession();
        if (error || !data.session) throw new AuthenticationRequiredError();

        const expiresAt = data.session.expires_at ?? 0;
        if (expiresAt <= Math.floor(Date.now() / 1000) + 60) {
          const refreshed = await supabase.auth.refreshSession();
          if (refreshed.error || !refreshed.data.session) {
            throw new AuthenticationRequiredError(
              'Your session expired. Sign in again.',
            );
          }
          return refreshed.data.session.access_token;
        }
        return data.session.access_token;
      },
      isLoading,
      session,
      async signIn(email, password) {
        if (configurationError) throw new Error(configurationError);
        const { error } = await getSupabaseClient().auth.signInWithPassword({
          email: email.trim().toLowerCase(),
          password,
        });
        if (error) throw error;
      },
      async signOut() {
        if (configurationError) return;
        const { error } = await getSupabaseClient().auth.signOut({
          scope: 'local',
        });
        if (error) throw error;
      },
      async signUp(email, password) {
        if (configurationError) throw new Error(configurationError);
        const { data, error } = await getSupabaseClient().auth.signUp({
          email: email.trim().toLowerCase(),
          password,
        });
        if (error) throw error;
        return { confirmationRequired: data.session === null };
      },
      user: session?.user ?? null,
    }),
    [configurationError, isLoading, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider.');
  return context;
}
