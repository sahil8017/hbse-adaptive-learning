import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function tierLabel(tier: number): string {
  return tier === 1 ? 'Easy' : tier === 2 ? 'Medium' : 'Hard';
}

export function tierColor(tier: number): string {
  return tier === 1 ? 'text-emerald-600' : tier === 2 ? 'text-amber-600' : 'text-rose-600';
}

export function masteryColor(pct: number): string {
  if (pct >= 80) return 'bg-emerald-500';
  if (pct >= 50) return 'bg-amber-500';
  return 'bg-rose-400';
}

export function statusBadgeClass(status: string): string {
  switch (status) {
    case 'mastered': return 'bg-emerald-100 text-emerald-700';
    case 'in_progress': return 'bg-amber-100 text-amber-700';
    default: return 'bg-stone-100 text-stone-500';
  }
}

export function formatDate(iso?: string): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}
