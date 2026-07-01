export default function SkeletonPractice() {
  return (
    <div className="min-h-screen bg-white p-6">
      {/* Header with timer */}
      <div className="flex justify-between items-center mb-8">
        <div className="skeleton-shimmer h-8 w-40 rounded" />
        <div className="skeleton-shimmer h-8 w-24 rounded" />
      </div>

      {/* Question area */}
      <div className="max-w-3xl mx-auto">
        {/* Question title */}
        <div className="skeleton-shimmer h-6 w-full rounded mb-4" />
        <div className="skeleton-shimmer h-4 w-5/6 rounded mb-8" />

        {/* Question content */}
        <div className="space-y-3 mb-8">
          <div className="skeleton-shimmer h-4 w-full rounded" />
          <div className="skeleton-shimmer h-4 w-4/5 rounded" />
          <div className="skeleton-shimmer h-4 w-3/4 rounded" />
        </div>

        {/* Options */}
        <div className="space-y-3 mb-8">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton-shimmer h-12 w-full rounded-lg" />
          ))}
        </div>

        {/* Footer buttons */}
        <div className="flex gap-4">
          <div className="skeleton-shimmer h-10 w-24 rounded" />
          <div className="skeleton-shimmer h-10 w-32 rounded" />
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-8 max-w-3xl mx-auto">
        <div className="skeleton-shimmer h-2 w-full rounded-full" />
      </div>
    </div>
  );
}
