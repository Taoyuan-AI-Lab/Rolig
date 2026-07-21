import { useCallback, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  type LayoutChangeEvent,
  type ListRenderItemInfo,
  Pressable,
  Text,
  type ViewToken,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useMemePrefetch } from '../hooks/useMemePrefetch';
import type { Meme } from '../types/meme';
import { MemeCard } from './MemeCard';

interface MemeFeedProps {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  memes: readonly Meme[];
  onEndReached?: () => void;
  onRetryPagination: () => void;
  paginationError: string | null;
}

const VIEWABILITY_CONFIG = {
  itemVisiblePercentThreshold: 80,
  minimumViewTime: 100,
};

export function MemeFeed({
  hasNextPage,
  isFetchingNextPage,
  memes,
  onEndReached,
  onRetryPagination,
  paginationError,
}: MemeFeedProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const insets = useSafeAreaInsets();

  useMemePrefetch(memes, activeIndex);

  const onLayout = useCallback((event: LayoutChangeEvent) => {
    setViewportHeight(event.nativeEvent.layout.height);
  }, []);

  const onViewableItemsChanged = useRef(
    ({ viewableItems }: { viewableItems: ViewToken<Meme>[] }) => {
      const nextVisible = viewableItems.find(
        (token): token is ViewToken<Meme> & { index: number } =>
          token.isViewable && token.index != null,
      );

      if (nextVisible) setActiveIndex(nextVisible.index);
    },
  ).current;

  const renderItem = useCallback(
    ({ item, index }: ListRenderItemInfo<Meme>) => (
      <MemeCard active={index === activeIndex} height={viewportHeight} meme={item} />
    ),
    [activeIndex, viewportHeight],
  );

  const getItemLayout = useCallback(
    (_data: ArrayLike<Meme> | null | undefined, index: number) => ({
      index,
      length: viewportHeight,
      offset: viewportHeight * index,
    }),
    [viewportHeight],
  );

  return (
    <View className="flex-1 bg-black" onLayout={onLayout}>
      {viewportHeight > 0 && (
        <FlatList
          bounces={false}
          data={memes}
          decelerationRate="fast"
          disableIntervalMomentum
          getItemLayout={getItemLayout}
          initialNumToRender={2}
          keyExtractor={(item) => item.id}
          maxToRenderPerBatch={3}
          onEndReached={hasNextPage ? onEndReached : undefined}
          onEndReachedThreshold={1.5}
          onViewableItemsChanged={onViewableItemsChanged}
          pagingEnabled
          removeClippedSubviews
          renderItem={renderItem}
          showsVerticalScrollIndicator={false}
          snapToAlignment="start"
          snapToInterval={viewportHeight}
          viewabilityConfig={VIEWABILITY_CONFIG}
          windowSize={5}
        />
      )}

      {(isFetchingNextPage || paginationError) && (
        <View
          className="absolute inset-x-4 items-center"
          pointerEvents={paginationError ? 'auto' : 'none'}
          style={{ top: Math.max(insets.top, 16) }}
        >
          {isFetchingNextPage ? (
            <View className="flex-row items-center rounded-full bg-black/70 px-4 py-2">
              <ActivityIndicator color="#ffffff" size="small" />
              <Text className="ml-2 text-xs font-semibold text-white">Loading more…</Text>
            </View>
          ) : (
            <Pressable
              accessibilityRole="button"
              className="rounded-full bg-red-500 px-4 py-2 active:opacity-80"
              onPress={onRetryPagination}
            >
              <Text className="text-center text-xs font-bold text-white">
                Couldn’t load more · Tap to retry
              </Text>
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
}
