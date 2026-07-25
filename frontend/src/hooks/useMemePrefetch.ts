import { useEffect, useRef } from 'react';
import { Platform } from 'react-native';
import { Image } from 'expo-image';
import {
  createVideoPlayer,
  type VideoSource,
} from 'expo-video';

import type { Meme } from '../types/meme';

const PREFETCH_DISTANCE = 3;

interface CachedVideoResource {
  release: () => void;
  url: string;
}

function preloadVideo(url: string): CachedVideoResource {
  if (Platform.OS === 'web' && typeof document !== 'undefined') {
    const video = document.createElement('video');
    video.muted = true;
    video.preload = 'auto';
    video.src = url;
    video.load();

    return {
      url,
      release: () => {
        video.pause();
        video.removeAttribute('src');
        video.load();
      },
    };
  }

  const source: VideoSource = { uri: url, useCaching: true };
  const player = createVideoPlayer(source);
  player.muted = true;

  return { url, release: () => player.release() };
}

/**
 * Warms media for i+1, i+2 and i+3 whenever the visible index changes.
 *
 * Images are decoded into Expo Image's memory/disk cache. Videos get detached
 * players, which makes the native player begin buffering even without a
 * VideoView; `useCaching` also lets the visible player reuse downloaded bytes.
 * On web, detached `video` elements with `preload="auto"` warm the browser's
 * HTTP media cache instead.
 * Doing this while the user is watching item i shifts network and decode work
 * away from the next swipe, substantially reducing blank frames and spinners.
 *
 * Only the three-item look-ahead window retains video players. Releasing stale
 * players prevents a long feed session from accumulating native decoders.
 */
export function useMemePrefetch(memes: readonly Meme[], activeIndex: number) {
  const prefetchedImages = useRef(new Set<string>());
  const videoResources = useRef(new Map<string, CachedVideoResource>());

  useEffect(() => {
    const upcoming = memes.slice(
      activeIndex + 1,
      activeIndex + 1 + PREFETCH_DISTANCE,
    );
    const upcomingVideos = upcoming.filter((meme) => meme.type === 'video');
    const desiredVideoIds = new Set(upcomingVideos.map((meme) => meme.id));

    const imageUrls = upcoming
      .filter((meme) => meme.type === 'image')
      .map((meme) => meme.url)
      .filter((url) => {
        if (prefetchedImages.current.has(url)) return false;
        prefetchedImages.current.add(url);
        return true;
      });

    if (imageUrls.length > 0) {
      void Image.prefetch(imageUrls, 'memory-disk').then((didPrefetch) => {
        // A failed batch is removed so a later visit can retry it.
        if (!didPrefetch) {
          imageUrls.forEach((url) => prefetchedImages.current.delete(url));
        }
      });
    }

    videoResources.current.forEach((cached, id) => {
      const stillDesired = desiredVideoIds.has(id);
      const nextVersion = upcomingVideos.find((meme) => meme.id === id);

      if (!stillDesired || nextVersion?.url !== cached.url) {
        cached.release();
        videoResources.current.delete(id);
      }
    });

    upcomingVideos.forEach((meme) => {
      if (videoResources.current.has(meme.id)) return;
      videoResources.current.set(meme.id, preloadVideo(meme.url));
    });
  }, [activeIndex, memes]);

  useEffect(
    () => () => {
      videoResources.current.forEach(({ release }) => release());
      videoResources.current.clear();
    },
    [],
  );
}
