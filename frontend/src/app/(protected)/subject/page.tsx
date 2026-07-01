'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import { masteryColor } from '@/lib/utils';
import { BasePageLoader } from '@/components/Loading';
import type { DashboardData, SubjectSummary } from '@/lib/types';


export default function SubjectsPage() {
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<DashboardData>('/dashboard')
      .then((d) => { setSubjects(d.subjects); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <BasePageLoader pageType="default" />;


  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h1 className="font-heading text-2xl font-bold text-stone-900">Subjects</h1>
      <div className="space-y-3">
        {subjects.map((subj) => (
          <Link
            key={subj.book_id}
            href={`/subject/${subj.book_id}`}
            className="flex items-center justify-between bg-white rounded-2xl border border-stone-200 hover:border-teal-300 hover:shadow-sm p-5 transition-all group"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 bg-teal-100 rounded-xl flex items-center justify-center shrink-0">
                <BookOpen className="w-5 h-5 text-teal-700" />
              </div>
              <div className="min-w-0">
                <p className="font-heading font-semibold text-stone-900">{subj.book_id.replace(/_/g, ' ')}</p>
                <p className="text-sm text-stone-500">{subj.total_chapters} chapters · {Math.round(subj.mastery_percent)}% mastery</p>
                <div className="mt-1.5 h-1 w-32 bg-stone-100 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${masteryColor(subj.mastery_percent)}`} style={{ width: `${subj.mastery_percent}%` }} />
                </div>
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-stone-400 group-hover:text-teal-600 transition-colors shrink-0 ml-3" />
          </Link>
        ))}
      </div>
    </div>
  );
}
