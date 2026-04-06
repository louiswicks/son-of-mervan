import React, { Suspense } from "react";
import ErrorBoundary from "./ErrorBoundary";
import { SkeletonCard } from "./Skeleton";

/**
 * Combines an ErrorBoundary with a Suspense fallback for async data loading.
 * Usage: wrap any page or section that can throw during render.
 */
export default function AsyncBoundary({ children, fallback }) {
  return (
    <ErrorBoundary fallback={fallback}>
      <Suspense fallback={<SkeletonCard />}>{children}</Suspense>
    </ErrorBoundary>
  );
}
