import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

interface AuthStorage {
  getItem: (key: string) => Promise<string | null>;
  removeItem: (key: string) => Promise<void>;
  setItem: (key: string, value: string) => Promise<void>;
}

interface SecureStoreManifest {
  chunks: number;
  version: string;
}

const CHUNK_SIZE = 1_800;
const MAX_CHUNKS = 64;
const MANIFEST_SUFFIX = '.manifest';
const secureStoreOptions: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

function manifestKey(key: string): string {
  return `${key}${MANIFEST_SUFFIX}`;
}

function chunkKey(key: string, version: string, index: number): string {
  return `${key}.${version}.${index}`;
}

function parseManifest(value: string | null): SecureStoreManifest | null {
  if (!value) return null;
  try {
    const parsed: unknown = JSON.parse(value);
    if (typeof parsed === 'object' && parsed !== null) {
      const chunks = 'chunks' in parsed ? parsed.chunks : undefined;
      const version = 'version' in parsed ? parsed.version : undefined;
      if (
        typeof chunks === 'number' &&
        Number.isInteger(chunks) &&
        chunks > 0 &&
        chunks <= MAX_CHUNKS &&
        typeof version === 'string' &&
        /^[A-Za-z0-9_-]+$/.test(version)
      ) {
        return { chunks, version };
      }
    }
  } catch {
    // Corrupt session metadata is treated as a signed-out state.
  }
  return null;
}

async function deleteManifestChunks(
  key: string,
  manifest: SecureStoreManifest | null,
) {
  if (!manifest) return;
  await Promise.all(
    Array.from({ length: manifest.chunks }, (_, index) =>
      SecureStore.deleteItemAsync(chunkKey(key, manifest.version, index)),
    ),
  );
}

const nativeSecureStorage: AuthStorage = {
  async getItem(key) {
    const rawManifest = await SecureStore.getItemAsync(manifestKey(key));
    const manifest = parseManifest(rawManifest);
    if (!manifest) {
      if (rawManifest) await SecureStore.deleteItemAsync(manifestKey(key));
      return null;
    }

    const chunks = await Promise.all(
      Array.from({ length: manifest.chunks }, (_, index) =>
        SecureStore.getItemAsync(chunkKey(key, manifest.version, index)),
      ),
    );
    return chunks.every((chunk): chunk is string => chunk !== null)
      ? chunks.join('')
      : null;
  },

  async removeItem(key) {
    const manifest = parseManifest(
      await SecureStore.getItemAsync(manifestKey(key)),
    );
    await SecureStore.deleteItemAsync(manifestKey(key));
    await deleteManifestChunks(key, manifest);
  },

  async setItem(key, value) {
    const chunks = value.match(new RegExp(`.{1,${CHUNK_SIZE}}`, 'gs')) ?? [''];
    if (chunks.length > MAX_CHUNKS) {
      throw new Error(
        'The authentication session is too large to store securely.',
      );
    }

    const previous = parseManifest(
      await SecureStore.getItemAsync(manifestKey(key)),
    );
    const version = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
    await Promise.all(
      chunks.map((chunk, index) =>
        SecureStore.setItemAsync(
          chunkKey(key, version, index),
          chunk,
          secureStoreOptions,
        ),
      ),
    );
    await SecureStore.setItemAsync(
      manifestKey(key),
      JSON.stringify({ chunks: chunks.length, version }),
      secureStoreOptions,
    );
    await deleteManifestChunks(key, previous);
  },
};

export const authStorage: AuthStorage =
  Platform.OS === 'web' ? AsyncStorage : nativeSecureStorage;
