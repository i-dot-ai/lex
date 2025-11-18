"use client"

import { motion } from "framer-motion"
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card"

const shimmerVariants = {
  animate: {
    backgroundPosition: ["0%", "100%", "0%"],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut",
    },
  },
}

const containerVariants = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
    },
  },
}

const itemVariants = {
  initial: { 
    opacity: 0, 
    y: 20,
    scale: 0.95,
  },
  animate: { 
    opacity: 1, 
    y: 0,
    scale: 1,
    transition: {
      duration: 0.5,
      ease: "easeOut",
    },
  },
}

const ShimmerSkeleton = ({ className }: { className: string }) => (
  <motion.div
    className={`bg-gradient-to-r from-muted via-muted/60 to-muted bg-[length:200%_100%] rounded-md ${className}`}
    variants={shimmerVariants}
    animate="animate"
  />
)

export function AnimatedResultSkeleton() {
  return (
    <motion.div
      variants={itemVariants}
      initial="initial"
      animate="animate"
      className="w-full"
    >
      <Card className="hover:shadow-md transition-all duration-300">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-4 mb-2">
            <ShimmerSkeleton className="h-5 w-3/4 flex-1" />
            <div className="flex items-center gap-1.5 shrink-0">
              <ShimmerSkeleton className="h-3.5 w-3.5 rounded" />
              <ShimmerSkeleton className="h-4 w-8" />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ShimmerSkeleton className="h-6 w-16" />
            <ShimmerSkeleton className="h-6 w-20" />
            <ShimmerSkeleton className="h-6 w-14" />
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="space-y-1 mb-4">
            <ShimmerSkeleton className="h-4 w-full" />
            <ShimmerSkeleton className="h-4 w-2/3" />
          </div>
          <ShimmerSkeleton className="h-9 w-32" />
        </CardContent>
      </Card>
    </motion.div>
  )
}

export function AnimatedResultSkeletonList({ count = 5 }: { count?: number }) {
  return (
    <motion.div
      variants={containerVariants}
      initial="initial"
      animate="animate"
      className="space-y-4"
    >
      {Array.from({ length: count }).map((_, i) => (
        <AnimatedResultSkeleton key={i} />
      ))}
    </motion.div>
  )
}

// Compact version for smaller spaces
export function CompactAnimatedSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-2"
    >
      <ShimmerSkeleton className="h-4 w-3/4" />
      <ShimmerSkeleton className="h-3 w-1/2" />
      <ShimmerSkeleton className="h-8 w-full" />
    </motion.div>
  )
}

// Results header skeleton for count and controls
export function ResultsHeaderSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex items-center justify-between gap-4"
    >
      <ShimmerSkeleton className="h-7 w-48" />
      <div className="flex items-center gap-2">
        <div className="relative">
          <ShimmerSkeleton className="h-10 w-64 rounded-md" />
        </div>
      </div>
    </motion.div>
  )
}

// Loading state for the entire results section
export function ResultsSectionSkeleton({ count = 5 }: { count?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-4"
    >
      <ResultsHeaderSkeleton />
      <AnimatedResultSkeletonList count={count} />
    </motion.div>
  )
}

// Alternative breathing animation for variety
export function BreathingResultSkeleton() {
  return (
    <motion.div
      animate={{
        scale: [1, 1.02, 1],
      }}
      transition={{
        duration: 2,
        repeat: Infinity,
        ease: "easeInOut",
      }}
      className="w-full"
    >
      <Card className="overflow-hidden">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-4 mb-2">
            <motion.div
              className="h-5 w-3/4 flex-1 bg-gradient-to-r from-muted via-accent to-muted bg-[length:200%_100%] rounded"
              animate={{ backgroundPosition: ["0%", "100%", "0%"] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <div className="flex items-center gap-1.5 shrink-0">
              <motion.div
                className="h-3.5 w-3.5 bg-gradient-to-r from-muted via-accent to-muted bg-[length:200%_100%] rounded"
                animate={{ backgroundPosition: ["0%", "100%", "0%"] }}
                transition={{ duration: 1.8, repeat: Infinity }}
              />
              <motion.div
                className="h-4 w-8 bg-gradient-to-r from-muted via-accent to-muted bg-[length:200%_100%] rounded"
                animate={{ backgroundPosition: ["0%", "100%", "0%"] }}
                transition={{ duration: 2.2, repeat: Infinity }}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {[16, 20, 14].map((width, i) => (
              <motion.div
                key={i}
                className={`h-6 w-${width} bg-gradient-to-r from-muted via-accent to-muted bg-[length:200%_100%] rounded`}
                animate={{ backgroundPosition: ["0%", "100%", "0%"] }}
                transition={{ 
                  duration: 1.6 + i * 0.2, 
                  repeat: Infinity,
                  delay: i * 0.1,
                }}
              />
            ))}
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="space-y-1 mb-4">
            <motion.div
              className="h-4 w-full bg-gradient-to-r from-muted via-accent to-muted bg-[length:200%_100%] rounded"
              animate={{ backgroundPosition: ["0%", "100%", "0%"] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <motion.div
              className="h-4 w-2/3 bg-gradient-to-r from-muted via-accent to-muted bg-[length:200%_100%] rounded"
              animate={{ backgroundPosition: ["0%", "100%", "0%"] }}
              transition={{ duration: 1.7, repeat: Infinity }}
            />
          </div>
          <motion.div
            className="h-9 w-32 bg-gradient-to-r from-muted via-accent to-muted bg-[length:200%_100%] rounded"
            animate={{ backgroundPosition: ["0%", "100%", "0%"] }}
            transition={{ duration: 1.4, repeat: Infinity }}
          />
        </CardContent>
      </Card>
    </motion.div>
  )
}