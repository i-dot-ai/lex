import { 
  AnimatedResultSkeleton, 
  AnimatedResultSkeletonList,
  ResultsHeaderSkeleton,
  ResultsSectionSkeleton 
} from "./animated-result-skeleton"

// Export the animated versions as the main skeleton components
export const ResultSkeleton = AnimatedResultSkeleton
export const ResultSkeletonList = AnimatedResultSkeletonList

// Export new components
export { ResultsHeaderSkeleton, ResultsSectionSkeleton }

// Keep legacy exports for backwards compatibility if needed
export { AnimatedResultSkeleton, AnimatedResultSkeletonList }
