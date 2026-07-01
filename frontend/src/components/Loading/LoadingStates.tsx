'use client';

import {
  ChatMessageSkeleton,
  DashboardCardSkeleton,
  QuestionSkeleton,
  FormFieldSkeleton,
  ChapterReaderSkeleton,
} from './SkeletonBase';

export function TutorPageLoading() {
  return (
    <div className="space-y-4 pt-4">
      <ChatMessageSkeleton />
      <ChatMessageSkeleton />
      <ChatMessageSkeleton />
    </div>
  );
}

export function DashboardLoading() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <DashboardCardSkeleton />
        <DashboardCardSkeleton />
        <DashboardCardSkeleton />
        <DashboardCardSkeleton />
      </div>
      <DashboardCardSkeleton />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DashboardCardSkeleton />
        <DashboardCardSkeleton />
      </div>
    </div>
  );
}

export function PracticeLoading() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="h-6 bg-stone-200 rounded animate-pulse w-1/3" />
        <div className="h-4 bg-stone-200 rounded animate-pulse w-2/3" />
      </div>
      {[1, 2, 3].map((i) => (
        <QuestionSkeleton key={i} />
      ))}
    </div>
  );
}

export function ProfileLoading() {
  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="h-8 bg-stone-200 rounded animate-pulse w-1/4" />
        <FormFieldSkeleton />
        <FormFieldSkeleton />
        <FormFieldSkeleton />
      </div>
      <div className="space-y-4">
        <div className="h-8 bg-stone-200 rounded animate-pulse w-1/4" />
        <FormFieldSkeleton />
        <FormFieldSkeleton />
      </div>
    </div>
  );
}

export function ChapterReaderLoading() {
  return (
    <div className="space-y-4">
      <ChapterReaderSkeleton />
    </div>
  );
}

export function ProgressLoading() {
  return (
    <div className="space-y-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="space-y-2 bg-white p-4 rounded-lg border border-stone-200">
          <div className="h-5 bg-stone-200 rounded animate-pulse w-1/3" />
          <div className="h-3 bg-stone-200 rounded animate-pulse w-full" />
          <div className="h-3 bg-stone-200 rounded animate-pulse w-2/3" />
        </div>
      ))}
    </div>
  );
}

export function BadgesLoading() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
        <div key={i} className="aspect-square bg-stone-200 rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

export function SettingsLoading() {
  return (
    <div className="space-y-6">
      {[1, 2, 3].map((i) => (
        <div key={i} className="space-y-3 bg-white p-4 rounded-lg border border-stone-200">
          <div className="h-6 bg-stone-200 rounded animate-pulse w-1/4" />
          <FormFieldSkeleton />
        </div>
      ))}
    </div>
  );
}
