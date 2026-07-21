import { ActivityIndicator, Pressable, Text, View } from 'react-native';

interface RetryStateProps {
  message?: string;
  onRetry: () => void;
}

export function FeedLoading() {
  return (
    <View className="flex-1 items-center justify-center bg-black px-8">
      <ActivityIndicator color="#ffffff" size="large" />
      <Text className="mt-4 text-sm font-semibold text-white/70">
        Finding your next laugh…
      </Text>
    </View>
  );
}

export function FeedError({ message, onRetry }: RetryStateProps) {
  return (
    <View className="flex-1 items-center justify-center bg-black px-8">
      <Text className="text-center text-3xl font-black text-white">Feed offline</Text>
      <Text className="mt-3 max-w-sm text-center text-base leading-6 text-white/70">
        {message}
      </Text>
      <RetryButton onPress={onRetry} />
    </View>
  );
}

export function EmptyFeed({ onRetry }: RetryStateProps) {
  return (
    <View className="flex-1 items-center justify-center bg-black px-8">
      <Text className="text-center text-3xl font-black text-white">That’s all for now</Text>
      <Text className="mt-3 text-center text-base text-white/70">
        Fresh memes are being prepared. Check again in a moment.
      </Text>
      <RetryButton onPress={onRetry} />
    </View>
  );
}

function RetryButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      className="mt-6 rounded-full bg-white px-6 py-3 active:opacity-80"
      onPress={onPress}
    >
      <Text className="font-bold text-black">Try again</Text>
    </Pressable>
  );
}
