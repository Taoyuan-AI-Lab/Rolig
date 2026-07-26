import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

interface AuthButtonProps {
  isLoading: boolean;
  isSignedIn: boolean;
  onPress: () => void;
}

export function AuthButton({
  isLoading,
  isSignedIn,
  onPress,
}: AuthButtonProps) {
  const insets = useSafeAreaInsets();

  return (
    <View
      className="absolute left-4"
      pointerEvents="box-none"
      style={{ top: Math.max(insets.top + 8, 16) }}
    >
      <Pressable
        accessibilityLabel={isSignedIn ? 'Open account' : 'Sign in'}
        accessibilityRole="button"
        className="flex-row items-center rounded-full border border-white/15 bg-black/75 px-4 py-2.5 active:opacity-75"
        disabled={isLoading}
        onPress={onPress}
      >
        {isLoading ? (
          <ActivityIndicator color="#ffffff" size="small" />
        ) : (
          <>
            <View
              className={
                isSignedIn
                  ? 'mr-2 h-2 w-2 rounded-full bg-emerald-400'
                  : 'mr-2 h-2 w-2 rounded-full bg-neutral-500'
              }
            />
            <Text className="text-xs font-black text-white">
              {isSignedIn ? 'Account' : 'Sign in'}
            </Text>
          </>
        )}
      </Pressable>
    </View>
  );
}
