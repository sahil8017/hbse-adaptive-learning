'use client';

import { use, useEffect, useState } from 'react';
import { BookOpen, Award, Flame } from 'lucide-react';
import { apiPublicGet } from '@/lib/api';
import { masteryColor } from '@/lib/utils';
import type { ShareProgressData } from '@/lib/types';

export default function SharedProgressPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [data, setData] = useState<ShareProgressData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    apiPublicGet<ShareProgressData>(`/dashboard/view/${token}`)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [token]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50">
        <div className="text-center">
          <p className="text-rose-600 font-medium">Link expired or invalid</p>
          <p className="text-stone-500 text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const { student, subjects } = data;
  const totalBadges = student.unlocked_badges.length;

  return (
    <div className="min-h-screen bg-stone-50 py-10 px-4">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-white rounded-2xl p-6 border border-stone-200 text-center space-y-2">
          <div className="flex items-center justify-center gap-2 text-teal-700 font-heading font-bold text-xl">
            <BookOpen className="w-5 h-5" />
            HBSE Learn — Progress Report
          </div>
          <h1 className="text-2xl font-heading font-bold text-stone-900">{student.username}</h1>
          <div className="flex items-center justify-center gap-4 text-sm text-stone-600">
            <span className="flex items-center gap-1">
              <Flame className="w-4 h-4 text-amber-500" /> {student.streak_count} day streak
            </span>
            <span className="flex items-center gap-1">
              <Award className="w-4 h-4 text-amber-500" /> {totalBadges} badges
            </span>
          </div>
        </div>

        {/* Subjects */}
        {Object.entries(subjects).map(([bookId, subj]) => (
          <div key={bookId} className="bg-white rounded-2xl border border-stone-200 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-heading font-semibold text-stone-800">{bookId}</h2>
              <span className="text-sm text-stone-500">{Math.round(subj.avg_mastery)}% avg mastery</span>
            </div>
            <div className="space-y-2">
              {subj.chapters.map((ch) => (
                <div key={ch.chapter_id} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-stone-700 truncate">{ch.chapter_id}</span>
                    <span className="text-stone-500 ml-2 shrink-0">{Math.round(ch.mastery_percent)}%</span>
                  </div>
                  <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${masteryColor(ch.mastery_percent)}`}
                      style={{ width: `${ch.mastery_percent}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        <p className="text-center text-stone-400 text-xs">Read-only view · Shared by student</p>
      </div>
    </div>
  );
}
