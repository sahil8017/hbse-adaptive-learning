'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Navbar from '@/components/Navbar';
import { BadgeUnlockProvider } from '@/context/BadgeUnlockContext';
import BadgeUnlockToast from '@/components/BadgeUnlockToast';

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { firebaseUser, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !firebaseUser) {
      router.push('/');
    }
  }, [firebaseUser, loading, router]);

  if (loading) return null;
  if (!firebaseUser) return null;

  return (
    <BadgeUnlockProvider>
      <div className="min-h-screen flex flex-col bg-stone-50">
        <Navbar />
        <main className="flex-1 max-w-7xl mx-auto w-full px-3 sm:px-6 lg:px-8 py-4 sm:py-6 pb-20 md:pb-6">
          {children}
        </main>
        <BadgeUnlockToast />
      </div>
    </BadgeUnlockProvider>
  );
}
