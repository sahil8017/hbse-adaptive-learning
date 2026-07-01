export default function SkeletonDefault() {
  return (
    <div className="min-h-screen bg-white p-6">
      {/* Header */}
      <div className="skeleton-shimmer h-8 w-48 rounded mb-8" />

      {/* Generic content blocks */}
      <div className="space-y-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-3">
            <div className="skeleton-shimmer h-6 w-32 rounded" />
            <div className="skeleton-shimmer h-4 w-full rounded" />
            <div className="skeleton-shimmer h-4 w-5/6 rounded" />
            <div className="skeleton-shimmer h-4 w-4/5 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
