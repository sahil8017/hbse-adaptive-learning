'use client';

import { use, useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  ChevronLeft, ChevronDown, CheckCircle2, Sparkles, Trophy,
} from 'lucide-react';
import { api, apiStream } from '@/lib/api';
import { tierLabel, tierColor, masteryColor } from '@/lib/utils';
import type { Question, PracticeSubmitResult } from '@/lib/types';
import MathText from '@/components/MathText';
import pdfMapData from '@/lib/pdf_page_mapping.json';

// ─── Data types ─────────────────────────────────────────────────────────────

interface CurriculumSection {
  id: string;
  title: string;
}

interface ChapterApiData {
  chapter: {
    id: string;
    title: string;
    sections: CurriculumSection[];
  };
  read_percent: number;
  mastery: {
    mastery_percent: number;
    current_tier: number;
    status: string;
    review_due_at?: string;
  };
  completed_sections: string[];
}

// Textbook file can use either format; we normalize to this
interface SectionContent {
  title: string;
  content: string;
  key_terms: string[];
}

function normalizeTextbook(raw: Record<string, unknown>): Map<string, SectionContent> {
  const map = new Map<string, SectionContent>();

  if (Array.isArray(raw.reading_nodes)) {
    for (const node of raw.reading_nodes as {
      node_id: string; node_title: string; content: string;
      inline_glossary?: Record<string, string>;
    }[]) {
      map.set(node.node_id, {
        title: node.node_title,
        content: node.content ?? '',
        key_terms: Object.keys(node.inline_glossary ?? {}),
      });
    }
  } else if (raw.sections && typeof raw.sections === 'object' && !Array.isArray(raw.sections)) {
    for (const [id, sec] of Object.entries(raw.sections as Record<string, { title: string; content: string; key_terms?: string[] }>)) {
      map.set(id, {
        title: sec.title ?? '',
        content: sec.content ?? '',
        key_terms: Array.isArray(sec.key_terms) ? sec.key_terms : [],
      });
    }
  }

  return map;
}

// ─── Bilingual helpers ───────────────────────────────────────────────────────

function hindiChapterTierLabel(tier: number) {
  if (tier === 1) return 'आसान -- Easy';
  if (tier === 2) return 'मध्यम -- Medium';
  return 'कठिन -- Hard';
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ChapterLearnPage({ params }: { params: Promise<{ bookId: string; chapterId: string }> }) {
  const { bookId, chapterId } = use(params);
  const [chapterData, setChapterData] = useState<ChapterApiData | null>(null);
  const [contentMap, setContentMap] = useState<Map<string, SectionContent>>(new Map());
  const [activeTab, setActiveTab] = useState<'read' | 'practice' | 'exam'>('read');
  const [loading, setLoading] = useState(true);

  const isHindi = bookId === 'Hindi';

  const reload = useCallback(async () => {
    try {
      const [ch, raw] = await Promise.all([
        api.get<ChapterApiData>(`/subject/${bookId}/chapter/${chapterId}`),
        api.get<Record<string, unknown>>(`/textbook/${bookId}/${chapterId}`).catch(() => ({})),
      ]);
      setChapterData(ch);
      const textMap = normalizeTextbook(raw);
      setContentMap(textMap);
      if (textMap.size === 0) {
        setActiveTab('practice');
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [bookId, chapterId]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { reload(); }, [reload]);

  const hasTextbook = contentMap.size > 0;
  const canAccessExam = !hasTextbook || (chapterData?.read_percent ?? 0) >= 100;
  const mastery = chapterData?.mastery;
  const sections = chapterData?.chapter?.sections ?? [];
  const completedSections = new Set(chapterData?.completed_sections ?? []);

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!chapterData) return (
    <div className="text-stone-500 py-10 text-center">
      {isHindi ? 'अध्याय नहीं मिला -- Chapter not found' : 'Chapter not found'}
    </div>
  );

  const tabLabel = (tab: 'read' | 'practice' | 'exam') => {
    if (tab === 'read') return isHindi ? 'पढ़ें -- Read' : 'Read';
    if (tab === 'practice') return isHindi ? 'अभ्यास -- Practice' : 'Practice';
    return isHindi ? 'बोर्ड परीक्षा -- Board Exam' : 'Board Exam';
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href={`/subject/${bookId}`} className="text-stone-500 hover:text-stone-700">
          <ChevronLeft className="w-5 h-5" />
        </Link>
        <div className="min-w-0">
          <h1 className="font-heading text-lg font-bold text-stone-900 truncate">{chapterData.chapter.title}</h1>
          {mastery && (
            <p className="text-stone-500 text-xs">
              {isHindi
                ? `स्तर -- Tier ${mastery.current_tier} (${hindiChapterTierLabel(mastery.current_tier)}) · महारत -- Mastery ${Math.round(mastery.mastery_percent)}% · पढ़ाई -- Read ${Math.round(chapterData.read_percent)}%`
                : `Tier ${mastery.current_tier} (${tierLabel(mastery.current_tier)}) · Mastery ${Math.round(mastery.mastery_percent)}% · Read ${Math.round(chapterData.read_percent)}%`
              }
            </p>
          )}
        </div>
      </div>

      {/* Mastery bar */}
      {mastery && (
        <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${masteryColor(mastery.mastery_percent)}`}
            style={{ width: `${mastery.mastery_percent}%` }}
          />
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-stone-200 overflow-x-auto">
        {(['read', 'practice', 'exam'] as const)
          .filter((tab) => tab !== 'read' || hasTextbook)
          .map((tab) => (
            <button
              key={tab}
              onClick={() => { if (tab === 'exam' && !canAccessExam) return; setActiveTab(tab); }}
              className={`px-3 sm:px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0 ${
                activeTab === tab
                  ? 'border-teal-600 text-teal-700'
                  : tab === 'exam' && !canAccessExam
                  ? 'border-transparent text-stone-300 cursor-not-allowed'
                  : 'border-transparent text-stone-500 hover:text-stone-700'
              }`}
            >
              {tabLabel(tab)}
              {tab === 'exam' && !canAccessExam && (
                <span className="hidden sm:inline ml-1 text-xs">
                  ({isHindi ? '100% पढ़ाई जरूरी' : '100% read required'})
                </span>
              )}
            </button>
          ))}
      </div>

      {activeTab === 'read' && (
        <SectionReaderPanel
          bookId={bookId}
          chapterId={chapterId}
          sections={sections}
          contentMap={contentMap}
          completedSections={completedSections}
          totalSections={sections.length}
          onProgressUpdate={reload}
          isHindi={isHindi}
        />
      )}
      {activeTab === 'practice' && (
        <PracticePanel
          bookId={bookId}
          chapterId={chapterId}
          mastery={mastery ?? null}
          onMasteryUpdate={reload}
          isHindi={isHindi}
        />
      )}
      {activeTab === 'exam' && canAccessExam && (
        <ExamPanel bookId={bookId} chapterId={chapterId} isHindi={isHindi} />
      )}
    </div>
  );
}

// ─── Section Reader ──────────────────────────────────────────────────────────

function SectionReaderPanel({
  bookId, chapterId, sections, contentMap, completedSections, totalSections, onProgressUpdate, isHindi,
}: {
  bookId: string; chapterId: string;
  sections: CurriculumSection[];
  contentMap: Map<string, SectionContent>;
  completedSections: Set<string>;
  totalSections: number;
  onProgressUpdate: () => void;
  isHindi: boolean;
}) {
  const [openSection, setOpenSection] = useState<string | null>(null);
  const [simplifyText, setSimplifyText] = useState<Record<string, string>>({});
  const [simplifying, setSimplifying] = useState<Record<string, boolean>>({});
  const [marking, setMarking] = useState<Record<string, boolean>>({});
  const [localRead, setLocalRead] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(sections.map((s) => [s.id, completedSections.has(s.id)]))
  );
  const [pdfPage, setPdfPage] = useState<number>(1);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const readCount = Object.values(localRead).filter(Boolean).length;

  // Load PDF mapping
  const pdfMap = pdfMapData as Record<string, Record<string, { pdf_url: string; pages: Record<string, number> }>>;
  const chapterPdf = pdfMap[bookId]?.[chapterId];
  const pdfUrl = chapterPdf?.pdf_url ?? null;

  const handleSectionClick = (sectionId: string) => {
    setOpenSection(openSection === sectionId ? null : sectionId);
    // Jump PDF to the section's page
    const page = chapterPdf?.pages?.[sectionId];
    if (page) setPdfPage(page);
  };

  const markRead = async (sectionId: string, read: boolean) => {
    setMarking((p) => ({ ...p, [sectionId]: true }));
    try {
      await api.post(`/subject/${bookId}/chapter/${chapterId}/read/${sectionId}`, { completed: read });
      setLocalRead((p) => ({ ...p, [sectionId]: read }));
      onProgressUpdate();
    } catch { /* ignore */ }
    setMarking((p) => ({ ...p, [sectionId]: false }));
  };

  const simplify = async (sectionId: string) => {
    if (simplifying[sectionId]) return;
    setSimplifying((p) => ({ ...p, [sectionId]: true }));
    setSimplifyText((p) => ({ ...p, [sectionId]: '' }));
    let text = '';
    try {
      for await (const chunk of apiStream(`/textbook/${bookId}/${chapterId}/${sectionId}/simplify`)) {
        if (chunk.text) { text += chunk.text; setSimplifyText((p) => ({ ...p, [sectionId]: text })); }
        if (chunk.done) break;
      }
    } catch {
      setSimplifyText((p) => ({ ...p, [sectionId]: 'Could not simplify. Please try again.' }));
    }
    setSimplifying((p) => ({ ...p, [sectionId]: false }));
  };

  const [mobileView, setMobileView] = useState<'sections' | 'book'>('sections');

  const AccordionPanel = (
    <div className="flex flex-col bg-white rounded-2xl border border-stone-200 overflow-hidden h-full">
      {/* Progress header */}
      <div className="px-3 py-2.5 bg-stone-50 border-b border-stone-100 shrink-0">
        <div className="flex justify-between text-xs text-stone-500 mb-1.5">
          <span>{readCount}/{totalSections} {isHindi ? 'पढ़े' : 'read'}</span>
          <span>{totalSections ? Math.round((readCount / totalSections) * 100) : 0}%</span>
        </div>
        <div className="h-1 bg-stone-200 rounded-full overflow-hidden">
          <div className="h-full bg-teal-500 rounded-full transition-all" style={{ width: `${totalSections ? (readCount / totalSections) * 100 : 0}%` }} />
        </div>
      </div>

      {/* Sections */}
      <div className="flex-1 overflow-y-auto">
        {sections.map((section) => {
          const isRead = localRead[section.id];
          const isOpen = openSection === section.id;
          const content = contentMap.get(section.id);

          return (
            <div key={section.id} className={`border-b border-stone-100 last:border-0 ${isRead ? 'bg-emerald-50/40' : ''}`}>
              <button
                onClick={() => handleSectionClick(section.id)}
                className={`w-full text-left px-3 py-3 sm:py-3 flex items-center gap-2 transition-colors ${isOpen ? 'bg-teal-50' : 'hover:bg-stone-50'}`}
              >
                <span className="shrink-0">
                  {isRead
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    : <div className="w-4 h-4 rounded-full border-2 border-stone-300" />}
                </span>
                <span className={`text-sm sm:text-xs font-medium leading-snug flex-1 ${isOpen ? 'text-teal-700' : 'text-stone-700'}`}>
                  {section.title}
                </span>
                <ChevronDown className={`w-4 h-4 shrink-0 text-stone-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
              </button>

              {isOpen && (
                <div className="px-4 pb-4 space-y-3 bg-white border-t border-teal-100">
                  <div className="pt-3">
                    {content?.content ? (
                      <p className="text-stone-700 text-sm leading-relaxed">
                        <MathText text={content.content} />
                      </p>
                    ) : (
                      <p className="text-stone-400 text-sm italic">
                        {isHindi ? 'सामग्री उपलब्ध नहीं' : 'Content not available.'}
                      </p>
                    )}
                  </div>

                  {content?.key_terms && content.key_terms.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {content.key_terms.map((term) => (
                        <span key={term} className="bg-teal-50 text-teal-700 text-xs px-2 py-0.5 rounded-full border border-teal-100">{term}</span>
                      ))}
                    </div>
                  )}

                  {simplifyText[section.id] && (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-900 leading-relaxed">
                      <p className="font-semibold text-amber-700 mb-1 text-xs">{isHindi ? 'सरलीकृत' : 'Simplified'}</p>
                      <MathText text={simplifyText[section.id]} />
                      {simplifying[section.id] && <span className="streaming-cursor" />}
                    </div>
                  )}

                  <div className="flex gap-2 flex-wrap pt-1">
                    <button
                      onClick={() => markRead(section.id, !isRead)}
                      disabled={marking[section.id]}
                      className={`flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg transition-colors disabled:opacity-60 ${
                        isRead ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200' : 'bg-teal-600 text-white hover:bg-teal-700'
                      }`}
                    >
                      {marking[section.id]
                        ? <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                        : <CheckCircle2 className="w-3 h-3" />}
                      {isRead ? (isHindi ? 'अपठित करें' : 'Mark unread') : (isHindi ? 'पढ़ा हुआ' : 'Mark as read')}
                    </button>
                    <button
                      onClick={() => simplify(section.id)}
                      disabled={simplifying[section.id]}
                      className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg border border-amber-300 text-amber-700 hover:bg-amber-50 transition-colors disabled:opacity-60"
                    >
                      <Sparkles className="w-3 h-3" />
                      {simplifying[section.id] ? (isHindi ? 'सरल हो रहा है…' : 'Simplifying…') : (isHindi ? 'AI से सरल करें' : 'Simplify with AI')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );

  const PdfPanel = (
    <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden flex flex-col h-full">
      {pdfUrl ? (
        <iframe
          ref={iframeRef}
          key={`${pdfUrl}#page=${pdfPage}`}
          src={`${pdfUrl}#page=${pdfPage}`}
          className="w-full flex-1 border-0"
          style={{ minHeight: '60vh' }}
          title="NCERT Textbook"
        />
      ) : (
        <div className="flex-1 flex items-center justify-center text-stone-400 text-sm p-8 text-center">
          {isHindi ? 'पुस्तक उपलब्ध नहीं' : 'Textbook PDF not available for this chapter.'}
        </div>
      )}
    </div>
  );

  return (
    <>
      {/* ── Mobile: toggle bar ─────────────────────────── */}
      <div className="flex lg:hidden bg-stone-100 rounded-xl p-1 gap-1 mb-2">
        <button
          onClick={() => setMobileView('sections')}
          className={`flex-1 flex items-center justify-center gap-1.5 text-sm font-medium py-2 rounded-lg transition-colors ${
            mobileView === 'sections' ? 'bg-white text-teal-700 shadow-sm' : 'text-stone-500'
          }`}
        >
          {isHindi ? 'अनुभाग' : 'Sections'}
        </button>
        <button
          onClick={() => setMobileView('book')}
          className={`flex-1 flex items-center justify-center gap-1.5 text-sm font-medium py-2 rounded-lg transition-colors ${
            mobileView === 'book' ? 'bg-white text-teal-700 shadow-sm' : 'text-stone-500'
          }`}
        >
          {isHindi ? 'पुस्तक' : 'Book'}
        </button>
      </div>

      {/* ── Mobile: single panel view ──────────────────── */}
      <div className="lg:hidden" style={{ height: 'calc(100vh - 280px)' }}>
        {mobileView === 'sections' ? AccordionPanel : PdfPanel}
      </div>

      {/* ── Desktop: side-by-side ─────────────────────── */}
      <div className="hidden lg:flex gap-3" style={{ height: 'calc(100vh - 240px)' }}>
        <div className="w-1/4 shrink-0">{AccordionPanel}</div>
        <div className="flex-1">{PdfPanel}</div>
      </div>
    </>
  );
}

// ─── Practice Panel ──────────────────────────────────────────────────────────

function PracticePanel({ bookId, chapterId, mastery, onMasteryUpdate, isHindi }: {
  bookId: string; chapterId: string;
  mastery: { mastery_percent: number; current_tier: number } | null;
  onMasteryUpdate: () => void;
  isHindi: boolean;
}) {
  const [question, setQuestion] = useState<Question | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [openAnswer, setOpenAnswer] = useState('');
  const [result, setResult] = useState<PracticeSubmitResult | null>(null);
  const [hintText, setHintText] = useState('');
  const [gettingHint, setGettingHint] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [loadingQ, setLoadingQ] = useState(true);
  const [noQuestions, setNoQuestions] = useState(false);

  const loadQuestion = useCallback(async () => {
    setLoadingQ(true);
    setResult(null); setSelected(null); setOpenAnswer(''); setHintText(''); setSubmitError(''); setNoQuestions(false);
    try {
      const res = await api.get<{ question: Question | null }>(`/subject/${bookId}/chapter/${chapterId}/practice`);
      const q = res.question ?? null;
      if (q) {
        // Backend uses question_type; normalise to type for our type system
        const raw = q as unknown as Record<string, unknown>;
        if (!q.type && raw.question_type) {
          q.type = raw.question_type as Question['type'];
        }
      }
      setQuestion(q);
      if (!q) setNoQuestions(true);
    } catch {
      setQuestion(null);
      setNoQuestions(true);
    }
    setLoadingQ(false);
  }, [bookId, chapterId]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { loadQuestion(); }, [loadQuestion]);

  const submitMcq = async () => {
    if (selected === null || !question || submitting) return;
    setSubmitting(true);
    setSubmitError('');
    try {
      const res = await api.post<PracticeSubmitResult>(`/subject/${bookId}/chapter/${chapterId}/practice/submit`, {
        question_id: question.id,
        user_answer: selected,
      });
      setResult(res);
      onMasteryUpdate();
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : 'Submit failed — please try again.');
    }
    setSubmitting(false);
  };

  const submitOpen = async () => {
    if (!openAnswer.trim() || !question || submitting) return;
    setSubmitting(true);
    setSubmitError('');
    try {
      const res = await api.post<PracticeSubmitResult>(`/subject/${bookId}/chapter/${chapterId}/practice/grade-open`, {
        question_id: question.id,
        user_answer: openAnswer,
      });
      setResult(res);
      onMasteryUpdate();
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : 'Submit failed — please try again.');
    }
    setSubmitting(false);
  };

  const getHint = async () => {
    if (!question || gettingHint) return;
    setGettingHint(true);
    setHintText('');
    let text = '';
    const studentAns = encodeURIComponent(openAnswer || String(selected ?? ''));
    try {
      for await (const chunk of apiStream(`/subject/${bookId}/chapter/${chapterId}/practice/stream?question_id=${question.id}&student_ans=${studentAns}`)) {
        if (chunk.text) { text += chunk.text; setHintText(text); }
        if (chunk.done) break;
      }
    } catch { setHintText('Could not get hint. Please try again.'); }
    setGettingHint(false);
  };

  if (loadingQ) return <div className="flex justify-center py-10"><div className="w-7 h-7 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>;
  if (noQuestions || !question) return (
    <div className="bg-white rounded-2xl border border-stone-200 p-8 text-center text-stone-500 text-sm">
      {isHindi
        ? 'इस अध्याय के लिए अभी कोई अभ्यास प्रश्न उपलब्ध नहीं -- No practice questions available for this chapter yet.'
        : 'No practice questions available for this chapter yet.'
      }
    </div>
  );

  return (
    <div className="bg-white rounded-2xl border border-stone-200 p-4 sm:p-5 space-y-4">
      {mastery && (
        <div className="flex items-center justify-between text-xs">
          <span className={`font-semibold ${tierColor(question.tier)}`}>
            {isHindi
              ? `स्तर -- Tier ${question.tier} · ${hindiChapterTierLabel(question.tier)}`
              : `Tier ${question.tier} · ${tierLabel(question.tier)}`
            }
          </span>
          <span className="text-stone-500">
            {isHindi ? `महारत -- Mastery: ${Math.round(mastery.mastery_percent)}%` : `Mastery: ${Math.round(mastery.mastery_percent)}%`}
          </span>
        </div>
      )}

      <p className="text-stone-800 font-medium leading-relaxed"><MathText text={question.text} /></p>

      {question.type === 'mcq' && question.options && (
        <div className="space-y-2">
          {question.options.map((opt, idx) => {
            const isSelected = selected === idx;
            const showWrong = result !== null && !result.is_correct && isSelected;
            const showSelected = !result && isSelected;
            return (
              <button
                key={idx}
                onClick={() => !result && setSelected(idx)}
                disabled={!!result}
                className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-all disabled:cursor-default ${
                  showWrong ? 'border-rose-400 bg-rose-50 text-rose-800' :
                  result && result.is_correct && isSelected ? 'border-emerald-500 bg-emerald-50 text-emerald-800' :
                  showSelected ? 'border-teal-500 bg-teal-50 text-teal-800' :
                  'border-stone-200 hover:border-stone-300 text-stone-700'
                }`}
              >
                <span className="font-mono mr-2 text-stone-400">{String.fromCharCode(65 + idx)}.</span><MathText text={opt} />
              </button>
            );
          })}
        </div>
      )}

      {question.type === 'open' && (
        <textarea
          value={openAnswer}
          onChange={(e) => setOpenAnswer(e.target.value)}
          disabled={!!result}
          placeholder={isHindi ? 'यहाँ उत्तर लिखें… -- Write your answer here…' : 'Write your answer here…'}
          rows={4}
          className="w-full px-4 py-3 border border-stone-300 rounded-xl text-sm resize-none focus:outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100 disabled:bg-stone-50"
        />
      )}

      {result && (
        <div className={`rounded-xl p-3 text-sm space-y-1 ${result.is_correct ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'}`}>
          <p className="font-medium">
            {result.is_correct
              ? (isHindi ? 'सही! -- Correct!' : 'Correct!')
              : (isHindi ? 'गलत -- Incorrect' : 'Incorrect')
            }
            {result.promoted && (
              <span className="ml-2">{isHindi ? 'स्तर बढ़ा! -- Tier up!' : 'Tier up!'}</span>
            )}
            <span className="ml-2 font-normal opacity-80">
              {isHindi ? `महारत -- Mastery: ${Math.round(result.mastery.mastery_percent)}%` : `Mastery: ${Math.round(result.mastery.mastery_percent)}%`}
            </span>
          </p>
          {result.feedback && <p className="text-xs opacity-90"><MathText text={result.feedback} /></p>}
        </div>
      )}

      {submitError && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-sm text-rose-700">
          {submitError}
        </div>
      )}

      {hintText && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-900 leading-relaxed">
          <p className="text-xs font-semibold text-amber-700 mb-1">
            {isHindi ? 'संकेत -- Hint' : 'Hint'}
          </p>
          <MathText text={hintText} />
          {gettingHint && <span className="streaming-cursor" />}
        </div>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        {!result ? (
          <>
            <button
              onClick={question.type === 'mcq' ? submitMcq : submitOpen}
              disabled={submitting || (question.type === 'mcq' ? selected === null : !openAnswer.trim())}
              className="flex items-center gap-1.5 bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold px-4 py-2 rounded-xl transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {submitting && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
              {isHindi ? 'जमा करें -- Submit' : 'Submit'}
            </button>
            <button
              onClick={getHint}
              disabled={gettingHint}
              className="flex items-center gap-1.5 border border-amber-300 text-amber-700 hover:bg-amber-50 text-sm px-4 py-2 rounded-xl transition-colors disabled:opacity-60"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {gettingHint
                ? (isHindi ? 'संकेत मिल रहा है… -- Getting hint…' : 'Getting hint…')
                : (isHindi ? 'संकेत लें -- Get hint' : 'Get hint')
              }
            </button>
          </>
        ) : (
          <button onClick={loadQuestion} className="bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold px-4 py-2 rounded-xl transition-colors">
            {isHindi ? 'अगला प्रश्न -- Next question →' : 'Next question →'}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Exam Panel ──────────────────────────────────────────────────────────────

interface ExamQ {
  id: number;
  text: string;
  options?: string[];
  type: 'mcq' | 'short' | 'long';
  marks: number;
}

function ExamPanel({ bookId, chapterId, isHindi }: { bookId: string; chapterId: string; isHindi: boolean }) {
  const [questions, setQuestions] = useState<ExamQ[]>([]);
  const [examToken, setExamToken] = useState('');
  const [answers, setAnswers] = useState<Record<number, number | string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [score, setScore] = useState<number | null>(null);
  const [passed, setPassed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get<{ questions: ExamQ[]; token: string }>(`/subject/${bookId}/chapter/${chapterId}/exam/questions`)
      .then((res) => { setQuestions(res.questions); setExamToken(res.token); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [bookId, chapterId]);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const res = await api.post<{ score_percent: number; passed: boolean }>(
        `/subject/${bookId}/chapter/${chapterId}/exam/submit`,
        { answers, exam_token: examToken },
      );
      setScore(res.score_percent);
      setPassed(res.passed);
      setSubmitted(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Submission failed');
    }
    setSubmitting(false);
  };

  if (loading) return <div className="flex justify-center py-10"><div className="w-7 h-7 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-rose-700 text-sm">{error}</div>;

  if (submitted && score !== null) return (
    <div className="text-center py-10 space-y-4">
      <Trophy className={`w-12 h-12 mx-auto ${passed ? 'text-amber-400' : 'text-stone-400'}`} />
      <h2 className="font-heading text-xl font-bold">
        {passed
          ? (isHindi ? 'उत्तीर्ण! -- Passed!' : 'Passed!')
          : (isHindi ? 'अभी नहीं… -- Not quite…' : 'Not quite…')
        }
      </h2>
      <p className="text-stone-600">
        {isHindi ? 'अंक -- Score: ' : 'Score: '}
        <span className="font-bold text-stone-900">{Math.round(score)}%</span>
      </p>
      <p className="text-sm text-stone-500">
        {passed
          ? (isHindi ? 'शानदार! -- Excellent work!' : 'Excellent work!')
          : (isHindi ? 'अभ्यास करते रहें -- Keep practising and try again.' : 'Keep practising and try again.')
        }
      </p>
    </div>
  );

  const allAnswered = questions.length > 0 && questions.every((q) => answers[q.id] !== undefined);

  return (
    <div className="space-y-4">
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
        {isHindi
          ? `बोर्ड परीक्षा मोड -- Board Exam Mode · ${questions.length} प्रश्न -- questions · उत्तीर्ण अंक -- Pass mark: 80%`
          : `Board Exam Mode · ${questions.length} questions · Pass mark: 80%`
        }
      </div>
      {questions.length > 0 && (
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-3 text-sm text-stone-700 mb-4">
          Total Marks: {questions.reduce((s, q) => s + q.marks, 0)} | Pass: 80% | Section A: MCQ (1m) | Section B: Short (2m) | Section C: Long (5m)
        </div>
      )}

      {questions.length > 0 && questions.some(q => q.type === 'mcq') && (
        <div className="space-y-3">
          <h3 className="font-heading font-semibold text-stone-900 text-lg">{isHindi ? 'अनुभाग A -- Section A: Multiple Choice (1 mark each)' : 'Section A: Multiple Choice (1 mark each)'}</h3>
          {questions.filter(q => q.type === 'mcq').map((q, idx) => (
            <div key={q.id} className="bg-white rounded-2xl border border-stone-200 p-4 space-y-2">
              <p className="font-medium text-stone-800"><span className="text-teal-600 font-bold">Q{idx + 1}</span>. <MathText text={q.text} /></p>
              <div className="space-y-2 ml-2">
                {q.options?.map((opt, i) => (
                  <button
                    key={i}
                    onClick={() => !submitted && setAnswers(p => ({ ...p, [q.id]: i }))}
                    disabled={submitted}
                    className={`w-full text-left px-3 py-2.5 rounded-lg border transition-all ${
                      answers[q.id] === i
                        ? 'border-teal-500 bg-teal-50 text-teal-800'
                        : 'border-stone-200 hover:border-stone-300 text-stone-700'
                    } disabled:cursor-default`}
                  >
                    <span className="font-mono text-stone-400 mr-2">{String.fromCharCode(65 + i)}.</span><MathText text={opt} />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {questions.length > 0 && questions.some(q => q.type === 'short') && (
        <div className="space-y-3">
          <h3 className="font-heading font-semibold text-stone-900 text-lg">{isHindi ? 'अनुभाग B -- Section B: Short Answer (2 marks each)' : 'Section B: Short Answer (2 marks each)'}</h3>
          {questions.filter(q => q.type === 'short').map((q, idx) => (
            <div key={q.id} className="bg-white rounded-2xl border border-stone-200 p-4 space-y-2">
              <p className="font-medium text-stone-800"><span className="text-teal-600 font-bold">Q{questions.filter(qq => qq.type === 'mcq').length + idx + 1}</span>. <MathText text={q.text} /></p>
              <textarea
                value={(answers[q.id] as string) || ''}
                onChange={(e) => !submitted && setAnswers(p => ({ ...p, [q.id]: e.target.value }))}
                disabled={submitted}
                placeholder={isHindi ? 'उत्तर यहाँ लिखें -- Write your answer here...' : 'Write your answer here...'}
                rows={3}
                className="w-full px-3 py-2 border border-stone-300 rounded-lg text-sm resize-none focus:outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100 disabled:bg-stone-50"
              />
            </div>
          ))}
        </div>
      )}

      {questions.length > 0 && questions.some(q => q.type === 'long') && (
        <div className="space-y-3">
          <h3 className="font-heading font-semibold text-stone-900 text-lg">{isHindi ? 'अनुभाग C -- Section C: Long Answer (5 marks each)' : 'Section C: Long Answer (5 marks each)'}</h3>
          {questions.filter(q => q.type === 'long').map((q, idx) => {
            const mcqCount = questions.filter(qq => qq.type === 'mcq').length;
            const shortCount = questions.filter(qq => qq.type === 'short').length;
            return (
              <div key={q.id} className="bg-white rounded-2xl border border-stone-200 p-4 space-y-2">
                <p className="font-medium text-stone-800"><span className="text-teal-600 font-bold">Q{mcqCount + shortCount + idx + 1}</span>. <MathText text={q.text} /></p>
                <textarea
                  value={(answers[q.id] as string) || ''}
                  onChange={(e) => !submitted && setAnswers(p => ({ ...p, [q.id]: e.target.value }))}
                  disabled={submitted}
                  placeholder={isHindi ? 'विस्तृत उत्तर यहाँ लिखें -- Write your detailed answer here...' : 'Write your detailed answer here...'}
                  rows={4}
                  className="w-full px-3 py-2 border border-stone-300 rounded-lg text-sm resize-none focus:outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100 disabled:bg-stone-50"
                />
              </div>
            );
          })}
        </div>
      )}
      <button
        onClick={handleSubmit}
        disabled={!allAnswered || submitting}
        className="w-full bg-amber-500 hover:bg-amber-600 text-white font-semibold py-3 rounded-xl transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {submitting ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Trophy className="w-4 h-4" />}
        {isHindi ? 'परीक्षा जमा करें -- Submit Exam' : 'Submit Exam'}
      </button>
    </div>
  );
}
