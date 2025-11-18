import { ResultSkeletonList } from '@/components/result-skeleton'

export default function Loading() {
  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <ResultSkeletonList count={5} />
    </div>
  )
}
