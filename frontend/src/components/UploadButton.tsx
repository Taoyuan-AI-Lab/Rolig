import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

interface UploadButtonProps {
  onPress: () => void;
}

export function UploadButton({ onPress }: UploadButtonProps) {
  const insets = useSafeAreaInsets();

  return (
    <View
      className="absolute right-4"
      pointerEvents="box-none"
      style={{ top: Math.max(insets.top + 8, 16) }}
    >
      <Pressable
        accessibilityHint="Select permitted meme media to upload"
        accessibilityLabel="Upload a meme"
        accessibilityRole="button"
        className="flex-row items-center rounded-full border border-white/15 bg-black/75 px-4 py-2.5 active:opacity-75"
        onPress={onPress}
      >
        <Text className="mr-1.5 text-xl font-light leading-5 text-white">+</Text>
        <Text className="text-xs font-black text-white">Upload</Text>
      </Pressable>
    </View>
  );
}
