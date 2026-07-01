'use client';

import { useEffect, useState } from 'react';
import { ChevronLeft, Plus, Pencil, Trash2, X, Save } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { tierLabel } from '@/lib/utils';
import type { AdminQuestion } from '@/lib/types';

const EMPTY_Q: Partial<AdminQuestion> = { tier: 1, type: 'mcq', options: ['', '', '', ''], correct_answer: 0 };

export default function QuestionBankPage() {
  const [questions, setQuestions] = useState<AdminQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Partial<AdminQuestion> | null>(null);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState({ bookId: '', tier: '' });

  const load = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filter.bookId) params.set('book_id', filter.bookId);
    if (filter.tier) params.set('tier', filter.tier);
    try {
      const qs = await api.get<AdminQuestion[]>(`/admin/questions?${params}`);
      setQuestions(qs);
    } catch { /* ignore */ }
    setLoading(false);
  };

  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [filter]);

  const save = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      if (editing.id) {
        await api.put(`/admin/questions/${editing.id}`, editing);
      } else {
        await api.post('/admin/questions', editing);
      }
      setEditing(null);
      await load();
    } catch { /* ignore */ }
    setSaving(false);
  };

  const del = async (id: number) => {
    if (!confirm('Delete this question?')) return;
    try { await api.del(`/admin/questions/${id}`); await load(); } catch { /* ignore */ }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Link href="/admin" className="text-stone-500 hover:text-stone-700"><ChevronLeft className="w-5 h-5" /></Link>
        <h1 className="font-heading text-xl font-bold text-stone-900">Question Bank</h1>
        <button
          onClick={() => setEditing({ ...EMPTY_Q })}
          className="ml-auto flex items-center gap-1.5 bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium px-3 py-2 rounded-xl transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Question
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <input
          value={filter.bookId}
          onChange={(e) => setFilter((p) => ({ ...p, bookId: e.target.value }))}
          placeholder="Subject (e.g. Mathematics)"
          className="px-3 py-2 text-sm border border-stone-300 rounded-xl focus:outline-none focus:border-teal-400 w-52"
        />
        <select
          value={filter.tier}
          onChange={(e) => setFilter((p) => ({ ...p, tier: e.target.value }))}
          className="px-3 py-2 text-sm border border-stone-300 rounded-xl focus:outline-none focus:border-teal-400"
        >
          <option value="">All tiers</option>
          <option value="1">Tier 1 — Easy</option>
          <option value="2">Tier 2 — Medium</option>
          <option value="3">Tier 3 — Hard</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-10"><div className="w-7 h-7 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : (
        <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-stone-50 text-left text-xs text-stone-500">
                <th className="px-4 py-3 font-medium">Question</th>
                <th className="px-4 py-3 font-medium">Subject</th>
                <th className="px-4 py-3 font-medium">Tier</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {questions.map((q) => (
                <tr key={q.id} className="hover:bg-stone-50">
                  <td className="px-4 py-3 text-stone-700 max-w-xs truncate">{q.text}</td>
                  <td className="px-4 py-3 text-stone-500 text-xs">{q.book_id}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${q.tier === 1 ? 'text-emerald-600' : q.tier === 2 ? 'text-amber-600' : 'text-rose-600'}`}>
                      T{q.tier} {tierLabel(q.tier)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-stone-500 text-xs capitalize">{q.type}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button onClick={() => setEditing({ ...q })} className="text-stone-400 hover:text-teal-600 transition-colors">
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button onClick={() => del(q.id)} className="text-stone-400 hover:text-rose-600 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {questions.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-stone-400">No questions found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit / Create dialog */}
      {editing && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-stone-100 px-5 py-4 flex items-center justify-between">
              <h3 className="font-heading font-semibold text-stone-900">{editing.id ? 'Edit Question' : 'New Question'}</h3>
              <button onClick={() => setEditing(null)} className="text-stone-400 hover:text-stone-600"><X className="w-5 h-5" /></button>
            </div>

            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Subject" value={editing.book_id || ''} onChange={(v) => setEditing((p) => ({ ...p, book_id: v }))} placeholder="Mathematics" />
                <Field label="Chapter ID" value={editing.chapter_id || ''} onChange={(v) => setEditing((p) => ({ ...p, chapter_id: v }))} placeholder="ch1" />
              </div>

              <div>
                <label className="block text-xs font-medium text-stone-600 mb-1">Question text</label>
                <textarea
                  value={editing.text || ''}
                  onChange={(e) => setEditing((p) => ({ ...p, text: e.target.value }))}
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-xl focus:outline-none focus:border-teal-400 resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">Tier</label>
                  <select
                    value={editing.tier || 1}
                    onChange={(e) => setEditing((p) => ({ ...p, tier: Number(e.target.value) as 1|2|3 }))}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-xl focus:outline-none focus:border-teal-400"
                  >
                    <option value={1}>1 — Easy</option>
                    <option value={2}>2 — Medium</option>
                    <option value={3}>3 — Hard</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">Type</label>
                  <select
                    value={editing.type || 'mcq'}
                    onChange={(e) => setEditing((p) => ({ ...p, type: e.target.value as 'mcq'|'open' }))}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-xl focus:outline-none focus:border-teal-400"
                  >
                    <option value="mcq">MCQ</option>
                    <option value="open">Open-ended</option>
                  </select>
                </div>
              </div>

              {editing.type === 'mcq' && (
                <div className="space-y-2">
                  <label className="block text-xs font-medium text-stone-600">Options (click correct answer radio)</label>
                  {(editing.options || ['', '', '', '']).map((opt, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="correct"
                        checked={editing.correct_answer === i}
                        onChange={() => setEditing((p) => ({ ...p, correct_answer: i }))}
                        className="accent-teal-600"
                      />
                      <input
                        value={opt}
                        onChange={(e) => {
                          const opts = [...(editing.options || ['', '', '', ''])];
                          opts[i] = e.target.value;
                          setEditing((p) => ({ ...p, options: opts }));
                        }}
                        placeholder={`Option ${String.fromCharCode(65 + i)}`}
                        className="flex-1 px-3 py-2 text-sm border border-stone-300 rounded-xl focus:outline-none focus:border-teal-400"
                      />
                    </div>
                  ))}
                </div>
              )}

              <Field label="Subtopic (optional)" value={editing.subtopic || ''} onChange={(v) => setEditing((p) => ({ ...p, subtopic: v }))} />
            </div>

            <div className="sticky bottom-0 bg-white border-t border-stone-100 px-5 py-4 flex gap-2 justify-end">
              <button onClick={() => setEditing(null)} className="px-4 py-2 text-sm text-stone-600 border border-stone-300 rounded-xl hover:bg-stone-50">Cancel</button>
              <button
                onClick={save}
                disabled={saving}
                className="flex items-center gap-1.5 px-4 py-2 text-sm bg-teal-600 hover:bg-teal-700 text-white font-medium rounded-xl disabled:opacity-60"
              >
                {saving ? <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="block text-xs font-medium text-stone-600 mb-1">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm border border-stone-300 rounded-xl focus:outline-none focus:border-teal-400"
      />
    </div>
  );
}
