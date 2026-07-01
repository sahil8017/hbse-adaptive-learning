import { useEffect, useState } from 'react';

interface LoadingConfig {
  initialMessage?: string;
  timeout?: number;
  showSpinner?: boolean;
}

export function usePageLoading(config: LoadingConfig = {}) {
  const {
    initialMessage = 'Loading...',
    timeout = 5000,
    showSpinner = true,
  } = config;

  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState(initialMessage);

  const setLoaded = (msg?: string) => {
    if (msg) setMessage(msg);
    setIsLoading(false);
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      if (isLoading) {
        setMessage('Still loading... Please wait');
      }
    }, timeout);

    return () => clearTimeout(timer);
  }, [isLoading, timeout]);

  return {
    isLoading,
    message,
    setLoaded,
    setMessage,
    showSpinner,
  };
}
