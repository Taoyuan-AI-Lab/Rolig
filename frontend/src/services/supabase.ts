import 'react-native-url-polyfill/auto';

import {
  createClient,
  processLock,
  type SupabaseClient,
} from '@supabase/supabase-js';
import { AppState, Platform, type NativeEventSubscription } from 'react-native';

import { getSupabasePublicConfig } from '../config/env';
import { authStorage } from './authStorage';

let client: SupabaseClient | null = null;
let appStateSubscription: NativeEventSubscription | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (client) return client;

  const { publishableKey, url } = getSupabasePublicConfig();
  client = createClient(url, publishableKey, {
    auth: {
      autoRefreshToken: true,
      detectSessionInUrl: false,
      lock: processLock,
      persistSession: true,
      storage: authStorage,
    },
  });

  if (Platform.OS !== 'web' && !appStateSubscription) {
    appStateSubscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        client?.auth.startAutoRefresh();
      } else {
        client?.auth.stopAutoRefresh();
      }
    });
  }

  return client;
}
