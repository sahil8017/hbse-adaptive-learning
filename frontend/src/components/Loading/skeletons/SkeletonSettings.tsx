export default function SkeletonSettings() {
  return (
    <div className="min-h-screen bg-white p-6">
      {/* Header */}
      <div className="skeleton-shimmer h-8 w-40 rounded mb-8" />

      <div className="flex flex-col md:flex-row gap-6 max-w-4xl">
        {/* Left sidebar menu */}
        <div className="w-full md:w-40 flex-shrink-0 space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton-shimmer h-10 w-full rounded" />
          ))}
        </div>

        {/* Right content panel */}
        <div className="flex-1">
          <div className="skeleton-shimmer h-6 w-32 rounded mb-6" />
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="space-y-2">
                <div className="skeleton-shimmer h-4 w-24 rounded" />
                <div className="skeleton-shimmer h-10 w-full rounded" />
              </div>
            ))}
          </div>

          {/* Save button */}
          <div className="mt-8">
            <div className="skeleton-shimmer h-10 w-24 rounded" />
          </div>
        </div>
      </div>
    </div>
  );
}
