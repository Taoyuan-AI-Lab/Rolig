import assert from 'node:assert/strict';
import test from 'node:test';

import {
  EnvironmentError,
  validateSupabasePublicConfig,
} from './env.ts';

const projectUrl = 'https://project-ref.supabase.co';
const publishableKey = `sb_publishable_${'a'.repeat(32)}`;

function legacyJwt(role) {
  const encode = (value) =>
    Buffer.from(JSON.stringify(value)).toString('base64url');
  return [
    encode({ alg: 'HS256', typ: 'JWT' }),
    encode({ role }),
    'test-signature',
  ].join('.');
}

test('accepts only a modern Supabase publishable key', () => {
  assert.deepEqual(
    validateSupabasePublicConfig(projectUrl, publishableKey),
    {
      publishableKey,
      url: projectUrl,
    },
  );
});

for (const [name, key] of [
  ['new secret key', `sb_secret_${'a'.repeat(32)}`],
  ['legacy service-role JWT', legacyJwt('service_role')],
  ['legacy anon JWT', legacyJwt('anon')],
  ['placeholder', 'sb_publishable_replace_me'],
  ['malformed publishable key', `sb_publishable_${'a'.repeat(19)}!`],
]) {
  test(`rejects a ${name}`, () => {
    assert.throws(
      () => validateSupabasePublicConfig(projectUrl, key),
      EnvironmentError,
    );
  });
}

for (const url of [
  'http://project-ref.supabase.co',
  'https://user:password@project-ref.supabase.co',
  'https://project-ref.supabase.co/rest/v1',
  'https://project-ref.supabase.co?redirect=.supabase.co',
]) {
  test(`rejects unsafe Supabase URL: ${url}`, () => {
    assert.throws(
      () => validateSupabasePublicConfig(url, publishableKey),
      EnvironmentError,
    );
  });
}
