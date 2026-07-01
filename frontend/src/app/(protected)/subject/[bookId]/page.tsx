'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { ChevronLeft, Lock, CheckCircle2, ChevronRight, AlertCircle, BookOpen, BookOpenCheck, FlaskConical, Trophy } from 'lucide-react';
import { api } from '@/lib/api';
import { statusBadgeClass } from '@/lib/utils';
import { BasePageLoader } from '@/components/Loading';
import type { ChapterMastery } from '@/lib/types';


const HINDI_BOOKS = [
  {
    key: 'Kshitij',
    nameHindi: 'क्षितिज',
    nameLatin: 'Kshitij',
    descHindi: 'गद्य और पद्य',
    descEnglish: 'Prose & Poetry',
    match: (sub?: string) => !!sub?.startsWith('Kshitij'),
  },
  {
    key: 'Kritika',
    nameHindi: 'कृतिका',
    nameLatin: 'Kritika',
    descHindi: 'पूरक पाठ्यपुस्तक',
    descEnglish: 'Supplementary Reader',
    match: (sub?: string) => sub === 'Kritika',
  },
  {
    key: 'Vyakaran',
    nameHindi: 'व्याकरण',
    nameLatin: 'Vyakaran',
    descHindi: 'व्याकरण और व्यावहारिक भाषा',
    descEnglish: 'Grammar & Language Practice',
    match: (sub?: string) => sub === 'Vyakaran',
  },
  {
    key: 'Essay',
    nameHindi: 'रचनात्मक लेखन',
    nameLatin: 'Essay & Letters',
    descHindi: 'निबंध, पत्र एवं लेखक-परिचय',
    descEnglish: 'Essay, Letters & Author Info',
    match: (sub?: string) => sub === 'Essay',
  },
];

const ENGLISH_BOOKS = [
  {
    key: 'Beehive',
    nameHindi: 'Beehive',
    nameLatin: 'Beehive',
    descHindi: 'Literature Reader (Prose & Poetry)',
    descEnglish: 'Literature Reader (Prose & Poetry)',
    match: (sub?: string) => !!sub?.startsWith('Beehive'),
  },
  {
    key: 'Moments',
    nameHindi: 'Moments',
    nameLatin: 'Moments',
    descHindi: 'Supplementary Reader stories',
    descEnglish: 'Supplementary Reader stories',
    match: (sub?: string) => sub === 'Moments',
  },
  {
    key: 'Grammar',
    nameHindi: 'Grammar',
    nameLatin: 'Grammar',
    descHindi: 'English Grammar & Usage',
    descEnglish: 'English Grammar & Usage',
    match: (sub?: string) => sub === 'Grammar',
  },
  {
    key: 'Writing_Skills',
    nameHindi: 'Writing & Reading Skills',
    nameLatin: 'Writing & Reading Skills',
    descHindi: 'Unseen Comprehension & Composition',
    descEnglish: 'Unseen Comprehension & Composition',
    match: (sub?: string) => sub === 'Writing_Skills',
  },
];

// Sub-category display labels for Kshitij and English sections
const SUB_CAT_LABELS: Record<string, { hindi: string; english: string }> = {
  'Kshitij - Prose': { hindi: 'क्षितिज - गद्य', english: 'Kshitij - Prose' },
  'Kshitij - Poetry': { hindi: 'क्षितिज - पद्य', english: 'Kshitij - Poetry' },
  'Kritika': { hindi: 'कृतिका', english: 'Kritika' },
  'Vyakaran': { hindi: 'व्याकरण', english: 'Vyakaran' },
  'Essay': { hindi: 'निबंध/पत्र/लेखक-परिचय', english: 'Essay/Letter/Author' },
  'Beehive - Prose': { hindi: 'Beehive - Prose', english: 'Beehive - Prose' },
  'Beehive - Poetry': { hindi: 'Beehive - Poetry', english: 'Beehive - Poetry' },
  'Moments': { hindi: 'Moments', english: 'Moments' },
  'Grammar': { hindi: 'Grammar', english: 'Grammar' },
  'Writing_Skills': { hindi: 'Writing Skills', english: 'Writing Skills' },
};

function hindiTierLabel(tier: number) {
  if (tier === 1) return 'आसान -- Easy';
  if (tier === 2) return 'मध्यम -- Medium';
  return 'कठिन -- Hard';
}

function hindiStatusLabel(status: string) {
  if (status === 'in_progress') return 'प्रगति में -- In progress';
  if (status === 'mastered') return 'महारत प्राप्त -- Mastered';
  return 'बंद -- Locked';
}

function chunkBySub(chapters: ChapterMastery[]) {
  const groups: { label: string; chapters: ChapterMastery[] }[] = [];
  let current: { label: string; chapters: ChapterMastery[] } | null = null;
  for (const ch of chapters) {
    const sub = ch.sub_category || '';
    if (!current || current.label !== sub) {
      current = { label: sub, chapters: [] };
      groups.push(current);
    }
    current.chapters.push(ch);
  }
  return groups;
}

export default function SubjectPage({ params }: { params: Promise<{ bookId: string }> }) {
  const { bookId } = use(params);
  const [chapters, setChapters] = useState<ChapterMastery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedBook, setSelectedBook] = useState<string | null>(null);

  useEffect(() => {
    api.get<ChapterMastery[]>(`/subject/${bookId}/chapters`)
      .then((chs) => { setChapters(chs); setLoading(false); })
      .catch((e: Error) => { setError(e.message); setLoading(false); });
  }, [bookId]);

  const isHindi = bookId === 'Hindi';
  const isEnglish = bookId === 'English';
  const isLanguage = isHindi || isEnglish;

  if (loading) return <BasePageLoader pageType="default" />;


  /* ── LANGUAGE: Book selection screen ── */
  if (isLanguage && !selectedBook) {
    const books = isHindi ? HINDI_BOOKS : ENGLISH_BOOKS;
    const subjectLabelHindi = isHindi ? 'हिंदी' : 'अंग्रेज़ी';
    const subjectLabelEnglish = isHindi ? 'Hindi' : 'English';
    
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Link href="/subject" className="text-stone-500 hover:text-stone-700 transition-colors">
            <ChevronLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="font-heading text-xl font-bold text-stone-900">
              {subjectLabelHindi} -- {subjectLabelEnglish}
            </h1>
            <p className="text-stone-500 text-sm">{isHindi ? 'पुस्तक चुनें -- Select a book' : 'अनुभाग चुनें -- Select a section'}</p>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-rose-600">
            <AlertCircle className="w-4 h-4" />{error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {books.map((book) => {
            const bookChapters = chapters.filter((ch) => book.match(ch.sub_category));
            const completedCount = bookChapters.filter((c) => c.chapter_complete).length;

            return (
              <button
                key={book.key}
                onClick={() => setSelectedBook(book.key)}
                className="text-left bg-white rounded-2xl border border-stone-200 hover:border-teal-300 hover:shadow-sm p-6 transition-all group"
              >
                <div className="w-12 h-12 bg-teal-100 rounded-xl flex items-center justify-center mb-4">
                  <BookOpen className="w-6 h-6 text-teal-700" />
                </div>
                <h2 className="font-heading text-xl font-bold text-stone-900">
                  {isHindi ? book.nameHindi : book.nameLatin}
                </h2>
                {isHindi && <p className="text-sm text-stone-500 mt-0.5">{book.nameLatin}</p>}
                <p className="text-xs text-stone-400 mt-1">
                  {isHindi ? `${book.descHindi} -- ${book.descEnglish}` : book.descHindi}
                </p>
                <div className="mt-4 space-y-1">
                  <div className="flex justify-between text-xs text-stone-500">
                    <span>
                      {isHindi 
                        ? `${completedCount}/${bookChapters.length} अध्याय पूर्ण -- chapters complete` 
                        : `${completedCount}/${bookChapters.length} chapters complete`
                      }
                    </span>
                  </div>
                  <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-teal-500 rounded-full transition-all"
                      style={{ width: `${bookChapters.length ? (completedCount / bookChapters.length) * 100 : 0}%` }}
                    />
                  </div>
                </div>
                <div className="flex items-center gap-1 text-sm text-teal-600 font-medium mt-4 group-hover:text-teal-700 transition-colors">
                  {isHindi ? 'अध्याय देखें -- View chapters' : 'View chapters'} <ChevronRight className="w-4 h-4" />
                </div>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  /* ── Chapter list after selection ── */
  const currentHindiBook = HINDI_BOOKS.find((b) => b.key === selectedBook);
  const currentEnglishBook = ENGLISH_BOOKS.find((b) => b.key === selectedBook);
  
  const filteredChapters = 
    isHindi && currentHindiBook ? chapters.filter((ch) => currentHindiBook.match(ch.sub_category)) :
    isEnglish && currentEnglishBook ? chapters.filter((ch) => currentEnglishBook.match(ch.sub_category)) :
    chapters;

  const completedChapters = filteredChapters.filter((c) => c.chapter_complete).length;
  const totalChapters = filteredChapters.length;
  const completePct = totalChapters > 0 ? Math.round((completedChapters / totalChapters) * 100) : 0;

  const subjectTitle = 
    isHindi && currentHindiBook ? `${currentHindiBook.nameHindi} -- ${currentHindiBook.nameLatin}` :
    isEnglish && currentEnglishBook ? currentEnglishBook.nameLatin :
    bookId.replace(/_/g, ' ');

  const subjectSub = isLanguage
    ? `${totalChapters} अध्याय -- chapters · ${completedChapters} पूर्ण -- complete`
    : `${totalChapters} chapters · ${completedChapters} complete`;

  const groups = isLanguage ? chunkBySub(filteredChapters) : [{ label: '', chapters: filteredChapters }];
  let globalIdx = 0;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Back + title */}
      <div className="flex items-center gap-3">
        {isLanguage ? (
          <button
            onClick={() => setSelectedBook(null)}
            className="text-stone-500 hover:text-stone-700 transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        ) : (
          <Link href="/subject" className="text-stone-500 hover:text-stone-700 transition-colors">
            <ChevronLeft className="w-5 h-5" />
          </Link>
        )}
        <div>
          <h1 className="font-heading text-xl font-bold text-stone-900">{subjectTitle}</h1>
          <p className="text-stone-500 text-sm">{subjectSub}</p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-rose-600">
          <AlertCircle className="w-4 h-4" />{error}
        </div>
      )}

      {/* Overall progress bar */}
      <div className="bg-white rounded-2xl border border-stone-200 p-4">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-stone-600 font-medium">
            {isHindi ? 'समग्र प्रगति -- Overall progress' : 'Overall progress'}
          </span>
          <span className="text-stone-800 font-semibold">{completedChapters}/{totalChapters} chapters</span>
        </div>
        <div className="h-2.5 bg-stone-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-teal-500 rounded-full transition-all"
            style={{ width: `${completePct}%` }}
          />
        </div>
      </div>

      {/* Chapter list */}
      <div className="space-y-3">
        {groups.map((group) => {
          const subLabel = SUB_CAT_LABELS[group.label];
          return (
            <div key={group.label} className="space-y-3">
              {isLanguage && group.label && subLabel && (
                <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide px-1 pt-2">
                  {isHindi ? `${subLabel.hindi} -- ${subLabel.english}` : subLabel.english}
                </h3>
              )}
              {group.chapters.map((ch) => {
                const idx = globalIdx++;
                return (
                  <div key={ch.id} className="bg-white rounded-2xl border border-stone-200 overflow-hidden">
                    <div className="p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3 min-w-0">
                          <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                            ch.status === 'mastered' ? 'bg-emerald-100 text-emerald-700' :
                            ch.status === 'in_progress' ? 'bg-teal-100 text-teal-700' :
                            'bg-stone-100 text-stone-400'
                          }`}>
                            {ch.status === 'mastered' ? <CheckCircle2 className="w-4 h-4" /> :
                             ch.status === 'locked' ? <Lock className="w-4 h-4" /> :
                             idx + 1}
                          </div>
                          <div className="min-w-0">
                            <p className="font-medium text-stone-800 truncate">{ch.title}</p>
                            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                              <span className={`text-xs px-2 py-0.5 rounded-full ${statusBadgeClass(ch.status)}`}>
                                {isHindi ? hindiStatusLabel(ch.status) : (ch.status === 'in_progress' ? 'In progress' : ch.status)}
                              </span>
                              {ch.status !== 'locked' && (
                                <span className="text-xs text-stone-500">
                                  {isHindi
                                    ? `स्तर -- Tier ${ch.current_tier} · ${hindiTierLabel(ch.current_tier)}`
                                    : `Tier ${ch.current_tier} · ${ch.current_tier === 1 ? 'Easy' : ch.current_tier === 2 ? 'Medium' : 'Hard'}`
                                  }
                                </span>
                              )}
                              {ch.review_due && (
                                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                                  {isHindi ? 'समीक्षा बकाया -- Review due' : 'Review due'}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        {ch.status !== 'locked' && (
                          <Link
                            href={`/subject/${bookId}/chapter/${ch.id}`}
                            className="shrink-0 flex items-center gap-1 text-sm text-teal-600 font-medium hover:text-teal-700 transition-colors"
                          >
                            {ch.status === 'mastered'
                              ? (isHindi ? 'समीक्षा -- Review' : 'Review')
                              : (isHindi ? 'अध्ययन -- Study' : 'Study')
                            }
                            <ChevronRight className="w-4 h-4" />
                          </Link>
                        )}
                      </div>

                      {ch.status !== 'locked' && (
                        <div className="mt-3 space-y-2.5">
                          {/* Reading */}
                          <div>
                            <div className="flex items-center justify-between text-xs text-stone-500 mb-1">
                              <span className="flex items-center gap-1">
                                <BookOpenCheck className="w-3.5 h-3.5 text-blue-500" />
                                {isHindi ? 'पढ़ाई -- Reading' : 'Reading'}
                              </span>
                              <span>{Math.round(ch.read_percent)}%</span>
                            </div>
                            <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
                              <div className="h-full bg-blue-400 rounded-full transition-all" style={{ width: `${ch.read_percent}%` }} />
                            </div>
                          </div>

                          {/* Practice Questions */}
                          <div className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-1 text-stone-500">
                              <FlaskConical className="w-3.5 h-3.5 text-violet-500" />
                              {isHindi ? 'अभ्यास प्रश्न -- Practice Questions' : 'Practice Questions'}
                            </span>
                            <span className={`font-semibold ${ch.practice_solved >= ch.practice_total && ch.practice_total > 0 ? 'text-emerald-600' : 'text-stone-600'}`}>
                              {ch.practice_solved}/{ch.practice_total}
                            </span>
                          </div>

                          {/* Board Paper */}
                          <div className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-1 text-stone-500">
                              <Trophy className="w-3.5 h-3.5 text-amber-500" />
                              {isHindi ? 'बोर्ड पेपर -- Board Paper' : 'Board Paper'}
                            </span>
                            {ch.board_passed ? (
                              <span className="flex items-center gap-1 text-emerald-600 font-semibold">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                {isHindi ? 'उत्तीर्ण -- Passed' : 'Passed'}
                              </span>
                            ) : (
                              <span className="text-stone-400">{isHindi ? 'अनुत्तीर्ण -- Not attempted' : 'Not attempted'}</span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
