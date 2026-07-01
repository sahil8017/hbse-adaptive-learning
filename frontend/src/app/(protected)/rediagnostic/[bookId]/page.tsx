'use client';

import { use, useState } from 'react';
import { useRouter } from 'next/navigation';
import { RefreshCcw } from 'lucide-react';
import { api } from '@/lib/api';

export default function ReDiagnosticPage({ params }: { params: Promise<{ bookId: string }> }) {
  const router = useRouter();
  const { bookId } = use(params);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  const handleRetest = async () => {
    setRunning(true);
    setError('');
    try {
      await api.post(`/diagnostic/retest/${bookId}`);
      setDone(true);
      setTimeout(() => router.push(`/subject/${bookId}`), 1500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start re-diagnostic');
      setRunning(false);
    }
  };

  return (
    <div className="max-w-md mx-auto text-center space-y-6 py-16">
      <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto">
        <RefreshCcw className="w-8 h-8 text-amber-600" />
      </div>

      <div>
        <h1 className="font-heading text-2xl font-bold text-stone-900">Re-assessment</h1>
        <p className="text-stone-600 mt-2 text-sm leading-relaxed">
          Your mastery in <strong className="capitalize">{bookId.replace(/_/g, ' ')}</strong> has dropped below 40%.
          We&apos;ll reset your difficulty to a comfortable level so you can rebuild.
        </p>
      </div>

      {done ? (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-emerald-700 font-medium">
          Done! Redirecting…
        </div>
      ) : (
        <>
          {error && <p className="text-rose-600 text-sm">{error}</p>}
          <button
            onClick={handleRetest}
            disabled={running || !bookId}
            className="bg-amber-500 hover:bg-amber-600 text-white font-semibold px-6 py-3 rounded-xl transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2 mx-auto"
          >
            {running ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <RefreshCcw className="w-4 h-4" />
            )}
            Start Re-assessment
          </button>
          <button onClick={() => router.back()} className="text-sm text-stone-500 hover:text-stone-700">
            Cancel
          </button>
        </>
      )}
    </div>
  );
}
