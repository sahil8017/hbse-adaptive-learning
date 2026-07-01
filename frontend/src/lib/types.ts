export interface Student {
  id: number;
  username: string;
  email: string;
  display_name: string;
  role: string;
  class_grade: string;
  board: string;
  school?: string;
  streak_count: number;
  last_active_date?: string;
  focus_areas: string[];
  unlocked_badges: string[];
}

export interface LoginResponse {
  student: Student;
  is_new: boolean;
  needs_diagnostic: boolean;
  auth_provider: string;
}

export interface SubjectMeta {
  book_id: string;
  name: string;
  short_name?: string;
  emoji?: string;
}

export interface ChapterMastery {
  id: string;
  title: string;
  sub_category?: string;
  status: 'locked' | 'in_progress' | 'mastered';
  mastery_percent: number;
  read_percent: number;
  current_tier: number;
  review_due: boolean;
  locked: boolean;
  practice_total: number;
  practice_solved: number;
  board_passed: boolean;
  chapter_complete: boolean;
}

export interface SubjectSummary {
  book_id: string;
  total_chapters: number;
  mastered_chapters: number;
  completed_chapters: number;
  read_percent: number;
  mastery_percent: number;
  review_due: boolean;
}

export interface DashboardData {
  student: Student;
  subjects: SubjectSummary[];
}

export interface Section {
  section_id: string;
  title: string;
  content?: string;
  key_terms?: string[];
  is_read: boolean;
}

export interface Chapter {
  chapter_id: string;
  title: string;
  sections: Section[];
}

export type QuestionType = 'mcq' | 'open';

export interface Question {
  id: number;
  text: string;
  options?: string[];
  type: QuestionType;
  tier: 1 | 2 | 3;
  book_id: string;
  chapter_id: string;
  subtopic?: string;
  is_pyq?: boolean;
  pyq_year?: number;
  marks?: number;
}

export interface PracticeSubmitResult {
  is_correct: boolean;
  promoted: boolean;
  new_tier: number;
  mastery: {
    mastery_percent: number;
    current_tier: number;
    status: string;
  };
  // grade-open only
  score?: number;
  feedback?: string;
  // mcq only
  student_answer_text?: string | null;
}

export type ExamQuestion = Question;

export interface Badge {
  id?: number;
  code: string;
  name: string;
  description: string;
  tier?: 'bronze' | 'silver' | 'gold';
  criteria?: string;
}

export interface ChatMessage {
  sender: 'user' | 'ai';
  message: string;
  is_blocked: boolean;
  timestamp: string;
}

export interface ShareChapter {
  chapter_id: string;
  mastery_percent: number;
  status: string;
}

export interface ShareSubject {
  chapters: ShareChapter[];
  avg_mastery: number;
}

export interface ShareProgressData {
  student: {
    username: string;
    streak_count: number;
    unlocked_badges: string[];
  };
  subjects: Record<string, ShareSubject>;
  exam_history: {
    book_id: string;
    chapter_id: string;
    score_percent: number;
    passed: boolean;
    attempted_at?: string;
  }[];
}

export interface AdminStudent {
  id: number;
  display_name: string;
  email: string;
  streak_count: number;
  last_active_date?: string;
  overall_mastery?: number;
}

export interface AdminQuestion {
  id: number;
  book_id: string;
  chapter_id: string;
  tier: 1 | 2 | 3;
  type: QuestionType;
  text: string;
  options?: string[];
  correct_answer?: number;
  subtopic?: string;
  is_pyq?: boolean;
  pyq_year?: number;
  marks?: number;
}

export interface MasteryDistribution {
  book_id: string;
  tier_1_count: number;
  tier_2_count: number;
  tier_3_count: number;
  avg_mastery: number;
}
