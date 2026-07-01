'use client';

import { useEffect, useState } from 'react';

interface Step {
  id: number;
  label: string;
  duration: number;
}

interface ProgressCardProps {
  steps: Step[];
  microCopy: string[];
  pageTitle: string;
  emoji: string;
}

export default function ProgressCard({
  steps,
  microCopy,
  pageTitle,
  emoji,
}: ProgressCardProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [copyIndex, setCopyIndex] = useState(0);
  const [copyVisible, setCopyVisible] = useState(true);

  // Advance steps automatically
  useEffect(() => {
    if (currentStep >= steps.length) return;
    const timer = setTimeout(() => {
      setCurrentStep((s) => s + 1);
    }, steps[currentStep]?.duration ?? 800);
    return () => clearTimeout(timer);
  }, [currentStep, steps]);

  // Rotate micro-copy with fade
  useEffect(() => {
    if (microCopy.length <= 1) return;
    const interval = setInterval(() => {
      setCopyVisible(false);
      setTimeout(() => {
        setCopyIndex((i) => (i + 1) % microCopy.length);
        setCopyVisible(true);
      }, 400);
    }, 2200);
    return () => clearInterval(interval);
  }, [microCopy]);

  return (
    <div className="fixed md:absolute inset-0 z-40 flex items-center justify-center bg-white/60 backdrop-blur-xs">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xl p-8 w-[380px] max-w-[90vw]">

        {/* Brand Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="h-10 w-10 rounded-xl bg-teal-600 flex items-center justify-center text-white flex-shrink-0">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6">
              {/* Book pages */}
              <path d="M4 6h16v12H4V6z" />
              <path d="M4 9h16" />
              <path d="M8 6v12" />
              {/* Light beam (knowledge) */}
              <path d="M12 2v2" strokeLinecap="round" />
              <path d="M16 4l-1.4 1.4" strokeLinecap="round" />
              <path d="M8 4l1.4 1.4" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <p className="text-[10px] font-medium text-teal-600 uppercase tracking-wider">HBSE Learning Platform</p>
            <p className="text-base font-semibold text-slate-800 flex items-center gap-1.5">
              {emoji && <span>{emoji}</span>}
              <span>{pageTitle}</span>
            </p>
          </div>
        </div>

        {/* Progress Steps */}
        <div className="flex flex-col gap-3 mb-6">
          {steps.map((step, index) => {
            const isDone = index < currentStep;
            const isActive = index === currentStep;
            
            return (
              <div key={step.id} className="flex items-center gap-3">
                {/* Icon */}
                <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
                  {isDone && (
                    <svg className="w-5 h-5 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {isActive && (
                    <svg className="w-4 h-4 text-teal-600 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                    </svg>
                  )}
                  {!isDone && !isActive && (
                    <div className="w-4 h-4 rounded-full border-2 border-slate-300" />
                  )}
                </div>

                {/* Label */}
                <span className={`text-sm transition-all duration-300 ${
                  isDone ? 'text-slate-400 line-through' :
                  isActive ? 'text-teal-700 font-medium' :
                  'text-slate-400'
                }`}>
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>

        {/* Divider */}
        <div className="border-t border-slate-100 mb-4" />

        {/* Micro-copy */}
        <div
          className="flex items-start gap-2 transition-opacity duration-300"
          style={{ opacity: copyVisible ? 1 : 0 }}
        >
          <p className="text-sm text-teal-700 italic leading-relaxed">
            {microCopy[copyIndex]}
          </p>
        </div>

      </div>
    </div>
  );
}
