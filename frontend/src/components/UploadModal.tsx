import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import {
  completeUploadSession,
  createUploadSession,
  fetchUploadStatus,
  getUploadErrorMessage,
  uploadMediaToSession,
} from '../services/uploadApi';
import {
  UPLOAD_LICENSES,
  type UploadAttribution,
  type UploadLicense,
  type UploadMedia,
  type UploadResult,
} from '../types/upload';

const MAX_IMAGE_BYTES = 20 * 1024 * 1024;
const MAX_VIDEO_BYTES = 75 * 1024 * 1024;
const STATUS_POLL_ATTEMPTS = 15;
const STATUS_POLL_INTERVAL_MS = 2_000;

const SUPPORTED_IMAGE_TYPES = new Set(['image/gif', 'image/jpeg', 'image/png', 'image/webp']);
const SUPPORTED_VIDEO_TYPES = new Set([
  'video/mp4',
  'video/quicktime',
  'video/webm',
  'video/x-m4v',
]);

type UploadStage =
  | 'form'
  | 'creating'
  | 'uploading'
  | 'finalizing'
  | 'processing'
  | 'ready'
  | 'pending'
  | 'rejected'
  | 'error';

interface UploadModalProps {
  onClose: () => void;
  onPublished: () => void;
  visible: boolean;
}

function inferMimeType(asset: ImagePicker.ImagePickerAsset): string {
  if (asset.mimeType) return asset.mimeType.toLowerCase();
  const extension = asset.fileName?.split('.').pop()?.toLowerCase();
  const inferred: Record<string, string> = {
    gif: 'image/gif',
    jpeg: 'image/jpeg',
    jpg: 'image/jpeg',
    m4v: 'video/x-m4v',
    mov: 'video/quicktime',
    mp4: 'video/mp4',
    png: 'image/png',
    webm: 'video/webm',
    webp: 'image/webp',
  };
  return extension ? (inferred[extension] ?? '') : '';
}

function normalizeMedia(asset: ImagePicker.ImagePickerAsset): UploadMedia {
  const mimeType = inferMimeType(asset);
  const isImage = asset.type === 'image' || SUPPORTED_IMAGE_TYPES.has(mimeType);
  const isVideo = asset.type === 'video' || SUPPORTED_VIDEO_TYPES.has(mimeType);

  if ((!isImage && !isVideo) || !mimeType) {
    throw new Error('Choose a JPEG, PNG, WebP, GIF, MP4, MOV, M4V, or WebM file.');
  }
  if (isImage && !SUPPORTED_IMAGE_TYPES.has(mimeType)) {
    throw new Error('This image format is not supported.');
  }
  if (isVideo && !SUPPORTED_VIDEO_TYPES.has(mimeType)) {
    throw new Error('This video format is not supported.');
  }

  const mediaType = isVideo ? 'video' : 'image';
  const maxBytes = mediaType === 'video' ? MAX_VIDEO_BYTES : MAX_IMAGE_BYTES;
  if (asset.fileSize != null && asset.fileSize > maxBytes) {
    const maxMegabytes = Math.round(maxBytes / (1024 * 1024));
    throw new Error(`${mediaType === 'video' ? 'Videos' : 'Images'} must be under ${maxMegabytes} MB.`);
  }

  const fallbackExtension = mediaType === 'video' ? 'mp4' : 'jpg';
  return {
    file: asset.file,
    fileName: asset.fileName ?? `rolig-upload-${Date.now()}.${fallbackExtension}`,
    fileSize: asset.fileSize,
    height: asset.height,
    mediaType,
    mimeType,
    uri: asset.uri,
    width: asset.width,
  };
}

function formatBytes(value?: number): string {
  if (value == null) return 'Size checked by server';
  const megabytes = value / (1024 * 1024);
  return megabytes < 1 ? `${Math.round(value / 1024)} KB` : `${megabytes.toFixed(1)} MB`;
}

function isHttpsUrl(value: string): boolean {
  try {
    return new URL(value).protocol === 'https:';
  } catch {
    return false;
  }
}

function delay(milliseconds: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, milliseconds));
}

function StageIndicator({ progress, stage }: { progress: number; stage: UploadStage }) {
  const labels: Partial<Record<UploadStage, string>> = {
    creating: 'Securing upload…',
    finalizing: 'Verifying media…',
    processing: 'Analyzing safety and humor…',
    uploading: `Uploading ${Math.round(progress * 100)}%`,
  };
  const label = labels[stage];
  if (!label) return null;

  return (
    <View className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
      <View className="flex-row items-center">
        <ActivityIndicator color="#ffffff" />
        <Text className="ml-3 text-sm font-bold text-white">{label}</Text>
      </View>
      {stage === 'uploading' ? (
        <View className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/15">
          <View className="h-full rounded-full bg-white" style={{ width: `${progress * 100}%` }} />
        </View>
      ) : null}
    </View>
  );
}

export function UploadModal({ onClose, onPublished, visible }: UploadModalProps) {
  const insets = useSafeAreaInsets();
  const requestRef = useRef<AbortController | null>(null);
  const [media, setMedia] = useState<UploadMedia | null>(null);
  const [creatorName, setCreatorName] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [license, setLicense] = useState<UploadLicense>('Permission granted');
  const [permissionConfirmed, setPermissionConfirmed] = useState(false);
  const [stage, setStage] = useState<UploadStage>('form');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState<string | null>(null);

  const busy =
    stage === 'creating' ||
    stage === 'uploading' ||
    stage === 'finalizing' ||
    stage === 'processing';
  const formValid =
    media != null &&
    creatorName.trim().length >= 2 &&
    isHttpsUrl(sourceUrl.trim()) &&
    permissionConfirmed;

  const helperText = useMemo(() => {
    if (!media) return 'Select one image or video from your library.';
    return `${media.mediaType === 'video' ? 'Video' : 'Image'} · ${formatBytes(media.fileSize)}`;
  }, [media]);

  useEffect(
    () => () => {
      requestRef.current?.abort();
    },
    [],
  );

  const reset = () => {
    requestRef.current?.abort();
    requestRef.current = null;
    setMedia(null);
    setCreatorName('');
    setSourceUrl('');
    setLicense('Permission granted');
    setPermissionConfirmed(false);
    setStage('form');
    setProgress(0);
    setMessage(null);
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const pickMedia = async () => {
    setMessage(null);
    try {
      if (Platform.OS !== 'web') {
        const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!permission.granted) {
          setMessage('Photo library permission is required to select a meme.');
          return;
        }
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        allowsEditing: false,
        allowsMultipleSelection: false,
        exif: false,
        mediaTypes: ['images', 'videos'],
        quality: 0.9,
        selectionLimit: 1,
      });
      if (!result.canceled && result.assets[0]) {
        setMedia(normalizeMedia(result.assets[0]));
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not open the media library.');
    }
  };

  const waitForResult = async (
    initialResult: UploadResult,
    signal: AbortSignal,
  ): Promise<UploadResult> => {
    let result = initialResult;
    for (let attempt = 0; result.status === 'processing' && attempt < STATUS_POLL_ATTEMPTS; attempt += 1) {
      await delay(STATUS_POLL_INTERVAL_MS);
      if (signal.aborted) throw new Error('Upload cancelled');
      result = await fetchUploadStatus(result.uploadId, signal);
    }
    return result;
  };

  const submit = async () => {
    if (!formValid || !media || busy) return;

    const controller = new AbortController();
    requestRef.current = controller;
    setMessage(null);
    setProgress(0);
    setStage('creating');

    const attribution: UploadAttribution = {
      creatorName: creatorName.trim(),
      license,
      permissionConfirmed,
      sourceUrl: sourceUrl.trim(),
    };

    try {
      // The client receives only a short-lived, single-object URL. R2 account
      // credentials stay exclusively in the backend environment.
      const session = await createUploadSession(media, controller.signal);
      setStage('uploading');
      await uploadMediaToSession(media, session, setProgress, controller.signal);

      setStage('finalizing');
      const initialResult = await completeUploadSession(
        session.uploadId,
        attribution,
        controller.signal,
      );

      setStage('processing');
      const result = await waitForResult(initialResult, controller.signal);
      setMessage(result.message);

      if (result.status === 'ready') {
        setStage('ready');
        onPublished();
      } else if (result.status === 'rejected') {
        setStage('rejected');
      } else {
        setStage('pending');
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setMessage(getUploadErrorMessage(error));
        setStage('error');
      }
    } finally {
      if (requestRef.current === controller) requestRef.current = null;
    }
  };

  const restart = () => {
    setStage('form');
    setProgress(0);
    setMessage(null);
  };

  const terminalTitle: Partial<Record<UploadStage, string>> = {
    error: 'Upload unsuccessful',
    pending: 'Analysis continues',
    ready: 'Meme published',
    rejected: 'Meme not published',
  };

  return (
    <Modal
      animationType="slide"
      onRequestClose={close}
      presentationStyle="pageSheet"
      transparent={Platform.OS !== 'ios'}
      visible={visible}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        className="flex-1 justify-end bg-black/70"
      >
        <View
          className="max-h-full rounded-t-[30px] border-t border-white/10 bg-neutral-950"
          style={{ paddingBottom: Math.max(insets.bottom, 18), paddingTop: 8 }}
        >
          <View className="items-center py-2">
            <View className="h-1 w-10 rounded-full bg-white/25" />
          </View>

          <View className="flex-row items-center justify-between px-5 pb-3">
            <View>
              <Text className="text-2xl font-black text-white">Upload a meme</Text>
              <Text className="mt-1 text-xs text-neutral-400">Private until safety review passes</Text>
            </View>
            <Pressable
              accessibilityLabel="Close upload"
              accessibilityRole="button"
              className="h-10 w-10 items-center justify-center rounded-full bg-white/10 active:opacity-70"
              disabled={busy}
              onPress={close}
            >
              <Text className="text-xl font-semibold text-white">×</Text>
            </Pressable>
          </View>

          <ScrollView
            contentContainerStyle={{ paddingBottom: 12, paddingHorizontal: 20 }}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {terminalTitle[stage] ? (
              <View className="items-center py-12">
                <View className="h-16 w-16 items-center justify-center rounded-full bg-white">
                  <Text className="text-3xl text-black">
                    {stage === 'ready' ? '✓' : stage === 'rejected' ? '!' : '…'}
                  </Text>
                </View>
                <Text className="mt-5 text-center text-2xl font-black text-white">
                  {terminalTitle[stage]}
                </Text>
                <Text className="mt-2 max-w-sm text-center text-sm leading-5 text-neutral-400">
                  {message ??
                    (stage === 'ready'
                      ? 'The approved meme is ready for the feed.'
                      : stage === 'pending'
                        ? 'You can close this screen. Rolig will finish moderation in the background.'
                        : stage === 'rejected'
                          ? 'The upload did not pass Rolig’s safety review.'
                          : 'Check the details and try again.')}
                </Text>
                <View className="mt-7 w-full gap-3">
                  {(stage === 'error' || stage === 'rejected') && (
                    <Pressable
                      className="rounded-full bg-white px-5 py-4 active:opacity-80"
                      onPress={restart}
                    >
                      <Text className="text-center text-base font-black text-black">Try again</Text>
                    </Pressable>
                  )}
                  <Pressable
                    className="rounded-full border border-white/15 px-5 py-4 active:opacity-80"
                    onPress={close}
                  >
                    <Text className="text-center text-base font-bold text-white">Close</Text>
                  </Pressable>
                </View>
              </View>
            ) : (
              <>
                <Pressable
                  accessibilityLabel="Select meme media"
                  accessibilityRole="button"
                  className="mt-3 h-48 overflow-hidden rounded-3xl border border-dashed border-white/25 bg-white/5 active:opacity-80"
                  disabled={busy}
                  onPress={pickMedia}
                >
                  {media?.mediaType === 'image' ? (
                    <Image contentFit="cover" source={{ uri: media.uri }} style={{ height: '100%', width: '100%' }} />
                  ) : (
                    <View className="flex-1 items-center justify-center p-6">
                      <Text className="text-4xl text-white">{media ? '▶' : '+'}</Text>
                      <Text className="mt-3 text-center text-sm font-bold text-white">
                        {media ? media.fileName : 'Choose an image or video'}
                      </Text>
                      <Text className="mt-1 text-center text-xs text-neutral-400">{helperText}</Text>
                    </View>
                  )}
                </Pressable>

                {media?.mediaType === 'image' ? (
                  <Pressable className="mt-2 self-center px-4 py-2" disabled={busy} onPress={pickMedia}>
                    <Text className="text-sm font-bold text-white">Choose different media</Text>
                  </Pressable>
                ) : null}

                <Text className="mb-2 mt-5 text-xs font-black uppercase tracking-widest text-neutral-400">
                  Attribution
                </Text>
                <TextInput
                  autoCapitalize="words"
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-base text-white"
                  editable={!busy}
                  maxLength={80}
                  onChangeText={setCreatorName}
                  placeholder="Original creator or account"
                  placeholderTextColor="#737373"
                  value={creatorName}
                />
                <TextInput
                  autoCapitalize="none"
                  autoCorrect={false}
                  className="mt-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-base text-white"
                  editable={!busy}
                  keyboardType="url"
                  maxLength={500}
                  onChangeText={setSourceUrl}
                  placeholder="https://source.example/post"
                  placeholderTextColor="#737373"
                  value={sourceUrl}
                />
                {sourceUrl.length > 0 && !isHttpsUrl(sourceUrl.trim()) ? (
                  <Text className="mt-2 text-xs text-rose-400">Enter a complete HTTPS source URL.</Text>
                ) : null}

                <Text className="mb-2 mt-5 text-xs font-black uppercase tracking-widest text-neutral-400">
                  Rights
                </Text>
                <View className="flex-row flex-wrap gap-2">
                  {UPLOAD_LICENSES.map((option) => (
                    <Pressable
                      accessibilityRole="radio"
                      accessibilityState={{ checked: license === option }}
                      className={
                        license === option
                          ? 'rounded-full bg-white px-4 py-2.5'
                          : 'rounded-full border border-white/15 px-4 py-2.5'
                      }
                      disabled={busy}
                      key={option}
                      onPress={() => setLicense(option)}
                    >
                      <Text
                        className={
                          license === option
                            ? 'text-xs font-bold text-black'
                            : 'text-xs font-bold text-white'
                        }
                      >
                        {option}
                      </Text>
                    </Pressable>
                  ))}
                </View>

                <Pressable
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: permissionConfirmed }}
                  className="mt-5 flex-row rounded-2xl border border-white/10 bg-white/5 p-4 active:opacity-80"
                  disabled={busy}
                  onPress={() => setPermissionConfirmed((value) => !value)}
                >
                  <View
                    className={
                      permissionConfirmed
                        ? 'mr-3 h-6 w-6 items-center justify-center rounded-md bg-white'
                        : 'mr-3 h-6 w-6 rounded-md border border-white/30'
                    }
                  >
                    {permissionConfirmed ? <Text className="font-black text-black">✓</Text> : null}
                  </View>
                  <Text className="flex-1 text-sm leading-5 text-neutral-300">
                    I confirm this upload is permitted and the attribution above is accurate.
                  </Text>
                </Pressable>

                {message ? <Text className="mt-4 text-sm text-rose-400">{message}</Text> : null}
                <StageIndicator progress={progress} stage={stage} />

                <Pressable
                  accessibilityRole="button"
                  className={
                    formValid && !busy
                      ? 'mt-6 rounded-full bg-white px-5 py-4 active:opacity-80'
                      : 'mt-6 rounded-full bg-white/15 px-5 py-4'
                  }
                  disabled={!formValid || busy}
                  onPress={() => void submit()}
                >
                  <Text
                    className={
                      formValid && !busy
                        ? 'text-center text-base font-black text-black'
                        : 'text-center text-base font-black text-neutral-500'
                    }
                  >
                    Upload for review
                  </Text>
                </Pressable>
                <Text className="mt-3 text-center text-[11px] leading-4 text-neutral-500">
                  Rolig validates the file again on the server. Uploads are not public until moderation succeeds.
                </Text>
              </>
            )}
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}
