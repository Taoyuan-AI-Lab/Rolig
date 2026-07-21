import { useEffect, useMemo, useState } from 'react';
import {
  type LayoutChangeEvent,
  Pressable,
  Share,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import type { Meme } from '../types/meme';

interface MemeInteractionOverlayProps {
  meme: Meme;
  onShare?: (meme: Meme) => void;
}

interface ActionButtonProps {
  accessibilityLabel: string;
  icon: string;
  label?: string;
  onPress?: () => void;
  selected?: boolean;
}

function compactNumber(value: number) {
  return new Intl.NumberFormat('en', {
    maximumFractionDigits: 1,
    notation: 'compact',
  }).format(value);
}

function ActionButton({
  accessibilityLabel,
  icon,
  label,
  onPress,
  selected = false,
}: ActionButtonProps) {
  const content = (
    <>
      <View className="h-12 w-12 items-center justify-center rounded-full bg-black/45">
        <Text
          className={selected ? 'text-[30px] text-rose-500' : 'text-[29px] text-white'}
          style={styles.iconShadow}
        >
          {icon}
        </Text>
      </View>
      {label ? (
        <Text className="mt-1 text-[11px] font-bold text-white" style={styles.textShadow}>
          {label}
        </Text>
      ) : null}
    </>
  );

  if (!onPress) {
    return (
      <View accessibilityLabel={accessibilityLabel} className="items-center" accessible>
        {content}
      </View>
    );
  }

  return (
    <Pressable
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      className="items-center active:opacity-75"
      hitSlop={10}
      onPress={onPress}
    >
      {content}
    </Pressable>
  );
}

function MusicTicker({ title }: { title: string }) {
  const [viewportWidth, setViewportWidth] = useState(0);
  const [contentWidth, setContentWidth] = useState(0);
  const translateX = useSharedValue(0);
  const tickerText = `♫  ${title}`;

  useEffect(() => {
    cancelAnimation(translateX);
    translateX.value = 0;

    if (contentWidth > viewportWidth && viewportWidth > 0) {
      const distance = contentWidth + 36;
      const duration = Math.max(5000, distance * 35);
      translateX.value = withRepeat(
        withTiming(-distance, { duration, easing: Easing.linear }),
        -1,
        false,
      );
    }

    return () => cancelAnimation(translateX);
  }, [contentWidth, title, translateX, viewportWidth]);

  const tickerStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  const onViewportLayout = (event: LayoutChangeEvent) => {
    setViewportWidth(event.nativeEvent.layout.width);
  };

  const onContentLayout = (event: LayoutChangeEvent) => {
    setContentWidth(event.nativeEvent.layout.width);
  };

  return (
    <View
      accessibilityLabel={`Music: ${title}`}
      className="mt-3 h-6 overflow-hidden"
      onLayout={onViewportLayout}
    >
      <Animated.View className="absolute flex-row items-center" style={tickerStyle}>
        <Text
          className="whitespace-nowrap text-[13px] font-medium text-white"
          numberOfLines={1}
          onLayout={onContentLayout}
          style={styles.textShadow}
        >
          {tickerText}
        </Text>
        {contentWidth > viewportWidth && viewportWidth > 0 ? (
          <Text
            className="ml-9 whitespace-nowrap text-[13px] font-medium text-white"
            numberOfLines={1}
            style={styles.textShadow}
          >
            {tickerText}
          </Text>
        ) : null}
      </Animated.View>
    </View>
  );
}

export function MemeInteractionOverlay({ meme, onShare }: MemeInteractionOverlayProps) {
  const [liked, setLiked] = useState(false);
  const insets = useSafeAreaInsets();
  const heartScale = useSharedValue(1);
  const burstOpacity = useSharedValue(0);
  const burstScale = useSharedValue(0.5);

  const creator = useMemo(
    () => meme.creatorUsername ?? `@rolig_${meme.creatorId.slice(0, 6)}`,
    [meme.creatorId, meme.creatorUsername],
  );
  const description =
    meme.summary || `AI tags: ${meme.tags.slice(0, 3).map((tag) => `#${tag}`).join(' ')}`;
  const musicTitle = meme.musicTitle ?? `original sound · ${creator.replace('@', '')}`;

  const heartStyle = useAnimatedStyle(() => ({
    transform: [{ scale: heartScale.value }],
  }));
  const burstStyle = useAnimatedStyle(() => ({
    opacity: burstOpacity.value,
    transform: [{ scale: burstScale.value }],
  }));

  const handleLike = () => {
    setLiked((value) => !value);
    cancelAnimation(heartScale);
    cancelAnimation(burstOpacity);
    cancelAnimation(burstScale);
    heartScale.value = withSequence(
      withTiming(0.78, { duration: 70 }),
      withSpring(1.35, { damping: 8, stiffness: 360 }),
      withSpring(1, { damping: 11, stiffness: 260 }),
    );
    burstScale.value = 0.5;
    burstOpacity.value = 0.85;
    burstScale.value = withSpring(1.9, { damping: 12, stiffness: 180 });
    burstOpacity.value = withTiming(0, { duration: 420 });
  };

  const handleShare = () => {
    if (onShare) {
      onShare(meme);
      return;
    }

    void Share.share({
      message: `This made me laugh on Rolig: ${meme.url}`,
      title: 'Share meme',
      url: meme.url,
    });
  };

  return (
    <View className="absolute inset-0" pointerEvents="box-none">
      <View
        className="absolute bottom-0 left-0 right-0 h-56 bg-black/35"
        pointerEvents="none"
      />

      <View
        className="absolute right-3 items-center gap-5"
        pointerEvents="box-none"
        style={{ bottom: Math.max(insets.bottom + 122, 138) }}
      >
        <View className="relative items-center">
          <Animated.View
            className="absolute h-12 w-12 rounded-full border-2 border-rose-400"
            pointerEvents="none"
            style={burstStyle}
          />
          <Animated.View style={heartStyle}>
            <ActionButton
              accessibilityLabel={liked ? 'Unlike this meme' : 'Like this meme'}
              icon={liked ? '♥' : '♡'}
              label={compactNumber(meme.likeCount + (liked ? 1 : 0))}
              onPress={handleLike}
              selected={liked}
            />
          </Animated.View>
        </View>

        <ActionButton
          accessibilityLabel="Share this meme"
          icon="➤"
          label="Share"
          onPress={handleShare}
        />

        <ActionButton
          accessibilityLabel={`${compactNumber(meme.viewCount)} views`}
          icon="◉"
          label={compactNumber(meme.viewCount)}
        />
      </View>

      <View
        className="absolute left-4 right-24"
        pointerEvents="none"
        style={{ bottom: Math.max(insets.bottom + 14, 22) }}
      >
        <Text className="text-[17px] font-extrabold text-white" style={styles.textShadow}>
          {creator}
        </Text>
        <Text
          className="mt-1 text-[14px] leading-5 text-white"
          numberOfLines={2}
          style={styles.textShadow}
        >
          {description}
        </Text>
        <MusicTicker title={musicTitle} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  iconShadow: {
    textShadowColor: 'rgba(0, 0, 0, 0.75)',
    textShadowOffset: { height: 1, width: 0 },
    textShadowRadius: 4,
  },
  textShadow: {
    textShadowColor: 'rgba(0, 0, 0, 0.9)',
    textShadowOffset: { height: 1, width: 0 },
    textShadowRadius: 3,
  },
});
