'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { BookOpen, Zap, TrendingUp, MessageCircle } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export default function LandingPage() {
  const { firebaseUser, loading, signInWithGoogle } = useAuth();
  const router = useRouter();
  const [error, setError] = useState('');
  const [signingIn, setSigningIn] = useState(false);

  useEffect(() => {
    if (!loading && firebaseUser) {
      router.push('/dashboard');
    }
  }, [firebaseUser, loading, router]);

  const handleGoogleSignIn = async () => {
    setError('');
    setSigningIn(true);
    try {
      await signInWithGoogle();
      router.push('/dashboard');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Sign-in failed. Please try again.');
    } finally {
      setSigningIn(false);
    }
  };

  if (loading) return null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 via-white to-amber-50 flex flex-col">
      <header className="px-6 py-4 flex items-center gap-2">
        <BookOpen className="w-6 h-6 text-teal-700" />
        <span className="font-heading font-bold text-teal-800 text-xl">HBSE Learn</span>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-4 text-center">
        <div className="max-w-2xl mx-auto space-y-6">
          <div className="inline-flex items-center gap-2 bg-teal-100 text-teal-700 text-sm font-medium px-3 py-1 rounded-full">
            <Zap className="w-3.5 h-3.5" />
            Class 9 · HBSE Curriculum
          </div>

          <h1 className="font-heading text-4xl sm:text-5xl font-bold text-stone-900 leading-tight">
            Learn smarter,<br />
            <span className="text-teal-600">not harder.</span>
          </h1>

          <p className="text-stone-600 text-lg max-w-md mx-auto">
            Adaptive practice questions, AI-powered hints, and a tutor that explains concepts — all tailored to your level.
          </p>

          <div className="flex flex-wrap justify-center gap-3 text-sm">
            {[
              { icon: TrendingUp, text: 'Tracks your mastery' },
              { icon: MessageCircle, text: 'AI Tutor chat' },
              { icon: Zap, text: 'Adaptive difficulty' },
            ].map(({ icon: Icon, text }) => (
              <span key={text} className="flex items-center gap-1.5 bg-white border border-stone-200 text-stone-700 px-3 py-1.5 rounded-full shadow-sm">
                <Icon className="w-3.5 h-3.5 text-teal-600" />
                {text}
              </span>
            ))}
          </div>

          <div className="bg-white rounded-2xl shadow-lg border border-stone-100 p-8 max-w-sm mx-auto space-y-4">
            <h2 className="font-heading font-semibold text-stone-800 text-lg">Get started</h2>

            <button
              onClick={handleGoogleSignIn}
              disabled={signingIn}
              className="w-full flex items-center justify-center gap-3 bg-white border border-stone-300 hover:border-teal-400 hover:bg-teal-50 text-stone-700 font-medium py-3 px-4 rounded-xl transition-all disabled:opacity-60 disabled:cursor-not-allowed shadow-sm"
            >
              {signingIn ? (
                <span className="w-5 h-5 border-2 border-stone-400 border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
              )}
              Continue with Google
            </button>

            {error && <p className="text-rose-600 text-sm text-center">{error}</p>}
            <p className="text-stone-400 text-xs text-center">For Class 9 HBSE students only</p>
          </div>
        </div>
      </main>

      <footer className="py-4 text-center text-stone-400 text-xs">
        © 2025 HBSE Adaptive Learning Platform
      </footer>
    </div>
  );
}
