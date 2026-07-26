import './global.css';

import { useState } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';

import { AuthButton } from './src/components/AuthButton';
import { AuthModal } from './src/components/AuthModal';
import { EmptyFeed, FeedError, FeedLoading } from './src/components/FeedState';
import { MemeFeed } from './src/components/MemeFeed';
import { UploadButton } from './src/components/UploadButton';
import { UploadModal } from './src/components/UploadModal';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import { useMemeFeed } from './src/hooks/useMemeFeed';

function RoligApp() {
  const { isLoading: isAuthLoading, session } = useAuth();
  const [authVisible, setAuthVisible] = useState(false);
  const [uploadVisible, setUploadVisible] = useState(false);
  const {
    error,
    hasNextPage,
    isFetchingNextPage,
    isInitialLoading,
    loadNextPage,
    memes,
    paginationError,
    refresh,
  } = useMemeFeed();

  let content;

  if (isInitialLoading && memes.length === 0) {
    content = <FeedLoading />;
  } else if (error && memes.length === 0) {
    content = <FeedError message={error} onRetry={refresh} />;
  } else if (memes.length === 0) {
    content = <EmptyFeed onRetry={refresh} />;
  } else {
    content = (
      <MemeFeed
        hasNextPage={hasNextPage}
        isFetchingNextPage={isFetchingNextPage}
        memes={memes}
        onEndReached={loadNextPage}
        onRetryPagination={loadNextPage}
        paginationError={paginationError}
      />
    );
  }

  return (
    <SafeAreaProvider>
      <View className="flex-1 bg-black">
        <StatusBar hidden />
        {content}
        <AuthButton
          isLoading={isAuthLoading}
          isSignedIn={session !== null}
          onPress={() => setAuthVisible(true)}
        />
        <UploadButton
          onPress={() => {
            if (session) {
              setUploadVisible(true);
            } else {
              setAuthVisible(true);
            }
          }}
        />
        <AuthModal
          onClose={() => setAuthVisible(false)}
          visible={authVisible}
        />
        <UploadModal
          onClose={() => setUploadVisible(false)}
          onPublished={() => void refresh()}
          visible={uploadVisible}
        />
      </View>
    </SafeAreaProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <RoligApp />
    </AuthProvider>
  );
}
