'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Users, AlertTriangle, BarChart2, Database, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import type { AdminStudent, MasteryDistribution } from '@/lib/types';

interface Anomaly {
  id: number;
  student_id: number;
  anomaly_type: string;
  book_id?: string;
  chapter_id?: string;
  timestamp: string;
}

export default function AdminDashboardPage() {
  const [students, setStudents] = useState<AdminStudent[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [distribution, setDistribution] = useState<MasteryDistribution[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<AdminStudent[]>('/admin/students').catch(() => []),
      api.get<Anomaly[]>('/admin/anomalies').catch(() => []),
      api.get<MasteryDistribution[]>('/admin/mastery-distribution').catch(() => []),
    ]).then(([s, a, d]) => {
      setStudents(s);
      setAnomalies(a);
      setDistribution(d);
      setLoading(false);
    });
  }, []);

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-2xl font-bold text-stone-900">Admin Dashboard</h1>
        <Link
          href="/admin/questions"
          className="flex items-center gap-2 text-sm bg-teal-600 hover:bg-teal-700 text-white font-medium px-4 py-2 rounded-xl transition-colors"
        >
          <Database className="w-4 h-4" />
          Question Bank
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <StatCard icon={Users} label="Total Students" value={students.length} color="teal" />
        <StatCard icon={AlertTriangle} label="Recent Anomalies" value={anomalies.length} color="amber" />
        <StatCard icon={BarChart2} label="Subjects Tracked" value={distribution.length} color="blue" />
      </div>

      {/* Mastery distribution */}
      {distribution.length > 0 && (
        <div className="bg-white rounded-2xl border border-stone-200 p-5 space-y-4">
          <h2 className="font-heading font-semibold text-stone-800">Mastery Distribution by Subject</h2>
          <div className="space-y-4">
            {distribution.map((d) => (
              <div key={d.book_id} className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="font-medium text-stone-700">{d.book_id}</span>
                  <span className="text-stone-500">Avg {Math.round(d.avg_mastery)}%</span>
                </div>
                <div className="flex gap-1 h-3 rounded-full overflow-hidden">
                  {[
                    { count: d.tier_1_count, cls: 'bg-emerald-400' },
                    { count: d.tier_2_count, cls: 'bg-amber-400' },
                    { count: d.tier_3_count, cls: 'bg-rose-400' },
                  ].map(({ count, cls }) => {
                    const total = d.tier_1_count + d.tier_2_count + d.tier_3_count;
                    const pct = total ? (count / total) * 100 : 0;
                    return <div key={cls} className={`${cls}`} style={{ width: `${pct}%` }} />;
                  })}
                </div>
                <div className="flex gap-4 text-xs text-stone-500">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-400 rounded-full" />Tier 1: {d.tier_1_count}</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 bg-amber-400 rounded-full" />Tier 2: {d.tier_2_count}</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 bg-rose-400 rounded-full" />Tier 3: {d.tier_3_count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Anomaly feed */}
      {anomalies.length > 0 && (
        <div className="bg-white rounded-2xl border border-stone-200 p-5 space-y-3">
          <h2 className="font-heading font-semibold text-stone-800 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" /> Recent Anomalies
          </h2>
          <div className="divide-y divide-stone-100">
            {anomalies.slice(0, 20).map((a) => (
              <div key={a.id} className="py-2 flex items-center justify-between text-sm">
                <div>
                  <span className="font-medium text-stone-700">Student #{a.student_id}</span>
                  <span className="text-stone-500 mx-2">·</span>
                  <span className="text-amber-600">{a.anomaly_type.replace(/_/g, ' ')}</span>
                  {a.book_id && <span className="text-stone-400 ml-2 text-xs">{a.book_id}</span>}
                </div>
                <span className="text-stone-400 text-xs">{formatDate(a.timestamp)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Student table */}
      <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden">
        <div className="p-5 border-b border-stone-100">
          <h2 className="font-heading font-semibold text-stone-800 flex items-center gap-2">
            <Users className="w-4 h-4 text-teal-600" /> Students
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-stone-50 text-left text-stone-500 text-xs">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Streak</th>
                <th className="px-4 py-3 font-medium">Last Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {students.map((s) => (
                <tr key={s.id} className="hover:bg-stone-50">
                  <td className="px-4 py-3 font-medium text-stone-800">{s.display_name}</td>
                  <td className="px-4 py-3 text-stone-500">{s.email}</td>
                  <td className="px-4 py-3 text-amber-600 font-semibold">{s.streak_count} days</td>
                  <td className="px-4 py-3 text-stone-500">{formatDate(s.last_active_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }: { icon: React.ComponentType<{ className?: string }>; label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    teal: 'bg-teal-50 text-teal-600',
    amber: 'bg-amber-50 text-amber-600',
    blue: 'bg-blue-50 text-blue-600',
  };
  return (
    <div className="bg-white rounded-2xl border border-stone-200 p-4 flex items-center gap-3">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${colors[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-heading font-bold text-stone-900">{value}</p>
        <p className="text-xs text-stone-500">{label}</p>
      </div>
    </div>
  );
}
