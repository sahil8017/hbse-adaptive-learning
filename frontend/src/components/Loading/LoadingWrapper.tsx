'use client';

import { ReactNode } from 'react';

interface LoadingWrapperProps {
  isLoading: boolean;
  children: ReactNode;
  skeleton: ReactNode;
  error?: string | null;
}

/**
 * Wraps content with conditional loading and error states
 *
 * Usage:
 * ```tsx
 * <LoadingWrapper
 *   isLoading={isLoading}
 *   skeleton={<DashboardLoading />}
 *   error={error}
 * >
 *   <YourContent />
 * </LoadingWrapper>
 * ```
 */
export default function LoadingWrapper({
  isLoading,
  children,
  skeleton,
  error,
}: LoadingWrapperProps) {
  if (error) {
    return (
      <div className="flex items-center justify-center py-12 text-red-600">
        <p>{error}</p>
      </div>
    );
  }

  if (isLoading) {
    return <>{skeleton}</>;
  }

  return <>{children}</>;
}
