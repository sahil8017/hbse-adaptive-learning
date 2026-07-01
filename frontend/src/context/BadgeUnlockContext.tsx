'use client';

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

export interface UnlockableBadge {
  code: string;
  name: string;
  description: string;
  tier: 'bronze' | 'silver' | 'gold';
}

interface BadgeUnlockContextValue {
  queue: UnlockableBadge[];
  triggerBadgeUnlocks: (badges: UnlockableBadge[]) => void;
  dismissCurrent: () => void;
}

const BadgeUnlockContext = createContext<BadgeUnlockContextValue | null>(null);

export function BadgeUnlockProvider({ children }: { children: ReactNode }) {
  const [queue, setQueue] = useState<UnlockableBadge[]>([]);

  const triggerBadgeUnlocks = useCallback((badges: UnlockableBadge[]) => {
    if (!badges.length) return;
    setQueue((prev) => [...prev, ...badges]);
  }, []);

  const dismissCurrent = useCallback(() => {
    setQueue((prev) => prev.slice(1));
  }, []);

  return (
    <BadgeUnlockContext.Provider value={{ queue, triggerBadgeUnlocks, dismissCurrent }}>
      {children}
    </BadgeUnlockContext.Provider>
  );
}

export function useBadgeUnlock() {
  const ctx = useContext(BadgeUnlockContext);
  if (!ctx) throw new Error('useBadgeUnlock must be used within BadgeUnlockProvider');
  return ctx;
}
