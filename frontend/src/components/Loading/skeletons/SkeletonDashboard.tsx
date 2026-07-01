export default function SkeletonDashboard() {
  return (
    <div className="min-h-screen bg-white p-6">
      {/* Header */}
      <div className="skeleton-shimmer h-8 w-48 rounded mb-8" />

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton-shimmer h-24 rounded-lg" />
        ))}
      </div>

      {/* Charts section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 skeleton-shimmer h-64 rounded-lg" />
        <div className="skeleton-shimmer h-64 rounded-lg" />
      </div>

      {/* Recent activity */}
      <div className="mt-8">
        <div className="skeleton-shimmer h-6 w-32 rounded mb-4" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton-shimmer h-12 w-full rounded" />
          ))}
        </div>
      </div>
    </div>
  );
}
