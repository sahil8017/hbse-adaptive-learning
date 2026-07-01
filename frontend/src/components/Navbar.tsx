'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { BookOpen, LayoutDashboard, MessageCircle, Award, Shield, LogOut, Menu, X } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/subject', label: 'Subjects', icon: BookOpen },
  { href: '/tutor', label: 'Tutor', icon: MessageCircle },
  { href: '/badges', label: 'Badges', icon: Award },
];

export default function Navbar() {
  const { student, logout, isAdmin } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (!student) return null;

  return (
    <>
      {/* ── Top bar ─────────────────────────────────── */}
      <nav className="bg-white border-b border-stone-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-13 sm:h-14">
            {/* Logo */}
            <Link href="/dashboard" className="flex items-center gap-1.5 font-heading font-bold text-teal-700 text-base sm:text-lg">
              <BookOpen className="w-4 h-4 sm:w-5 sm:h-5" />
              <span>HBSE Learn</span>
            </Link>

            {/* Desktop nav */}
            <div className="hidden md:flex items-center gap-1">
              {navItems.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    pathname.startsWith(href)
                      ? 'bg-teal-50 text-teal-700'
                      : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900',
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </Link>
              ))}
              {isAdmin && (
                <Link
                  href="/admin"
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    pathname.startsWith('/admin')
                      ? 'bg-amber-50 text-amber-700'
                      : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900',
                  )}
                >
                  <Shield className="w-4 h-4" />
                  Admin
                </Link>
              )}
            </div>

            {/* Desktop right */}
            <div className="hidden md:flex items-center gap-3">
              <span className="text-sm text-stone-600">
                <span className="font-medium text-stone-800">{student.display_name || student.username}</span>
                <span className="ml-2 text-amber-600 font-semibold">{student.streak_count} day streak</span>
              </span>
              <button onClick={logout} className="text-stone-400 hover:text-rose-600 transition-colors">
                <LogOut className="w-4 h-4" />
              </button>
            </div>

            {/* Mobile: streak + hamburger */}
            <div className="flex md:hidden items-center gap-2">
              <span className="text-sm text-amber-600 font-semibold">{student.streak_count} streak</span>
              <button
                className="p-1.5 rounded-lg text-stone-600 hover:bg-stone-100"
                onClick={() => setMobileOpen(!mobileOpen)}
              >
                {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile dropdown menu */}
        {mobileOpen && (
          <div className="md:hidden border-t border-stone-100 px-3 py-2 space-y-1 bg-white">
            {isAdmin && (
              <Link href="/admin" onClick={() => setMobileOpen(false)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-amber-700">
                <Shield className="w-4 h-4" />Admin
              </Link>
            )}
            <div className="flex items-center justify-between px-3 py-2 text-sm text-stone-600">
              <span className="font-medium text-stone-800">{student.display_name || student.username}</span>
              <button onClick={logout} className="flex items-center gap-1 text-rose-500 text-xs">
                <LogOut className="w-3.5 h-3.5" />Sign out
              </button>
            </div>
          </div>
        )}
      </nav>

      {/* ── Mobile bottom navigation bar ─────────────── */}
      <div className="md:hidden fixed bottom-0 inset-x-0 z-50 bg-white border-t border-stone-200 flex">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex-1 flex flex-col items-center gap-0.5 py-2 text-xs font-medium transition-colors',
                active ? 'text-teal-600' : 'text-stone-400',
              )}
            >
              <Icon className={cn('w-5 h-5', active && 'text-teal-600')} />
              {label}
            </Link>
          );
        })}
      </div>

    </>
  );
}
