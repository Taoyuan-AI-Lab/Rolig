import { memo, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { useVideoPlayer, VideoView, type VideoSource } from 'expo-video';

import type { Meme } from '../types/meme';
import { MemeInteractionOverlay } from './MemeInteractionOverlay';

interface MemeCardProps {
  active: boolean;
  height: number;
  meme: Meme;
}

interface VideoMemeProps {
  active: boolean;
  meme: Meme;
}

function VideoMeme({ active, meme }: VideoMemeProps) {
  // Browsers prohibit unmuted autoplay. Native starts with sound, while web
  // starts muted and lets the user opt in with one tap.
  const [muted, setMuted] = useState(Platform.OS === 'web');
  const [firstFrameReady, setFirstFrameReady] = useState(false);
  const source: VideoSource = { uri: meme.url, useCaching: true };
  const player = useVideoPlayer(source, (instance) => {
    instance.loop = true;
    instance.muted = Platform.OS === 'web';
  });

  useEffect(() => {
    player.muted = muted;
  }, [muted, player]);

  useEffect(() => {
    if (active) {
      player.play();
    } else {
      player.pause();
    }
  }, [active, player]);

  return (
    <Pressable
      accessibilityHint="Mutes or unmutes this video"
      accessibilityLabel={muted ? 'Unmute video' : 'Mute video'}
      accessibilityRole="button"
      className="absolute inset-0"
      onPress={() => setMuted((value) => !value)}
    >
      <VideoView
        contentFit="cover"
        nativeControls={false}
        onFirstFrameRender={() => setFirstFrameReady(true)}
        player={player}
        style={styles.media}
        surfaceType="textureView"
      />
      {!firstFrameReady && (
        <View className="absolute inset-0 items-center justify-center bg-neutral-950">
          <ActivityIndicator color="#ffffff" size="large" />
        </View>
      )}
      <View className="absolute right-4 top-4 rounded-full bg-black/50 px-3 py-1.5">
        <Text className="text-xs font-semibold text-white">
          {muted ? 'Muted' : 'Sound on'}
        </Text>
      </View>
    </Pressable>
  );
}

export const MemeCard = memo(function MemeCard({ active, height, meme }: MemeCardProps) {
  return (
    <View className="relative overflow-hidden bg-black" style={{ height }}>
      {meme.type === 'image' ? (
        <Image
          cachePolicy="memory-disk"
          contentFit="cover"
          recyclingKey={meme.id}
          source={{ uri: meme.url }}
          style={styles.media}
          transition={180}
        />
      ) : (
        <VideoMeme active={active} meme={meme} />
      )}

      <MemeInteractionOverlay meme={meme} />
    </View>
  );
});

const styles = StyleSheet.create({
  media: {
    height: '100%',
    left: 0,
    position: 'absolute',
    top: 0,
    width: '100%',
  },
});
