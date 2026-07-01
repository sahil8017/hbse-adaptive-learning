'use client';

export function SkeletonPulse({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-stone-200 rounded animate-pulse ${className}`} />
  );
}

export function ChatMessageSkeleton() {
  return (
    <div className="flex gap-3 mb-4">
      <SkeletonPulse className="w-8 h-8 rounded-full shrink-0" />
      <div className="flex-1 space-y-2">
        <SkeletonPulse className="h-4 w-3/4" />
        <SkeletonPulse className="h-4 w-1/2" />
      </div>
    </div>
  );
}

export function DashboardCardSkeleton() {
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-4 space-y-3">
      <SkeletonPulse className="h-5 w-1/3" />
      <SkeletonPulse className="h-8 w-1/2" />
      <div className="pt-2 space-y-2">
        <SkeletonPulse className="h-3 w-full" />
        <SkeletonPulse className="h-3 w-4/5" />
      </div>
    </div>
  );
}

export function QuestionSkeleton() {
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-4 space-y-4">
      <SkeletonPulse className="h-6 w-5/6" />
      <div className="space-y-2">
        {[1, 2, 3, 4].map((i) => (
          <SkeletonPulse key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

export function FormFieldSkeleton() {
  return (
    <div className="space-y-2 mb-4">
      <SkeletonPulse className="h-4 w-1/4" />
      <SkeletonPulse className="h-10 w-full" />
    </div>
  );
}

export function TextSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonPulse
          key={i}
          className={`h-4 ${i === lines - 1 ? 'w-3/4' : 'w-full'}`}
        />
      ))}
    </div>
  );
}

export function ChapterReaderSkeleton() {
  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2 space-y-4">
        <SkeletonPulse className="h-8 w-3/4" />
        <TextSkeleton lines={5} />
      </div>
      <div className="space-y-2">
        <SkeletonPulse className="h-6 w-full" />
        {[1, 2, 3].map((i) => (
          <SkeletonPulse key={i} className="h-12 w-full" />
        ))}
      </div>
    </div>
  );
}
