import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAuth } from '../context/AuthContext';

type AuthMode = 'signIn' | 'signUp';

interface AuthModalProps {
  onClose: () => void;
  visible: boolean;
}

function readableAuthError(error: unknown): string {
  if (!(error instanceof Error))
    return 'Authentication could not be completed.';
  const message = error.message.toLowerCase();
  if (message.includes('invalid login credentials'))
    return 'The email or password is incorrect.';
  if (message.includes('email not confirmed'))
    return 'Confirm your email before signing in.';
  if (message.includes('rate limit'))
    return 'Too many attempts. Wait a moment and try again.';
  if (message.includes('password')) return error.message;
  return 'Authentication could not be completed. Please try again.';
}

export function AuthModal({ onClose, visible }: AuthModalProps) {
  const insets = useSafeAreaInsets();
  const { configurationError, session, signIn, signOut, signUp, user } =
    useAuth();
  const [mode, setMode] = useState<AuthMode>('signIn');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) {
      setMode('signIn');
      setEmail('');
      setPassword('');
      setMessage(null);
      setBusy(false);
    }
  }, [visible]);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const formValid = emailValid && password.length >= 8;

  const submit = async () => {
    if (!formValid || busy) return;
    setBusy(true);
    setMessage(null);
    try {
      if (mode === 'signIn') {
        await signIn(email, password);
        onClose();
      } else {
        const result = await signUp(email, password);
        if (result.confirmationRequired) {
          setPassword('');
          setMessage(
            'Check your email to confirm the account, then return here to sign in.',
          );
          setMode('signIn');
        } else {
          onClose();
        }
      }
    } catch (error) {
      setMessage(readableAuthError(error));
    } finally {
      setBusy(false);
    }
  };

  const logOut = async () => {
    if (busy) return;
    setBusy(true);
    setMessage(null);
    try {
      await signOut();
      onClose();
    } catch {
      setMessage('Could not sign out. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      animationType="slide"
      onRequestClose={busy ? undefined : onClose}
      presentationStyle="pageSheet"
      transparent={Platform.OS !== 'ios'}
      visible={visible}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        className="flex-1 justify-end bg-black/70"
      >
        <View
          className="rounded-t-[30px] border-t border-white/10 bg-neutral-950 px-5 pt-3"
          style={{ paddingBottom: Math.max(insets.bottom, 24) }}
        >
          <View className="items-center pb-5">
            <View className="h-1 w-10 rounded-full bg-white/25" />
          </View>
          <View className="flex-row items-center justify-between">
            <View>
              <Text className="text-2xl font-black text-white">
                {session
                  ? 'Your account'
                  : mode === 'signIn'
                    ? 'Sign in to Rolig'
                    : 'Create account'}
              </Text>
              <Text className="mt-1 text-xs text-neutral-400">
                {session
                  ? 'Your session is protected on this device.'
                  : 'Required for secure uploads'}
              </Text>
            </View>
            <Pressable
              accessibilityLabel="Close account"
              accessibilityRole="button"
              className="h-10 w-10 items-center justify-center rounded-full bg-white/10 active:opacity-70"
              disabled={busy}
              onPress={onClose}
            >
              <Text className="text-xl font-semibold text-white">×</Text>
            </Pressable>
          </View>

          {session ? (
            <View className="pt-8">
              <View className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <Text className="text-xs font-black uppercase tracking-widest text-neutral-500">
                  Signed in as
                </Text>
                <Text className="mt-2 text-base font-bold text-white">
                  {user?.email ?? 'Rolig user'}
                </Text>
              </View>
              {message ? (
                <Text className="mt-4 text-sm text-rose-400">{message}</Text>
              ) : null}
              <Pressable
                className="mt-6 rounded-full border border-rose-400/30 bg-rose-400/10 px-5 py-4 active:opacity-80"
                disabled={busy}
                onPress={() => void logOut()}
              >
                {busy ? (
                  <ActivityIndicator color="#fb7185" />
                ) : (
                  <Text className="text-center text-base font-black text-rose-400">
                    Sign out
                  </Text>
                )}
              </Pressable>
            </View>
          ) : (
            <View className="pt-8">
              {configurationError ? (
                <View className="rounded-2xl border border-amber-400/30 bg-amber-400/10 p-4">
                  <Text className="text-sm leading-5 text-amber-300">
                    {configurationError}
                  </Text>
                </View>
              ) : (
                <>
                  <TextInput
                    autoCapitalize="none"
                    autoComplete="email"
                    autoCorrect={false}
                    className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-base text-white"
                    editable={!busy}
                    keyboardType="email-address"
                    onChangeText={setEmail}
                    placeholder="Email"
                    placeholderTextColor="#737373"
                    textContentType="emailAddress"
                    value={email}
                  />
                  <TextInput
                    autoCapitalize="none"
                    autoComplete={
                      mode === 'signIn' ? 'current-password' : 'new-password'
                    }
                    className="mt-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-base text-white"
                    editable={!busy}
                    onChangeText={setPassword}
                    onSubmitEditing={() => void submit()}
                    placeholder="Password (8+ characters)"
                    placeholderTextColor="#737373"
                    secureTextEntry
                    textContentType={
                      mode === 'signIn' ? 'password' : 'newPassword'
                    }
                    value={password}
                  />
                  {message ? (
                    <Text
                      className={
                        message.startsWith('Check your email')
                          ? 'mt-4 text-sm leading-5 text-emerald-400'
                          : 'mt-4 text-sm leading-5 text-rose-400'
                      }
                    >
                      {message}
                    </Text>
                  ) : null}
                  <Pressable
                    className={
                      formValid && !busy
                        ? 'mt-6 rounded-full bg-white px-5 py-4 active:opacity-80'
                        : 'mt-6 rounded-full bg-white/15 px-5 py-4'
                    }
                    disabled={!formValid || busy}
                    onPress={() => void submit()}
                  >
                    {busy ? (
                      <ActivityIndicator color="#000000" />
                    ) : (
                      <Text
                        className={
                          formValid
                            ? 'text-center text-base font-black text-black'
                            : 'text-center text-base font-black text-neutral-500'
                        }
                      >
                        {mode === 'signIn' ? 'Sign in' : 'Create account'}
                      </Text>
                    )}
                  </Pressable>
                  <Pressable
                    className="mt-4 px-4 py-2 active:opacity-70"
                    disabled={busy}
                    onPress={() => {
                      setMode((current) =>
                        current === 'signIn' ? 'signUp' : 'signIn',
                      );
                      setMessage(null);
                    }}
                  >
                    <Text className="text-center text-sm font-bold text-neutral-300">
                      {mode === 'signIn'
                        ? 'New to Rolig? Create an account'
                        : 'Already have an account? Sign in'}
                    </Text>
                  </Pressable>
                </>
              )}
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}
