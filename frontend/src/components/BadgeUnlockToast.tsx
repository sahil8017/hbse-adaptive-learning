'use client';

import { useEffect, useState, useRef } from 'react';
import { useBadgeUnlock } from '@/context/BadgeUnlockContext';
import type { UnlockableBadge } from '@/context/BadgeUnlockContext';

const DISPLAY_MS = 4500;

const tierConfig = {
  gold: {
    ring: 'border-yellow-400',
    bg: 'from-yellow-500 via-amber-400 to-yellow-600',
    glow: 'shadow-yellow-400/60',
    label: 'bg-yellow-500 text-white',
    confetti: ['#FFD700', '#FFA500', '#FF8C00', '#FFEC00', '#FFB300'],
    particle: 'bg-yellow-400',
  },
  silver: {
    ring: 'border-slate-400',
    bg: 'from-slate-400 via-stone-300 to-slate-500',
    glow: 'shadow-slate-400/60',
    label: 'bg-slate-400 text-white',
    confetti: ['#C0C0C0', '#A8A8A8', '#D3D3D3', '#808080', '#E8E8E8'],
    particle: 'bg-slate-400',
  },
  bronze: {
    ring: 'border-amber-600',
    bg: 'from-amber-600 via-amber-500 to-amber-700',
    glow: 'shadow-amber-500/60',
    label: 'bg-amber-600 text-white',
    confetti: ['#CD7F32', '#B8860B', '#DAA520', '#C68642', '#A0522D'],
    particle: 'bg-amber-500',
  },
};

function Confetti({ colors }: { colors: string[] }) {
  const pieces = Array.from({ length: 24 }, (_, i) => i);
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {pieces.map((i) => {
        const color = colors[i % colors.length];
        const left = `${8 + (i * 3.7) % 84}%`;
        const delay = `${(i * 0.07) % 1}s`;
        const size = 5 + (i % 4) * 2;
        const shape = i % 3 === 0 ? 'rounded-full' : i % 3 === 1 ? 'rounded-sm rotate-45' : '';
        return (
          <div
            key={i}
            className={`absolute ${shape}`}
            style={{
              left,
              top: '-12px',
              width: size,
              height: size,
              backgroundColor: color,
              animation: `confetti-fall ${0.9 + (i % 5) * 0.18}s ease-in ${delay} forwards`,
            }}
          />
        );
      })}
    </div>
  );
}

function BadgeIcon({ tier }: { tier: 'bronze' | 'silver' | 'gold' }) {
  const cfg = tierConfig[tier];
  return (
    <div className="relative flex items-center justify-center">
      {/* Pulsing rings */}
      <div className={`absolute w-28 h-28 rounded-full border-4 ${cfg.ring} opacity-40 badge-ring`} />
      <div
        className={`absolute w-28 h-28 rounded-full border-4 ${cfg.ring} opacity-20 badge-ring`}
        style={{ animationDelay: '0.4s' }}
      />

      {/* Main badge circle */}
      <div
        className={`relative w-24 h-24 rounded-full bg-gradient-to-br ${cfg.bg} shadow-2xl ${cfg.glow} badge-float flex items-center justify-center`}
      >
        {/* Inner shield/star shape */}
        <svg viewBox="0 0 48 48" className="w-12 h-12 text-white drop-shadow-lg" fill="currentColor">
          {tier === 'gold' && (
            // Star shape for gold
            <path d="M24 4l5.09 10.26L41 16.18l-8.5 8.28 2 11.54L24 30.77l-10.5 5.23 2-11.54L7 16.18l11.91-1.92z" />
          )}
          {tier === 'silver' && (
            // Shield for silver
            <path d="M24 4L8 10v14c0 8.84 6.84 17.12 16 20 9.16-2.88 16-11.16 16-20V10L24 4z" />
          )}
          {tier === 'bronze' && (
            // Ribbon/medal for bronze
            <>
              <circle cx="24" cy="20" r="14" />
              <path d="M16 32l-4 10 12-6 12 6-4-10" opacity="0.85" />
            </>
          )}
        </svg>

        {/* Gloss overlay */}
        <div className="absolute inset-0 rounded-full bg-gradient-to-b from-white/30 to-transparent" />
      </div>
    </div>
  );
}

function ToastCard({ badge, onDismiss }: { badge: UnlockableBadge; onDismiss: () => void }) {
  const [exiting, setExiting] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const cfg = tierConfig[badge.tier] ?? tierConfig.bronze;

  const dismiss = () => {
    setExiting(true);
    setTimeout(onDismiss, 280);
  };

  useEffect(() => {
    timerRef.current = setTimeout(dismiss, DISPLAY_MS);
    return () => clearTimeout(timerRef.current);
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      className={`relative bg-white rounded-3xl shadow-2xl overflow-hidden w-[340px] max-w-[92vw] ${exiting ? 'toast-out' : 'toast-in'}`}
      style={{ boxShadow: '0 25px 60px rgba(0,0,0,0.3)' }}
    >
      <Confetti colors={cfg.confetti} />

      {/* Top gradient band */}
      <div className={`h-2 w-full bg-gradient-to-r ${cfg.bg}`} />

      <div className="px-6 pt-8 pb-6 flex flex-col items-center gap-4">
        {/* "Badge Unlocked" label */}
        <span className="text-xs font-bold uppercase tracking-widest text-stone-400">
          Badge Unlocked
        </span>

        {/* Animated badge icon */}
        <div className="badge-pop">
          <BadgeIcon tier={badge.tier} />
        </div>

        {/* Text */}
        <div className="text-center space-y-1">
          <h2 className="font-heading text-xl font-bold text-stone-900">{badge.name}</h2>
          <p className="text-sm text-stone-500 leading-relaxed">{badge.description}</p>
        </div>

        {/* Tier pill */}
        <span className={`text-xs font-semibold uppercase tracking-wider px-3 py-1 rounded-full ${cfg.label}`}>
          {badge.tier}
        </span>

        {/* Dismiss button */}
        <button
          onClick={dismiss}
          className="mt-1 text-xs text-stone-400 hover:text-stone-600 transition-colors"
        >
          Tap to dismiss
        </button>
      </div>

      {/* Progress drain bar */}
      <div className="h-1 w-full bg-stone-100">
        <div
          className={`h-full bg-gradient-to-r ${cfg.bg}`}
          style={{ animation: `progress-drain ${DISPLAY_MS}ms linear forwards` }}
        />
      </div>
    </div>
  );
}

export default function BadgeUnlockToast() {
  const { queue, dismissCurrent } = useBadgeUnlock();
  const current = queue[0];

  if (!current) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center pointer-events-none">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm pointer-events-auto" onClick={dismissCurrent} />
      {/* Card */}
      <div className="relative pointer-events-auto">
        <ToastCard key={current.code} badge={current} onDismiss={dismissCurrent} />
      </div>
    </div>
  );
}
