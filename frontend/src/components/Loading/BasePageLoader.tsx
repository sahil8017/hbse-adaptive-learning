'use client';

import { useMemo } from 'react';
import { useLoadingConfig, type PageType } from './useLoadingConfig';
import ProgressCard from './ProgressCard';
import {
  SkeletonTutor,
  SkeletonDashboard,
  SkeletonPractice,
  SkeletonProfile,
  SkeletonSettings,
  SkeletonDefault,
} from './skeletons';

interface BasePageLoaderProps {
  pageType: PageType;
}

export default function BasePageLoader({ pageType }: BasePageLoaderProps) {
  const config = useLoadingConfig(pageType);

  // Select skeleton based on page type
  const SkeletonComponent = useMemo(() => {
    switch (pageType) {
      case 'tutor':
        return SkeletonTutor;
      case 'dashboard':
        return SkeletonDashboard;
      case 'practice':
        return SkeletonPractice;
      case 'profile':
        return SkeletonProfile;
      case 'settings':
        return SkeletonSettings;
      default:
        return SkeletonDefault;
    }
  }, [pageType]);

  return (
    <div className="relative min-h-screen bg-[#F8FAFC] overflow-hidden">
      {/* Skeleton background */}
      <SkeletonComponent />

      {/* Progress overlay card */}
      <ProgressCard
        steps={config.steps}
        microCopy={config.microCopy}
        pageTitle={config.pageTitle}
        emoji={config.emoji}
      />
    </div>
  );
}
