export default function SkeletonTutor() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <div className="hidden md:flex flex-col gap-4 w-64 p-4 border-r border-slate-200 bg-white">
        {[80, 65, 75, 60, 70].map((w, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="skeleton-shimmer h-8 w-8 rounded-lg flex-shrink-0" />
            <div className="skeleton-shimmer h-4 rounded" style={{ width: `${w}%` }} />
          </div>
        ))}
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col p-6 gap-4 bg-white">
        {/* Chat header */}
        <div className="flex items-center gap-3 pb-4 border-b border-slate-200">
          <div className="skeleton-shimmer h-10 w-10 rounded-full" />
          <div className="flex flex-col gap-2">
            <div className="skeleton-shimmer h-4 w-32 rounded" />
            <div className="skeleton-shimmer h-3 w-20 rounded" />
          </div>
        </div>

        {/* Chat bubbles */}
        <div className="flex justify-start">
          <div className="skeleton-shimmer h-16 w-64 rounded-2xl rounded-tl-xs" />
        </div>
        <div className="flex justify-end">
          <div className="skeleton-shimmer h-12 w-48 rounded-2xl rounded-tr-xs" />
        </div>
        <div className="flex justify-start">
          <div className="skeleton-shimmer h-20 w-72 rounded-2xl rounded-tl-xs" />
        </div>

        {/* Input bar */}
        <div className="mt-auto skeleton-shimmer h-12 w-full rounded-xl" />
      </div>
    </div>
  );
}
