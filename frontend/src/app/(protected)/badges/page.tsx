'use client';

import { useEffect, useState } from 'react';
import { Lock } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import type { Badge } from '@/lib/types';
import { BasePageLoader } from '@/components/Loading';

const tierConfig: Record<string, {
  bg: string; ring: string; glow: string; label: string;
  labelText: string; cardBorder: string; cardBg: string;
}> = {
  gold: {
    bg: 'from-yellow-500 via-amber-400 to-yellow-600',
    ring: 'ring-yellow-400/60',
    glow: 'shadow-yellow-400/40',
    label: 'bg-yellow-500 text-white',
    labelText: 'Gold',
    cardBorder: 'border-yellow-200',
    cardBg: 'bg-gradient-to-b from-yellow-50 to-white',
  },
  silver: {
    bg: 'from-slate-400 via-stone-300 to-slate-500',
    ring: 'ring-slate-400/60',
    glow: 'shadow-slate-400/30',
    label: 'bg-slate-400 text-white',
    labelText: 'Silver',
    cardBorder: 'border-slate-200',
    cardBg: 'bg-gradient-to-b from-slate-50 to-white',
  },
  bronze: {
    bg: 'from-amber-600 via-amber-500 to-amber-700',
    ring: 'ring-amber-500/50',
    glow: 'shadow-amber-500/30',
    label: 'bg-amber-600 text-white',
    labelText: 'Bronze',
    cardBorder: 'border-amber-200',
    cardBg: 'bg-gradient-to-b from-amber-50 to-white',
  },
};

function BadgeIcon({ tier, earned }: { tier: string; earned: boolean }) {
  const cfg = tierConfig[tier] ?? tierConfig.bronze;

  if (!earned) {
    return (
      <div className="w-16 h-16 rounded-full bg-stone-100 flex items-center justify-center">
        <Lock className="w-7 h-7 text-stone-300" />
      </div>
    );
  }

  return (
    <div className={`relative w-16 h-16 rounded-full bg-gradient-to-br ${cfg.bg} shadow-lg ${cfg.glow} ring-4 ${cfg.ring} flex items-center justify-center`}>
      <svg viewBox="0 0 48 48" className="w-9 h-9 text-white drop-shadow" fill="currentColor">
        {tier === 'gold' && (
          <path d="M24 5l5.09 10.26L41 17.18l-8.5 8.28 2 11.54L24 31.77l-10.5 5.23 2-11.54L7 17.18l11.91-1.92z" />
        )}
        {tier === 'silver' && (
          <path d="M24 5L8 11v13c0 8.84 6.84 17.12 16 20 9.16-2.88 16-11.16 16-20V11L24 5z" />
        )}
        {tier === 'bronze' && (
          <>
            <circle cx="24" cy="20" r="13" />
            <path d="M16 31l-4 10 12-6 12 6-4-10" opacity="0.85" />
          </>
        )}
      </svg>
      {/* Gloss */}
      <div className="absolute inset-0 rounded-full bg-gradient-to-b from-white/35 to-transparent" />
    </div>
  );
}

function BadgeCard({ badge, earned }: { badge: Badge; earned: boolean }) {
  const tier = badge.tier || 'bronze';
  const cfg = tierConfig[tier] ?? tierConfig.bronze;

  return (
    <div
      className={`relative rounded-2xl border p-4 flex flex-col items-center text-center gap-3 transition-all duration-300 ${
        earned
          ? `${cfg.cardBorder} ${cfg.cardBg} shadow-md hover:shadow-xl hover:-translate-y-1 hover:scale-[1.02]`
          : 'border-stone-100 bg-white opacity-45 grayscale'
      }`}
    >
      {/* Earned shimmer effect on gold */}
      {earned && tier === 'gold' && (
        <div
          className="absolute inset-0 rounded-2xl pointer-events-none opacity-20"
          style={{
            background: 'linear-gradient(105deg, transparent 40%, rgba(255,215,0,0.6) 50%, transparent 60%)',
            backgroundSize: '200% 100%',
            animation: 'badge-shimmer-gold 3s ease-in-out infinite',
          }}
        />
      )}

      <BadgeIcon tier={tier} earned={earned} />

      <div className="space-y-1">
        <p className="font-heading font-bold text-stone-800 text-sm leading-tight">{badge.name}</p>
        <p className="text-xs text-stone-500 leading-relaxed">{badge.description}</p>
      </div>

      {earned ? (
        <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${cfg.label}`}>
          {cfg.labelText}
        </span>
      ) : (
        <span className="text-[10px] text-stone-300 font-medium uppercase tracking-wider">Locked</span>
      )}
    </div>
  );
}

export default function BadgesPage() {
  const { student } = useAuth();
  const [catalog, setCatalog] = useState<Badge[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<Badge[]>('/badges/catalog')
      .then((b) => { setCatalog(b); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const unlocked = new Set(student?.unlocked_badges ?? []);
  const earnedCount = catalog.filter((b) => unlocked.has(b.code)).length;

  if (loading) return <BasePageLoader pageType="profile" />;

  // Sort: earned first, then by tier (gold > silver > bronze)
  const tierOrder = { gold: 0, silver: 1, bronze: 2 };
  const sorted = [...catalog].sort((a, b) => {
    const ae = unlocked.has(a.code);
    const be = unlocked.has(b.code);
    if (ae !== be) return ae ? -1 : 1;
    return (tierOrder[a.tier as keyof typeof tierOrder] ?? 3) - (tierOrder[b.tier as keyof typeof tierOrder] ?? 3);
  });

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-heading text-2xl font-bold text-stone-900">Badges</h1>
        <p className="text-stone-500 text-sm mt-1">
          {earnedCount} of {catalog.length} earned
        </p>
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="h-3 bg-stone-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-amber-500 to-yellow-400 transition-all duration-700"
            style={{ width: `${catalog.length ? (earnedCount / catalog.length) * 100 : 0}%` }}
          />
        </div>
        <p className="text-xs text-stone-400 text-right">{Math.round(catalog.length ? (earnedCount / catalog.length) * 100 : 0)}% complete</p>
      </div>

      {/* Earned summary row */}
      {earnedCount > 0 && (
        <div className="flex gap-3 flex-wrap">
          {(['gold', 'silver', 'bronze'] as const).map((tier) => {
            const count = catalog.filter((b) => unlocked.has(b.code) && b.tier === tier).length;
            if (!count) return null;
            const cfg = tierConfig[tier];
            return (
              <div key={tier} className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${cfg.cardBorder} ${cfg.cardBg}`}>
                <div className={`w-4 h-4 rounded-full bg-gradient-to-br ${cfg.bg}`} />
                <span className="text-xs font-semibold text-stone-700">{count} {cfg.labelText}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Badge grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
        {sorted.map((badge) => (
          <BadgeCard key={badge.code} badge={badge} earned={unlocked.has(badge.code)} />
        ))}
      </div>
    </div>
  );
}
