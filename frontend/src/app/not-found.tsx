import Link from 'next/link';
import { BookOpen } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-stone-50 flex flex-col items-center justify-center text-center px-4">
      <div className="w-16 h-16 bg-teal-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <BookOpen className="w-8 h-8 text-teal-600" />
      </div>
      <h1 className="font-heading text-6xl font-bold text-stone-200 mb-2">404</h1>
      <h2 className="font-heading text-xl font-semibold text-stone-800 mb-2">Page not found</h2>
      <p className="text-stone-500 text-sm mb-6 max-w-xs">The page you&apos;re looking for doesn&apos;t exist or has been moved.</p>
      <Link
        href="/dashboard"
        className="bg-teal-600 hover:bg-teal-700 text-white font-medium px-5 py-2.5 rounded-xl transition-colors text-sm"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
