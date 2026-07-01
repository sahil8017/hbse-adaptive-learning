'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle2, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import type { Question } from '@/lib/types';
import { BasePageLoader } from '@/components/Loading';


export default function OnboardingPage() {
  const router = useRouter();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [current, setCurrent] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get<Question[]>('/diagnostic/questions')
      .then((qs) => { setQuestions(qs); setLoading(false); })
      .catch((e: Error) => { setError(e.message); setLoading(false); });
  }, []);

  const handleAnswer = (qId: number, idx: number) => {
    setAnswers((prev) => ({ ...prev, [qId]: idx }));
  };

  const handleNext = () => {
    if (current < questions.length - 1) setCurrent(current + 1);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await api.post('/diagnostic/submit', { answers });
      router.push('/dashboard');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Submission failed');
      setSubmitting(false);
    }
  };

  if (loading) return <BasePageLoader pageType="practice" />;


  if (!questions.length) return null;

  const q = questions[current];
  const answered = answers[q.id] !== undefined;
  const isLast = current === questions.length - 1;
  const allAnswered = questions.every((q) => answers[q.id] !== undefined);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <h1 className="font-heading text-2xl font-bold text-stone-900">Quick Assessment</h1>
        <p className="text-stone-500 text-sm">Answer {questions.length} questions so we can set the right difficulty level for you.</p>
      </div>

      {/* Progress */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-stone-500">
          <span>Question {current + 1} of {questions.length}</span>
          <span>{Object.keys(answers).length} answered</span>
        </div>
        <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
          <div className="h-full bg-teal-500 rounded-full transition-all" style={{ width: `${((current + 1) / questions.length) * 100}%` }} />
        </div>
      </div>

      {/* Question card */}
      <div className="bg-white rounded-2xl border border-stone-200 p-6 space-y-5">
        <div className="flex items-start gap-3">
          <span className="shrink-0 w-7 h-7 bg-teal-100 text-teal-700 rounded-full flex items-center justify-center text-sm font-bold">{current + 1}</span>
          <p className="text-stone-800 font-medium leading-relaxed">{q.text}</p>
        </div>

        <div className="space-y-2">
          {q.options?.map((opt, idx) => (
            <button
              key={idx}
              onClick={() => handleAnswer(q.id, idx)}
              className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-all ${
                answers[q.id] === idx
                  ? 'border-teal-500 bg-teal-50 text-teal-800 font-medium'
                  : 'border-stone-200 hover:border-stone-300 text-stone-700'
              }`}
            >
              <span className="font-mono mr-2 text-stone-400">{String.fromCharCode(65 + idx)}.</span>
              {opt}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-rose-600 text-sm">{error}</p>}

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setCurrent(Math.max(0, current - 1))}
          disabled={current === 0}
          className="text-sm text-stone-500 hover:text-stone-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ← Previous
        </button>

        <div className="flex gap-1">
          {questions.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrent(i)}
              className={`w-2 h-2 rounded-full transition-colors ${
                i === current ? 'bg-teal-600' : answers[questions[i].id] !== undefined ? 'bg-teal-200' : 'bg-stone-200'
              }`}
            />
          ))}
        </div>

        {isLast ? (
          <button
            onClick={handleSubmit}
            disabled={!allAnswered || submitting}
            className="flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold px-5 py-2.5 rounded-xl transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <CheckCircle2 className="w-4 h-4" />
            )}
            Submit
          </button>
        ) : (
          <button
            onClick={handleNext}
            disabled={!answered}
            className="flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold px-5 py-2.5 rounded-xl transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            Next <ChevronRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
