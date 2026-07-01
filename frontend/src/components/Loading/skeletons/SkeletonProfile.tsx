export default function SkeletonProfile() {
  return (
    <div className="min-h-screen bg-white p-6">
      <div className="flex flex-col md:flex-row gap-6">
        {/* Left sidebar */}
        <div className="w-full md:w-64 flex-shrink-0">
          {/* Avatar */}
          <div className="skeleton-shimmer h-24 w-24 rounded-full mx-auto mb-4" />
          {/* Name */}
          <div className="skeleton-shimmer h-6 w-32 rounded mx-auto mb-2" />
          {/* Class */}
          <div className="skeleton-shimmer h-4 w-24 rounded mx-auto mb-8" />

          {/* Menu items */}
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="skeleton-shimmer h-10 w-full rounded" />
            ))}
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1">
          {/* Section title */}
          <div className="skeleton-shimmer h-8 w-48 rounded mb-6" />

          {/* Content cards */}
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton-shimmer h-32 w-full rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
