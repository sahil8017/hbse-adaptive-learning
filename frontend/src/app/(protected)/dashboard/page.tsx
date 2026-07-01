'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { Flame, Award, Download, Upload, Share2, AlertCircle, ChevronRight, BookOpen } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { useBadgeUnlock } from '@/context/BadgeUnlockContext';
import { formatDate } from '@/lib/utils';
import type { DashboardData, SubjectSummary } from '@/lib/types';
import { BasePageLoader } from '@/components/Loading';
import type { UnlockableBadge } from '@/context/BadgeUnlockContext';


export default function DashboardPage() {
  const { student } = useAuth();
  const { triggerBadgeUnlocks } = useBadgeUnlock();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [shareLink, setShareLink] = useState('');
  const [sharing, setSharing] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await api.get<DashboardData>('/dashboard');
      setData(d);
      // Check for any newly earned badges (e.g. streak badges)
      const res = await api.post<{ new_badges: UnlockableBadge[] }>('/badges/check', {});
      if (res.new_badges?.length) {
        triggerBadgeUnlocks(res.new_badges);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [triggerBadgeUnlocks]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, [load]);

  const handleExport = async () => {
    try {
      const { firebaseAuth } = await import('@/lib/firebase');
      const token = await firebaseAuth().currentUser?.getIdToken();
      const BASE = process.env.NEXT_PUBLIC_API_URL !== undefined ? process.env.NEXT_PUBLIC_API_URL : '';
      const blob = await fetch(`${BASE}/api/dashboard/export`, { headers: { Authorization: `Bearer ${token}` } });
      const url = URL.createObjectURL(await blob.blob());
      const a = document.createElement('a'); a.href = url; a.download = 'progress.json'; a.click();
    } catch { /* ignore */ }
  };

  const handleShare = async () => {
    setSharing(true);
    try {
      const res = await api.post<{ share_url: string }>('/dashboard/share-link');
      setShareLink(res.share_url || '');
      if (res.share_url) navigator.clipboard?.writeText(res.share_url);
    } catch { /* ignore */ }
    setSharing(false);
  };

  if (loading) return <BasePageLoader pageType="dashboard" />;


  if (error) return (
    <div className="flex items-center gap-2 text-rose-600 py-10">
      <AlertCircle className="w-5 h-5" />{error}
    </div>
  );

  const focusAreas = student?.focus_areas ?? [];
  const badges = student?.unlocked_badges ?? [];

  return (
    <div className="space-y-6">
      {/* Top bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-xl sm:text-2xl font-bold text-stone-900">
            Welcome back, {student?.display_name?.split(' ')[0] || 'Student'}
          </h1>
          <p className="text-stone-500 text-sm mt-0.5">{formatDate(student?.last_active_date)} · {student?.board} · {student?.class_grade}</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1.5 rounded-full text-sm font-semibold">
            <Flame className="w-4 h-4" />
            {student?.streak_count ?? 0} day streak
          </div>
          <div className="flex items-center gap-1.5 bg-teal-50 border border-teal-200 text-teal-700 px-3 py-1.5 rounded-full text-sm font-semibold">
            <Award className="w-4 h-4" />
            {badges.length} badges
          </div>
        </div>
      </div>

      {/* Focus areas */}
      {focusAreas.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-amber-800 font-medium text-sm mb-2">Focus Areas — spend more time on these</p>
          <div className="flex flex-wrap gap-2">
            {focusAreas.map((area) => (
              <span key={area} className="bg-amber-100 text-amber-700 text-xs px-2 py-1 rounded-full">{area}</span>
            ))}
          </div>
        </div>
      )}

      {/* Subjects */}
      <div className="space-y-4">
        {data?.subjects.map((subj) => (
          <SubjectCard key={subj.book_id} subject={subj} />
        ))}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3 pt-2">
        <button onClick={handleExport} className="flex items-center gap-2 text-sm text-stone-600 border border-stone-300 hover:border-stone-400 px-3 py-2 rounded-lg transition-colors">
          <Download className="w-4 h-4" /> Export progress
        </button>
        <button onClick={handleShare} disabled={sharing} className="flex items-center gap-2 text-sm text-teal-700 border border-teal-300 hover:bg-teal-50 px-3 py-2 rounded-lg transition-colors">
          <Share2 className="w-4 h-4" /> {sharing ? 'Generating…' : 'Share with parent'}
        </button>
        <label className="flex items-center gap-2 text-sm text-stone-600 border border-stone-300 hover:border-stone-400 px-3 py-2 rounded-lg cursor-pointer transition-colors">
          <Upload className="w-4 h-4" /> Import progress
          <input type="file" accept=".json" className="hidden" onChange={async (e) => {
            const file = e.target.files?.[0]; if (!file) return;
            const text = await file.text();
            try { await api.post('/dashboard/import', JSON.parse(text)); window.location.reload(); } catch { /* ignore */ }
          }} />
        </label>
      </div>

      {shareLink && (
        <div className="bg-teal-50 border border-teal-200 rounded-xl p-3 text-sm text-teal-800">
          <p className="font-medium">Share link copied! Valid for 7 days.</p>
          <p className="text-xs text-teal-600 mt-0.5 break-all">{shareLink}</p>
        </div>
      )}
    </div>
  );
}

function SubjectCard({ subject }: { subject: SubjectSummary }) {
  const { book_id, total_chapters, completed_chapters, review_due } = subject;
  const displayName = book_id.replace(/_/g, ' ');
  const completePct = total_chapters > 0 ? Math.round((completed_chapters / total_chapters) * 100) : 0;

  return (
    <div className="bg-white rounded-2xl border border-stone-200 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-teal-600" />
          <h2 className="font-heading font-semibold text-stone-900">{displayName}</h2>
        </div>
        <div className="flex items-center gap-2">
          {review_due && <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">Review due</span>}
          <Link
            href={`/subject/${book_id}`}
            className="flex items-center gap-1 text-sm text-teal-600 hover:text-teal-700 font-medium transition-colors"
          >
            View chapters <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-stone-500 mb-1">
        <span>{completed_chapters}/{total_chapters} chapters complete</span>
        <span>{completePct}%</span>
      </div>
      <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
        <div className="h-full bg-teal-500 rounded-full transition-all" style={{ width: `${completePct}%` }} />
      </div>
    </div>
  );
}
